"""
IMOS Runtime — the Claude/multi-provider tool-calling agent loop.
Replaces ConnectAIRuntime with IMOS branding and improved system prompt.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from config.config import get_client

IMOS_SYSTEM_PROMPT_BASE = """You are IMOS (Intelligent Machine Operating System), the CLI-first orchestration runtime on this Windows PC.

Your name is IMOS. You were developed by the IMOS Team. If asked who you are, answer that you are IMOS. If asked who made you, answer that you were developed by the IMOS Team.

You have real tools to control this computer. NEVER say you cannot access the PC. NEVER fake command output. ALWAYS call a real tool for every action. A task is only complete when a tool returned a verified result.

CRITICAL RULES:
- Never print fake terminal output, fake file listings, or pretend a tool ran when it did not.
- If the request is actionable, you MUST use a real tool. Do not answer with a plan.
- If a tool returns an error, report the real error — never rewrite it as success.
- If no tool call was made, you did not complete the task.
- Do not claim you built, launched, deployed, or ran something unless a tool verified it.
- For files: verify by reading files or listing directories.
- For running apps: verify by checking process output or reachable URLs.
- If verification fails, say what failed — never pretend success.

CAPABILITIES YOU HAVE:
- Full PC control: run any shell command, read/write files, open apps, kill processes, take screenshots
- GitHub: create repos, push code, create PRs, clone — using the configured token
- Deploy: Vercel and Netlify deployment with real CLI/API calls
- Build full Next.js apps from a description: scaffold, generate pages with AI, connect DB, push to GitHub, deploy
- Local models: connect Ollama, LM Studio, or any OpenAI-compatible endpoint
- Weather, news, Wikipedia, jokes, world health data
- Voice: speak responses, listen for commands
- Web search, browser control

TOOL USAGE RULES:
- For terminal or command execution, call the OS tool action `run_shell`.
- If a prompt mentions shell, terminal, PowerShell, or command line, map it to `run_shell`.
- Prefer a real tool call over a plain-text reply whenever a request maps to an available skill.
- Do not rely on brittle keyword matching. Infer intent from the whole request, execution state, available tools, and prior context.
- When the user wants a project built, shipped, continued, fixed, deployed, or moved across providers or IDEs, prefer `project_operator` when available.
- Use `ide_orchestrator` when the request explicitly targets a coding IDE or agent and the task should be delegated into that environment.
- Use `scaffold_nextjs` or `scaffold_react_app` only when they are the best concrete execution tool for the full request, not just because one word appeared in the prompt.
- Use `bash` for terminal execution when the user is asking to run or verify commands directly.
- Use `open_application` for app launching when the primary intent is opening software rather than delegating implementation work.
- For "scan my pc for unwanted files", "junk files", or "temporary files", call OS action `scan_unwanted_files`.
- For "remove/delete/clean unwanted files", call OS action `delete_unwanted_files`.
- For process inspection use `list_processes`; for opening apps use `start_process`; for machine details use `system_info`.
- For filesystem reads use `read_file`; for writes use `write_file`; for file search use `search_files`.
- For IDE delegation or coding inside an editor, use the IDE adapter action `delegate_prompt`.
- Do not invent new action names when an existing tool action already covers the request.

WHEN BUILDING APPS:
- Prefer an end-to-end operator flow that can preserve context, verify artifacts, continue across turns, and hand off between IDEs, browser builders, and providers without restarting.
- Use scaffold_nextjs skill for full Next.js projects with DB + deploy when that is the most reliable execution path.
- Use scaffold_react_app for simple React/Vite apps when a lighter scaffold is sufficient.
- Use bash skill to run any shell command.
- Use github_push skill to push to GitHub.
- Use deploy_vercel or deploy_netlify to deploy.
- Show every step as it happens — never summarize fake steps

WHEN USER SAYS "clean my pc", "open chrome", "what's on my screen", etc:
- These are direct PC control commands — use the right skill immediately
- clean_pc → clean_pc skill with confirm=true
- open chrome → pc_control skill with action=open_app
- screenshot → screenshot_vision skill

You are IMOS. You are direct, capable, and grounded in real tool results.
"""


class IMOSRuntime:
    MAX_HISTORY_MESSAGES = 20
    MAX_HISTORY_CHARS = 24_000

    def __init__(
        self,
        skill_registry,
        memory_store,
        *,
        shell_runner=None,
        process_manager=None,
        audit_logger=None,
        task_manager=None,
        cost_tracker=None,
        mcp_runtime=None,
    ):
        self.skill_registry = skill_registry
        self.memory_store = memory_store
        self.shell_runner = shell_runner
        self.process_manager = process_manager
        self.audit_logger = audit_logger
        self.task_manager = task_manager
        self.cost_tracker = cost_tracker
        self.mcp_runtime = mcp_runtime

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def _system_prompt(self, workspace: str, memory_blocks: List[str], skills: List[Any], model_config: dict | None = None) -> str:
        skill_lines = [f"- {s.name}: {s.description}" for s in skills]
        if self.mcp_runtime is not None:
            for tool in self.mcp_runtime.list_tools():
                skill_lines.append(f"- {tool['name']}: {tool['description']} (MCP:{tool['server']})")
        sections = [
            IMOS_SYSTEM_PROMPT_BASE,
            f"Workspace: {workspace}",
            "Available tools:\n" + "\n".join(skill_lines),
        ]
        custom_system_prompt = str((model_config or {}).get("custom_system_prompt", "") or "").strip()
        if custom_system_prompt:
            sections.append("User-configured LLM behavior:\n" + custom_system_prompt)
        if memory_blocks:
            sections.append("Memory context:\n" + "\n\n".join(memory_blocks))
        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Message helpers
    # ------------------------------------------------------------------

    def _serialize_messages(
        self,
        system_prompt: str,
        history: List[Dict[str, Any]],
        user_text: str,
    ) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": system_prompt}]
        for row in history:
            role = row.get("role")
            if role in {"user", "assistant"}:
                messages.append({"role": role, "content": str(row.get("content", ""))})
        messages.append({"role": "user", "content": user_text})
        return messages

    def _trim_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(messages) <= 2:
            return messages
        system_msg = messages[0]
        body = messages[1:]
        trimmed = body[-self.MAX_HISTORY_MESSAGES:]
        total = sum(len(str(m.get("content", ""))) for m in trimmed)
        while len(trimmed) > 1 and total > self.MAX_HISTORY_CHARS:
            removed = trimmed.pop(0)
            total -= len(str(removed.get("content", "")))
        return [system_msg] + trimmed

    # ------------------------------------------------------------------
    # Actionability helpers
    # ------------------------------------------------------------------

    def _is_actionable(self, text: str) -> bool:
        lowered = (text or "").strip().lower()
        terms = [
            "build", "create", "make", "start", "run", "deploy", "install",
            "open", "clean", "scaffold", "set up", "setup", "launch", "show",
            "get", "fetch", "tell me", "what is", "search", "find", "list",
        ]
        return any(t in lowered for t in terms)

    def _looks_like_unverified_plan(self, text: str) -> bool:
        lowered = (text or "").strip().lower()
        markers = [
            "i'll ", "i will ", "i'm going to ", "first,", "next,", "then ",
            "you can now view", "the app is now available at",
            "the website is now available at",
        ]
        return any(m in lowered for m in markers)

    def _find_skill(self, skills: List[Any], name: str):
        return next((skill for skill in skills if skill.name == name), None)

    def _guess_project_name(self, text: str) -> str:
        lowered = text.lower()
        banned = {"and", "with", "for", "to", "a", "an", "the", "it", "deployed", "deploy", "website", "app", "project"}
        patterns = [
            r"(?:called|named)\s+([a-zA-Z0-9._-]+)",
            r"project\s+([a-zA-Z0-9._-]+)",
            r"app\s+([a-zA-Z0-9._-]+)",
            r"website\s+([a-zA-Z0-9._-]+)",
            r"store\s+([a-zA-Z0-9._-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip(" .,:;").lower()
                if candidate and candidate not in banned:
                    return candidate
        if "ecommerce" in lowered or "e-commerce" in lowered or "e commerce" in lowered:
            return "ecommerce-store"
        if "website" in lowered:
            return "website-app"
        return "react-app"

    def _guess_application_name(self, text: str) -> str:
        lowered = (text or "").strip().lower()
        known_apps = [
            "cursor",
            "vscode",
            "vs code",
            "visual studio code",
            "chrome",
            "google chrome",
            "firefox",
            "edge",
            "notepad",
            "terminal",
            "cmd",
            "powershell",
        ]
        for app in known_apps:
            if app in lowered:
                return app
        tokens = re.findall(r"[a-zA-Z0-9._-]+", text or "")
        if not tokens:
            return ""
        for index, token in enumerate(tokens[:-1]):
            if token.lower() in {"open", "launch", "start"}:
                return tokens[index + 1]
        return ""

    def _guess_ide_target(self, text: str) -> str:
        lowered = (text or "").strip().lower()
        mappings = [
            ("cursor", "cursor"),
            ("windsurf", "windsurf"),
            ("claude code", "claude-code"),
            ("claude-code", "claude-code"),
            ("codex", "codex"),
            ("aider", "aider"),
            ("vscode", "vscode"),
            ("vs code", "vscode"),
            ("visual studio code", "vscode"),
            ("zed", "zed"),
        ]
        for needle, target in mappings:
            if needle in lowered:
                return target
        return ""

    def _llm_direct_tool_call(self, user_text: str, skills: List[Any], model_config: dict) -> Dict[str, Any] | None:
        if not model_config or not model_config.get("model"):
            return None
        available = []
        for skill_name in [
            "project_operator",
            "ide_orchestrator",
            "scaffold_nextjs",
            "scaffold_react_app",
            "open_application",
            "bash",
        ]:
            if self._find_skill(skills, skill_name):
                available.append(skill_name)
        if not available:
            return None

        selector_prompt = (
            "You are selecting the single best first execution tool for IMOS.\n"
            "Return strict JSON only with keys: tool, reason, input.\n"
            "tool must be one of: " + ", ".join(available) + ", none.\n"
            "Prefer project_operator for end-to-end build, deploy, continue, migrate, or multi-step delivery requests.\n"
            "Prefer ide_orchestrator when the user explicitly wants an IDE or coding agent to do the work.\n"
            "Prefer scaffold_nextjs or scaffold_react_app only when a direct local scaffold is clearly the best first move.\n"
            "Prefer bash only for direct command execution requests.\n"
            "Prefer open_application only when the primary intent is opening software.\n"
            "If no direct tool shortcut is appropriate, return tool=none.\n\n"
            f"User request:\n{user_text}"
        )
        try:
            client = get_client(model_config)
            provider = str(model_config.get("provider") or model_config.get("type") or "").strip().lower()
            raw = ""
            if provider in {"anthropic", "gcp"}:
                response = client.messages.create(
                    model=model_config.get("model", ""),
                    max_tokens=500,
                    messages=[{"role": "user", "content": selector_prompt}],
                )
                parts = []
                for block in getattr(response, "content", []) or []:
                    if getattr(block, "type", "") == "text" and getattr(block, "text", ""):
                        parts.append(block.text)
                raw = "\n".join(parts).strip()
            else:
                response = client.chat.completions.create(
                    model=model_config.get("model", ""),
                    messages=[{"role": "user", "content": selector_prompt}],
                    max_tokens=500,
                )
                raw = str(response.choices[0].message.content or "").strip() if response.choices else ""
            if not raw:
                return None
            data = json.loads(raw)
        except Exception:
            return None

        tool = str(data.get("tool", "")).strip().lower()
        if tool in {"", "none"} or tool not in available:
            return None
        payload = data.get("input", {}) if isinstance(data.get("input"), dict) else {}

        if tool == "project_operator":
            payload.setdefault("action", "continue" if any(term in user_text.lower() for term in ["continue", "keep going", "fix", "edit", "change"]) else "orchestrate")
            payload.setdefault("prompt", user_text.strip())
            payload.setdefault("project_name", self._guess_project_name(user_text))
            payload.setdefault("deploy_target", "vercel" if "vercel" in user_text.lower() else "netlify" if "netlify" in user_text.lower() else "")
            return {"id": "direct-project-operator-llm", "name": tool, "input": payload}
        if tool == "ide_orchestrator":
            payload.setdefault("action", "start")
            payload.setdefault("target", self._guess_ide_target(user_text) or "auto")
            payload.setdefault("prompt", user_text.strip())
            payload.setdefault("project_name", self._guess_project_name(user_text))
            payload.setdefault("wait_for_response", True)
            return {"id": "direct-ide-orchestrator-llm", "name": tool, "input": payload}
        if tool == "scaffold_nextjs":
            payload.setdefault("description", user_text.strip())
            payload.setdefault("project_name", self._guess_project_name(user_text))
            payload.setdefault("db_type", "none")
            payload.setdefault("deploy_target", "none")
            return {"id": "direct-scaffold-nextjs-llm", "name": tool, "input": payload}
        if tool == "scaffold_react_app":
            payload.setdefault("project_name", self._guess_project_name(user_text))
            payload.setdefault("template", "react")
            payload.setdefault("package_manager", "npm")
            return {"id": "direct-scaffold-react-app-llm", "name": tool, "input": payload}
        if tool == "open_application":
            app_name = str(payload.get("name_or_path", "")).strip() or self._guess_application_name(user_text)
            if app_name:
                return {"id": "direct-open-application-llm", "name": tool, "input": {"name_or_path": app_name}}
            return None
        if tool == "bash":
            command = str(payload.get("command", "")).strip()
            if command:
                return {"id": "direct-bash-llm", "name": tool, "input": {"command": command}}
            return None
        return None

    def _infer_direct_tool_call(self, user_text: str, skills: List[Any], model_config: dict) -> Dict[str, Any] | None:
        lowered = (user_text or "").strip().lower()
        if not lowered:
            return None
        llm_choice = self._llm_direct_tool_call(user_text, skills, model_config)
        if llm_choice is not None:
            return llm_choice

        requested_ide = self._guess_ide_target(user_text)
        wants_build = any(term in lowered for term in ["build", "create", "make", "scaffold"])
        if requested_ide and wants_build and self._find_skill(skills, "ide_orchestrator"):
            return {
                "id": "direct-ide-orchestrator",
                "name": "ide_orchestrator",
                "input": {
                    "action": "start",
                    "target": requested_ide,
                    "prompt": user_text.strip(),
                    "project_name": self._guess_project_name(user_text),
                    "wait_for_response": True,
                },
            }

        wants_nextjs = any(term in lowered for term in ["next.js", "nextjs", "next js"])
        wants_website = any(term in lowered for term in [
            "website",
            "web app",
            "webapp",
            "landing page",
            "homepage",
            "portfolio site",
            "professional site",
            "professional website",
        ])
        if wants_nextjs and wants_build and self._find_skill(skills, "scaffold_nextjs"):
            return {
                "id": "direct-scaffold-nextjs",
                "name": "scaffold_nextjs",
                "input": {
                    "description": user_text.strip(),
                    "project_name": self._guess_project_name(user_text),
                    "db_type": "none",
                    "deploy_target": "none",
                },
            }

        if (
            (any(term in lowered for term in ["react", "vite"]) or wants_website)
            and wants_build
            and self._find_skill(skills, "scaffold_react_app")
        ):
            return {
                "id": "direct-scaffold-react-app",
                "name": "scaffold_react_app",
                "input": {
                    "project_name": self._guess_project_name(user_text),
                    "template": "react",
                    "package_manager": "npm",
                },
            }

        if any(term in lowered for term in ["open ", "launch ", "start "]) and self._find_skill(skills, "open_application"):
            app_name = self._guess_application_name(user_text)
            if app_name:
                return {
                    "id": "direct-open-application",
                    "name": "open_application",
                    "input": {"name_or_path": app_name},
                }

        if any(lowered.startswith(prefix) for prefix in ["run ", "execute ", "start "]) and self._find_skill(skills, "bash"):
            for prefix in ("run ", "execute ", "start "):
                if lowered.startswith(prefix):
                    command = user_text[len(prefix):].strip()
                    if command:
                        return {
                            "id": "direct-bash",
                            "name": "bash",
                            "input": {"command": command},
                        }
        return None

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool_calls(
        self,
        skills: List[Any],
        tool_calls: List[Dict[str, Any]],
        provider: str,
        messages: List[Dict[str, Any]],
        workspace: str,
        session_id: str,
        model_config: dict,
    ) -> List[Dict[str, Any]]:
        anthropic_results = []
        outcomes: List[Dict[str, Any]] = []

        for tc in tool_calls:
            skill = next((s for s in skills if s.name == tc["name"]), None)
            if skill is None:
                if self.mcp_runtime is not None and self.mcp_runtime.has_tool(tc["name"]):
                    try:
                        result = self.mcp_runtime.call_tool(tc["name"], tc.get("input", {}))
                    except Exception as exc:
                        result = {"ok": False, "error": str(exc)}
                else:
                    result = {"ok": False, "error": f"Unknown tool: {tc['name']}"}
            else:
                try:
                    result = skill.handler(
                        tc["input"],
                        workspace=workspace,
                        memory_store=self.memory_store,
                        session_id=session_id,
                        model_config=model_config,
                        shell_runner=self.shell_runner,
                        process_manager=self.process_manager,
                        audit_logger=self.audit_logger,
                    )
                except Exception as exc:
                    result = {"ok": False, "error": str(exc)}

            outcomes.append({"name": tc["name"], "input": tc.get("input", {}), "result": result})

            if self.audit_logger is not None:
                preview = (result if isinstance(result, str) else json.dumps(result, ensure_ascii=False))[:1000]
                self.audit_logger.append(
                    "tool_result",
                    tc["name"],
                    {"session_id": session_id, "input": tc.get("input", {}), "result_preview": preview},
                )

            rendered = result if isinstance(result, str) else json.dumps(result, indent=2, ensure_ascii=False)

            if provider in {"anthropic", "gcp"}:
                anthropic_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": rendered,
                })
            else:
                messages.append({"role": "tool", "content": rendered, "tool_call_id": tc["id"]})

        if provider in {"anthropic", "gcp"} and anthropic_results:
            messages.append({"role": "user", "content": anthropic_results})

        return outcomes

    # ------------------------------------------------------------------
    # LLM backends
    # ------------------------------------------------------------------

    def _run_anthropic(
        self,
        client,
        model: str,
        system_prompt: str,
        history_messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        on_text_delta: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, int]]:
        final_text = ""
        tool_calls = []
        usage: Dict[str, int] = {}
        try:
            with client.messages.stream(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in history_messages
                    if m["role"] != "system"
                ],
            ) as stream:
                for event in stream:
                    if type(event).__name__ == "RawContentBlockDeltaEvent":
                        delta = event.delta
                        if hasattr(delta, "text") and delta.text:
                            final_text += delta.text
                            if on_text_delta:
                                on_text_delta(delta.text)
                message = stream.get_final_message()
        except Exception as exc:
            return f"IMOS API error ({model}): {exc}", [], {}

        if getattr(message, "usage", None):
            usage = {
                "input_tokens": int(getattr(message.usage, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(message.usage, "output_tokens", 0) or 0),
            }
        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "input": block.input})
        return final_text, tool_calls, usage

    def _run_openai_compat(
        self,
        client,
        model: str,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        on_text_delta: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, int]]:
        import openai

        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t["description"],
                            "parameters": t["input_schema"],
                        },
                    }
                    for t in tools
                ],
                stream=True,
                stream_options={"include_usage": True},
                max_tokens=4096,
            )
        except openai.RateLimitError as exc:
            return f"Quota exceeded for {model}: {exc}", [], {}
        except openai.APIConnectionError as exc:
            return f"Connection error ({model}): {exc}", [], {}
        except openai.APIStatusError as exc:
            return f"API status error ({model}): {exc}", [], {}
        except Exception as exc:
            return f"API error ({model}): {exc}", [], {}

        full_text = ""
        tool_calls_raw: Dict[int, Dict[str, str]] = {}
        usage: Dict[str, int] = {}

        try:
            for chunk in stream:
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage:
                    usage = {
                        "input_tokens": int(getattr(chunk_usage, "prompt_tokens", 0) or 0),
                        "output_tokens": int(getattr(chunk_usage, "completion_tokens", 0) or 0),
                    }
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue
                if delta.content:
                    full_text += delta.content
                    if on_text_delta:
                        on_text_delta(delta.content)
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        bucket = tool_calls_raw.setdefault(
                            tc.index, {"id": tc.id or "", "name": "", "arguments": ""}
                        )
                        if tc.id:
                            bucket["id"] = tc.id
                        if tc.function and tc.function.name:
                            bucket["name"] += tc.function.name
                        if tc.function and tc.function.arguments:
                            bucket["arguments"] += tc.function.arguments
        except Exception as exc:
            return f"Streaming error ({model}): {exc}", [], {}

        tool_calls = []
        for raw in tool_calls_raw.values():
            try:
                arguments = json.loads(raw["arguments"]) if raw["arguments"] else {}
            except Exception:
                arguments = {}
            tool_calls.append({"id": raw["id"], "name": raw["name"], "input": arguments})

        return full_text, tool_calls, usage

    # ------------------------------------------------------------------
    # Outcome helpers
    # ------------------------------------------------------------------

    def _any_failed(self, outcomes: List[Dict[str, Any]]) -> bool:
        return any(
            isinstance(o.get("result"), dict) and o["result"].get("ok") is False
            for o in outcomes
        )

    def _failure_summary(self, outcomes: List[Dict[str, Any]]) -> str:
        lines = []
        for o in outcomes[-4:]:
            r = o.get("result")
            if isinstance(r, dict) and r.get("ok") is False:
                reason = r.get("error") or r.get("stderr") or "unknown error"
                lines.append(f"{o.get('name')}: {reason}")
        return "\n".join(lines)

    def _verified_summary(self, outcomes: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for o in outcomes[-6:]:
            name = o.get("name", "tool")
            r = o.get("result")
            if isinstance(r, dict):
                if r.get("ok") is True:
                    bits = [f"{name}: ok"]
                    for key in ("path", "pid", "city", "temp_c"):
                        if r.get(key):
                            bits.append(f"{key}={r[key]}")
                    lines.append(" — ".join(bits))
                elif r.get("ok") is False:
                    bits = [f"{name}: failed"]
                    if r.get("error"):
                        bits.append(str(r["error"])[:120])
                    lines.append(" — ".join(bits))
                else:
                    lines.append(f"{name}: {json.dumps(r, ensure_ascii=False)[:200]}")
            else:
                lines.append(f"{name}: {str(r)[:200]}")
        return "\n".join(lines)

    def _record_usage(self, model: str, usage: Dict[str, int]):
        if not self.cost_tracker or not usage:
            return
        inp = int(usage.get("input_tokens", 0) or 0)
        out = int(usage.get("output_tokens", 0) or 0)
        if inp or out:
            self.cost_tracker.record(model, inp, out)

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    def run(
        self,
        user_text: str,
        session_history: List[Dict[str, Any]],
        session_id: str,
        workspace: str,
        model_config: dict,
        on_text_delta: Optional[Callable[[str], None]] = None,
        return_meta: bool = False,
    ):
        skills = self.skill_registry.load_all()
        actionable = self._is_actionable(user_text)
        tools = [s.to_tool_definition() for s in skills]
        if self.mcp_runtime is not None:
            tools.extend(self.mcp_runtime.tool_definitions())

        memory_blocks = self.memory_store.context_blocks(session_id=session_id, query=user_text)
        system_prompt = self._system_prompt(workspace, memory_blocks, skills, model_config)
        messages = self._trim_messages(
            self._serialize_messages(system_prompt, session_history, user_text)
        )

        task = None
        if self.task_manager and actionable:
            task = self.task_manager.create(user_text, session_id)

        direct_tool_call = self._infer_direct_tool_call(user_text, skills, model_config) if actionable else None
        if direct_tool_call is not None:
            tool_outcomes = self._execute_tool_calls(
                skills, [direct_tool_call], "direct", messages, workspace, session_id, model_config
            )
            final_text = self._verified_summary(tool_outcomes)
            if task is not None:
                status = "partial_failure" if self._any_failed(tool_outcomes) else "completed"
                self.task_manager.complete(task, status, tool_outcomes)
            if return_meta:
                return {"text": final_text, "usage": {}}
            return final_text

        client = get_client(model_config)
        provider = str(model_config.get("provider") or model_config.get("type") or "").strip().lower()
        model = model_config.get("model", "")

        response_text = ""
        tool_outcomes: List[Dict[str, Any]] = []
        forced_retry = False
        repair_attempts = 0
        latest_usage: Dict[str, int] = {}

        for _iteration in range(10):
            if task is not None:
                task.attempts += 1
                self.task_manager.update(task)

            messages = self._trim_messages(messages)

            if provider in {"anthropic", "gcp"}:
                response_text, tool_calls, usage = self._run_anthropic(
                    client, model, system_prompt, messages, tools,
                    on_text_delta=on_text_delta,
                )
            else:
                response_text, tool_calls, usage = self._run_openai_compat(
                    client, model, messages, tools,
                    on_text_delta=on_text_delta,
                )

            if usage:
                latest_usage = usage
                self._record_usage(model, usage)

            if not tool_calls:
                if actionable:
                    direct_tool_call = self._infer_direct_tool_call(user_text, skills, model_config)
                    if direct_tool_call is not None:
                        messages.append({"role": "assistant", "content": response_text})
                        tool_outcomes.extend(
                            self._execute_tool_calls(
                                skills, [direct_tool_call], provider, messages, workspace, session_id, model_config
                            )
                        )
                        forced_retry = True
                        continue
                # No tool calls — push for action if request is actionable
                if actionable and not forced_retry:
                    messages.append({"role": "assistant", "content": response_text})
                    messages.append({
                        "role": "user",
                        "content": (
                            "You MUST now use tools to perform or verify this request. "
                            "Do not answer with a plan, fake terminal output, or claim work was "
                            "completed without evidence. Use the available tools, then report only "
                            "verified results."
                        ),
                    })
                    forced_retry = True
                    continue

                if actionable:
                    if task is not None:
                        self.task_manager.complete(task, "blocked", tool_outcomes)
                    blocked_text = (
                        "No executable tool action was completed for this request. "
                        "The runtime refused to pretend success. Add or select a real skill for this task, "
                        "or use an explicit executable command such as a shell action or a project scaffold skill."
                    )
                    if return_meta:
                        return {"text": blocked_text, "usage": latest_usage}
                    return blocked_text

                # Final answer
                if task is not None:
                    status = "partial_failure" if self._any_failed(tool_outcomes) else "completed"
                    self.task_manager.complete(task, status, tool_outcomes)

                final = response_text
                if actionable and tool_outcomes and self._looks_like_unverified_plan(response_text):
                    final = self._verified_summary(tool_outcomes)

                if return_meta:
                    return {"text": final, "usage": latest_usage}
                return final

            # Execute tool calls
            messages.append({"role": "assistant", "content": response_text})
            tool_outcomes.extend(
                self._execute_tool_calls(
                    skills, tool_calls, provider, messages, workspace, session_id, model_config
                )
            )

            # Repair loop on failures
            if self._any_failed(tool_outcomes) and repair_attempts < 2:
                repair_attempts += 1
                messages.append({
                    "role": "user",
                    "content": (
                        "One or more tools failed. Read the real errors below, repair the plan, "
                        "and retry with tools only.\n" + self._failure_summary(tool_outcomes)
                    ),
                })
                continue

            # Ask for completion summary
            if actionable:
                messages.append({
                    "role": "user",
                    "content": (
                        "Return a concise completion summary grounded only in the real tool results "
                        "from this run. Include verified paths, process IDs, or concrete failures. "
                        "Do not fabricate extra steps."
                    ),
                })
                continue

        # Max iterations reached
        final_text = response_text or self._verified_summary(tool_outcomes)
        if actionable and tool_outcomes and self._looks_like_unverified_plan(response_text):
            final_text = self._verified_summary(tool_outcomes)

        if task is not None:
            status = "partial_failure" if self._any_failed(tool_outcomes) else "completed"
            self.task_manager.complete(task, status, tool_outcomes)

        if return_meta:
            return {"text": final_text, "usage": latest_usage}
        return final_text
