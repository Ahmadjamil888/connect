from __future__ import annotations

import json
import re
import uuid
from typing import Any

from imos.models import IMOSSubtask, IMOSTask
from imos.registry import AdapterRegistry


class TaskRouter:
    ADAPTER_ALIASES = {
        "google_search": "search_web",
        "web_search": "search_web",
        "search": "search_web",
        "browser": "browser_action",
        "web_browser": "browser_action",
        "terminal": "shell_command",
        "powershell": "shell_command",
        "command_line": "shell_command",
        "github": "git_operation",
        "git": "git_operation",
    }

    INTENT_CAPABILITY = {
        "code_generation": "write_file",
        "code_editing": "apply_diff",
        "code_review": "read_file",
        "file_operation": "read_file",
        "send_message": "send_message",
        "search_web": "navigate",
        "git_operation": "repo",
        "payment": "charge",
        "meeting": "create_meeting",
        "browser_action": "navigate",
        "shell_command": "run_shell",
        "question_answer": "chat",
        "multi_step": "chat",
        "navigate": "navigate",
        "start_process": "start_process",
        "list_processes": "list_processes",
        "system_info": "system_info",
        "read_file": "read_file",
        "write_file": "write_file",
        "search_files": "search_files",
    }

    def __init__(self, registry: AdapterRegistry, settings: dict[str, Any], synthesis_adapter=None) -> None:
        self.registry = registry
        self.settings = settings
        self.synthesis_adapter = synthesis_adapter

    async def decompose(self, prompt: str, context: dict[str, Any] | None = None) -> list[IMOSSubtask]:
        if self.synthesis_adapter:
            plan = await self._llm_decompose(prompt, context or {})
            if plan:
                return plan
        return self._heuristic_decompose(prompt)

    async def _llm_decompose(self, prompt: str, context: dict[str, Any]) -> list[IMOSSubtask]:
        task = IMOSTask(
            task_id=str(uuid.uuid4()),
            prompt=(
                "Return JSON only with schema: "
                '{"subtasks":[{"task_id":"...","subtask_type":"code_generation|code_editing|code_review|file_operation|send_message|search_web|git_operation|payment|meeting|browser_action|shell_command|question_answer|multi_step","target_adapter":"adapter_name","prompt":"rewritten prompt","priority":1,"can_run_parallel":false,"depends_on":[]}]} '
                f"\nPrompt: {prompt}\nContext: {json.dumps(context)}"
            ),
            subtask_type="question_answer",
            target_adapter=self.synthesis_adapter.name,
            context=context,
            metadata={"system_prompt": "You are an IMOS router. Produce strict JSON only."},
        )
        result = await self.synthesis_adapter.send(task)
        if not result.success or not result.output:
            return []
        try:
            data = json.loads(str(result.output))
            subtasks = []
            for entry in data.get("subtasks", []):
                subtasks.append(
                    IMOSTask(
                        task_id=entry.get("task_id", str(uuid.uuid4())),
                        prompt=entry["prompt"],
                        subtask_type=entry["subtask_type"],
                        target_adapter=entry["target_adapter"],
                        priority=int(entry.get("priority", 0)),
                        context=context,
                        metadata={"can_run_parallel": bool(entry.get("can_run_parallel", False)), "depends_on": entry.get("depends_on", [])},
                    )
                )
            return [IMOSSubtask(original_prompt=prompt, subtasks=subtasks, routing_explanation="LLM-routed task graph")]
        except Exception:
            return []

    def _heuristic_decompose(self, prompt: str) -> list[IMOSSubtask]:
        lowered = prompt.lower()
        parts = [part.strip() for part in prompt.replace(" and then ", ",").replace(" then ", ",").split(",") if part.strip()]
        tasks: list[IMOSTask] = []
        for index, part in enumerate(parts or [prompt]):
            subtask_type = self._infer_intent(part.lower())
            target = self._select_adapter(subtask_type)
            metadata = self._build_task_metadata(part, subtask_type, index, tasks)
            tasks.append(
                IMOSTask(
                    task_id=str(uuid.uuid4()),
                    prompt=part,
                    subtask_type=subtask_type,
                    target_adapter=target,
                    priority=index,
                    metadata=metadata,
                )
            )
        return [IMOSSubtask(original_prompt=prompt, subtasks=tasks, routing_explanation=f"Heuristic routing for prompt: {lowered[:80]}")]

    def _infer_intent(self, lowered: str) -> str:
        if any(token in lowered for token in ["weather", "temperature in ", "forecast", "news about ", "search for ", "look up ", "google ", "find on web", "search the web"]):
            return "search_web"
        if any(token in lowered for token in ["list processes", "running apps", "running processes", "show processes"]):
            return "list_processes"
        if any(token in lowered for token in ["system info", "cpu usage", "ram usage", "disk usage", "ip address", "hostname"]):
            return "system_info"
        if any(token in lowered for token in ["open website", "go to ", "visit ", "browse ", "open url"]) or "http://" in lowered or "https://" in lowered:
            return "navigate"
        if any(token in lowered for token in ["open app", "launch ", "start app", "open cursor", "open vscode", "open vs code", "open chrome", "open notepad", "open terminal", "open explorer", "open file explorer"]):
            return "start_process"
        if any(token in lowered for token in ["read file", "open file", "show file", "view file"]):
            return "read_file"
        if any(token in lowered for token in ["write file", "save file", "create file", "make file"]):
            return "write_file"
        if any(token in lowered for token in ["search files", "find file", "find folder", "search folder"]):
            return "search_files"
        if any(token in lowered for token in ["commit", "branch", "pull request", "repo", "git"]):
            return "git_operation"
        if any(token in lowered for token in ["slack", "discord", "telegram", "email", "message"]):
            return "send_message"
        if any(token in lowered for token in ["browser", "click", "form", "website"]):
            return "browser_action"
        if any(token in lowered for token in ["shell", "terminal", "command", "powershell", "bash"]):
            return "shell_command"
        if any(token in lowered for token in ["write file", "save file", "create file", "edit file"]):
            return "code_editing"
        if any(token in lowered for token in ["meeting", "zoom", "calendar", "schedule"]):
            return "meeting"
        if any(token in lowered for token in ["pay", "charge", "invoice", "subscription"]):
            return "payment"
        return "question_answer"

    def resolve_target_adapter(self, requested: str, subtask_type: str, prompt: str = "") -> str:
        explicit = self.registry.get(requested)
        if explicit is not None:
            return explicit.name

        normalized = str(requested or "").strip().lower().replace("-", "_").replace(" ", "_")
        alias_type = self.ADAPTER_ALIASES.get(normalized)
        if alias_type:
            return self._select_adapter(alias_type)

        inferred_type = subtask_type or self._infer_intent(prompt.lower())
        fallback = self._select_adapter(inferred_type)
        if fallback != "unassigned":
            return fallback
        return requested

    def _build_task_metadata(self, prompt: str, subtask_type: str, index: int, existing_tasks: list[IMOSTask]) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "can_run_parallel": False if index > 0 else True,
            "depends_on": [existing_tasks[-1].task_id] if existing_tasks else [],
        }
        lowered = prompt.lower().strip()
        if subtask_type == "navigate":
            match = re.search(r"(https?://\S+|www\.\S+)", prompt, re.IGNORECASE)
            url = match.group(1) if match else ""
            if url and not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            if url:
                metadata["action"] = "navigate"
                metadata["params"] = {"url": url}
        elif subtask_type == "start_process":
            command = re.sub(r"^(open|launch|start)\s+", "", lowered).strip()
            aliases = {
                "file explorer": "explorer",
                "explorer": "explorer",
                "terminal": "powershell",
                "command prompt": "cmd",
                "vs code": "code",
            }
            command = aliases.get(command, command)
            if command:
                metadata["action"] = "start_process"
                metadata["params"] = {"command": command}
        elif subtask_type == "search_web":
            query = re.sub(r"^(search for|search the web for|search the web|look up|google)\s+", "", prompt.strip(), flags=re.IGNORECASE).strip()
            metadata["action"] = "search_web"
            metadata["params"] = {"query": query or prompt.strip()}
        elif subtask_type in {"list_processes", "system_info", "read_file", "write_file", "search_files"}:
            metadata["action"] = subtask_type
        return metadata

    def _select_adapter(self, subtask_type: str) -> str:
        capability = self.INTENT_CAPABILITY.get(subtask_type, "chat")
        candidates = self.registry.get_capable_adapters(capability)
        if not candidates:
            all_models = self.registry.get_by_type("model")
            if all_models:
                return all_models[0].name
            return "unassigned"
        preferred_name = self.settings.get("preferred_adapters", {}).get(subtask_type)
        if preferred_name:
            for adapter in candidates:
                if adapter.name == preferred_name:
                    return adapter.name
        healthy = [adapter for adapter in candidates if adapter.status == "connected"] or candidates
        return sorted(healthy, key=lambda adapter: adapter.name)[0].name
