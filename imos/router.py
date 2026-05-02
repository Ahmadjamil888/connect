from __future__ import annotations

import json
import uuid
from typing import Any

from imos.models import IMOSSubtask, IMOSTask
from imos.registry import AdapterRegistry


class TaskRouter:
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
            tasks.append(
                IMOSTask(
                    task_id=str(uuid.uuid4()),
                    prompt=part,
                    subtask_type=subtask_type,
                    target_adapter=target,
                    priority=index,
                    metadata={"can_run_parallel": False if index > 0 else len(parts) == 1, "depends_on": [tasks[-1].task_id] if tasks else []},
                )
            )
        return [IMOSSubtask(original_prompt=prompt, subtasks=tasks, routing_explanation=f"Heuristic routing for prompt: {lowered[:80]}")]

    def _infer_intent(self, lowered: str) -> str:
        if any(token in lowered for token in ["commit", "branch", "pull request", "repo", "git"]):
            return "git_operation"
        if any(token in lowered for token in ["slack", "discord", "telegram", "email", "message"]):
            return "send_message"
        if any(token in lowered for token in ["browser", "open url", "click", "form", "website"]):
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
