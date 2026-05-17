from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from config.config import get_client


class ConnectAIRuntime:
    MAX_HISTORY_MESSAGES = 20
    MAX_HISTORY_CHARS = 24000

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
        event_bus=None,
        session_manager=None,
    ):
        self.skill_registry = skill_registry
        self.memory_store = memory_store
        self.shell_runner = shell_runner
        self.process_manager = process_manager
        self.audit_logger = audit_logger
        self.task_manager = task_manager
        self.cost_tracker = cost_tracker
        self.mcp_runtime = mcp_runtime
        self.event_bus = event_bus
        self.session_manager = session_manager
        self.consent_manager = None

    def _missing_skill_message(self, name: str) -> str:
        if name == "computer_control":
            return "computer_control is not installed.\nRun: pip install pyautogui pygetwindow pillow\nThen restart IMOS."
        return f"Skill '{name}' not found. Type /help to see available commands."

    def _is_actionable_request(self, text: str) -> bool:
        lowered = (text or "").strip().lower()
        actionable_terms = [
            "build",
            "create",
            "make",
            "start",
            "run",
            "deploy",
            "install",
            "open",
            "clean",
            "scaffold",
            "set up",
            "setup",
            "launch",
        ]
        return any(term in lowered for term in actionable_terms)

    def _make_plan(self, user_text: str, skills: List[Any]) -> List[Dict[str, Any]]:
        lowered = (user_text or "").strip().lower()
        plan: List[Dict[str, Any]] = [{"step": "Understand request and inspect current workspace state", "status": "pending"}]
        if any(term in lowered for term in ["react", "vite", "website", "web app", "e-commerce", "ecommerce"]):
            if self._find_skill(skills, "scaffold_react_app"):
                plan.append({"step": "Scaffold a real React project with dependencies", "status": "pending"})
            if self._find_skill(skills, "path_exists"):
                plan.append({"step": "Verify generated project files on disk", "status": "pending"})
        if any(term in lowered for term in ["run", "start", "dev server", "launch"]) and self._find_skill(skills, "start_dev_server"):
            plan.append({"step": "Start a background process and capture logs", "status": "pending"})
            if self._find_skill(skills, "http_probe"):
                plan.append({"step": "Probe the local URL to verify the server is reachable", "status": "pending"})
        if len(plan) == 1:
            plan.append({"step": "Choose and execute the best available local skill", "status": "pending"})
            plan.append({"step": "Verify the result with real filesystem or process evidence", "status": "pending"})
        return plan

    def _system_prompt(self, workspace: str, memory_blocks: List[str], skills: List[Any], model_config: dict | None = None) -> str:
        skill_lines = []
        for skill in skills:
            skill_lines.append(f"- {skill.name}: {skill.description}")
        if self.mcp_runtime is not None:
            for tool in self.mcp_runtime.list_tools():
                skill_lines.append(f"- {tool['name']}: {tool['description']} (MCP:{tool['server']})")
        sections = [
            "You are IMOS, the Intelligent Machine Operating System.",
            "Your name is IMOS. If the user asks your name, answer IMOS.",
            "You were developed by the IMOS Team. If the user asks who made you, answer that you were developed by the IMOS Team.",
            "Your primary function is to combine shell, voice, dashboard, automation, and session history into one unified runtime.",
            "Treat shell, voice, and dashboard activity as one operator context rather than separate personalities.",
            "Address the user naturally and directly. Your tone can be concise and assistant-like, but your output must stay factual and tool-grounded.",
            "You act through local tools and skills available on this machine.",
            "If a user asks for something that can be done with an available skill, do it instead of giving generic advice.",
            "CRITICAL RULES:",
            "- Never print fake terminal output, fake file listings, or pretend a tool ran when it did not.",
            "- If the request is actionable, you must use a real tool or explicitly say no tool action was completed.",
            "- If a tool returns an error, report the real error instead of rewriting it as success.",
            "- If no tool call was made, you did not complete the task.",
            "Do not say you are unable to access the PC when a skill exists for the task.",
            "The gateway owns sessions and command routing. Only act on natural-language tasks here.",
            "Prefer acting over explaining. Explain only when blocked, unsafe, or missing credentials.",
            "Do not claim you built, launched, deployed, or ran something unless you verified it with concrete evidence.",
            "For files and projects, verify by reading files, listing directories, or checking generated artifacts.",
            "For running apps or dev servers, verify by starting them with a real command and checking process output, logs, or reachable local URLs.",
            "If verification fails, explicitly say what failed instead of pretending success.",
            "For actionable requests, your final answer must be grounded in the actual tool results from this run.",
            "Do not emit imaginary command logs, file paths, URLs, or success messages.",
            "You must prefer an actual tool call over a plain-text reply whenever the request maps to an available skill.",
            "If a voice transcript is just your name or an attention word with no task, do not answer with trivia or generic chat.",
            "If a voice transcript starts with your name, treat the name as attention and execute only the remaining task.",
            "Routing examples:",
            "- 'build me a website' -> scaffold_react_app unless the user explicitly asks for Next.js.",
            "- 'build me a Next.js website' -> scaffold_nextjs.",
            "- shell, terminal, PowerShell, or command requests -> bash.",
            "- 'open cursor' or 'launch vscode' -> open_application.",
            "If a request is actionable and no exact mapping exists, choose the closest executable skill instead of replying with advice.",
            f"Workspace: {workspace}",
            "Available skills:\n" + "\n".join(skill_lines),
        ]
        custom_system_prompt = str((model_config or {}).get("custom_system_prompt", "") or "").strip()
        if custom_system_prompt:
            sections.append("User-configured LLM behavior:\n" + custom_system_prompt)
        if memory_blocks:
            sections.append("Memory context:\n" + "\n\n".join(memory_blocks))
        return "\n\n".join(sections)

    def _serialize_messages(self, system_prompt: str, history: List[Dict[str, Any]], user_text: str) -> List[Dict[str, str]]:
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
        system_message = messages[0]
        body = messages[1:]
        trimmed = body[-self.MAX_HISTORY_MESSAGES :]
        total_chars = sum(len(str(item.get("content", ""))) for item in trimmed)
        while len(trimmed) > 1 and total_chars > self.MAX_HISTORY_CHARS:
            removed = trimmed.pop(0)
            total_chars -= len(str(removed.get("content", "")))
        return [system_message] + trimmed

    def _find_skill(self, skills: List[Any], name: str):
        return next((skill for skill in skills if skill.name == name), None)

    def _looks_like_unverified_plan(self, text: str) -> bool:
        lowered = (text or "").strip().lower()
        if not lowered:
            return True
        plan_markers = [
            "i'll ",
            "i will ",
            "i'm going to ",
            "first,",
            "next,",
            "then ",
            "you can now view",
            "the app is now available at",
            "the website is now available at",
            "the dashboard is now open",
        ]
        return any(marker in lowered for marker in plan_markers)

    def _verified_summary(self, outcomes: List[Dict[str, Any]]) -> str:
        if not outcomes:
            return ""
        lines: List[str] = []
        for outcome in outcomes[-6:]:
            name = outcome.get("name", "tool")
            result = outcome.get("result")
            if isinstance(result, dict):
                if result.get("ok") is True:
                    bits = [f"{name}: ok"]
                    if result.get("path"):
                        bits.append(f"path={result['path']}")
                    if result.get("pid"):
                        bits.append(f"pid={result['pid']}")
                    verified_files = result.get("verified_files")
                    if isinstance(verified_files, dict):
                        confirmed = [key for key, value in verified_files.items() if value]
                        if confirmed:
                            bits.append("verified=" + ",".join(confirmed))
                    lines.append(" - ".join(bits))
                elif result.get("ok") is False:
                    bits = [f"{name}: failed"]
                    if result.get("error"):
                        bits.append(str(result["error"]))
                    elif result.get("step"):
                        bits.append(f"step={result['step']}")
                    lines.append(" - ".join(bits))
                else:
                    lines.append(f"{name}: {json.dumps(result, ensure_ascii=False)[:280]}")
            else:
                text = str(result).strip()
                lines.append(f"{name}: {text[:280] if text else 'completed'}")
        return "\n".join(lines)

    def _guess_project_name(self, text: str) -> str:
        lowered = text.lower()
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
                return match.group(1).strip(" .,:;")
        if "ecommerce" in lowered or "e-commerce" in lowered:
            return "ecommerce-store"
        if "html" in lowered and ("landing page" in lowered or "website" in lowered):
            return "html-landing-page"
        if "website" in lowered:
            return "website-app"
        return "react-app"

    def _html_landing_page_content(self, title: str) -> str:
        safe_title = title.replace("-", " ").replace("_", " ").strip().title() or "Landing Page"
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{safe_title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f0e8;
      --panel: #fffaf2;
      --text: #1f1a14;
      --muted: #6c6258;
      --accent: #b85c38;
      --accent-dark: #8e4325;
      --border: #e3d6c6;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Consolas, "Courier New", monospace;
      background: linear-gradient(180deg, var(--bg), #efe4d4);
      color: var(--text);
    }}
    .wrap {{
      max-width: 960px;
      margin: 0 auto;
      padding: 72px 24px;
    }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 48px;
      box-shadow: 0 20px 60px rgba(31, 26, 20, 0.08);
    }}
    .eyebrow {{
      display: inline-block;
      margin-bottom: 16px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(184, 92, 56, 0.12);
      color: var(--accent-dark);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0 0 16px;
      font-size: clamp(2.5rem, 6vw, 4.5rem);
      line-height: 0.95;
    }}
    p {{
      max-width: 52ch;
      font-size: 1rem;
      line-height: 1.7;
      color: var(--muted);
    }}
    .actions {{
      display: flex;
      gap: 12px;
      margin-top: 28px;
      flex-wrap: wrap;
    }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 160px;
      padding: 14px 18px;
      border-radius: 14px;
      text-decoration: none;
      border: 1px solid var(--accent);
      color: white;
      background: var(--accent);
    }}
    .button.secondary {{
      background: transparent;
      color: var(--accent-dark);
      border-color: var(--border);
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <span class="eyebrow">Launch Ready</span>
      <h1>{safe_title}</h1>
      <p>A clean single-file landing page scaffold generated by IMOS. Replace this copy with your product pitch, proof points, and call to action.</p>
      <div class="actions">
        <a class="button" href="#start">Get Started</a>
        <a class="button secondary" href="#learn">Learn More</a>
      </div>
    </section>
  </main>
</body>
</html>
"""

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

    def _infer_direct_tool_call(self, user_text: str, skills: List[Any]) -> Dict[str, Any] | None:
        lowered = (user_text or "").strip().lower()
        if not lowered:
            return None

        wants_build = any(term in lowered for term in ["build", "create", "make", "scaffold"])
        requested_ide = self._guess_ide_target(user_text)
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
        wants_html = any(term in lowered for term in [" html ", "static site", "static website", "plain html", "simple html"]) or lowered.startswith("html ")
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

        if wants_html and wants_build and wants_website and self._find_skill(skills, "write_file"):
            project_name = self._guess_project_name(user_text)
            return {
                "id": "direct-write-html-landing-page",
                "name": "write_file",
                "input": {
                    "path": f"{project_name}/index.html",
                    "content": self._html_landing_page_content(project_name),
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
        anthropic_tool_results = []
        outcomes: List[Dict[str, Any]] = []
        blocked_tools = {"computer_control", "send_email", "open_application", "write_file", "bash", "scaffold_react_app", "scaffold_nextjs", "start_dev_server"}
        for tool_call in tool_calls:
            started = time.perf_counter()
            input_summary = json.dumps(tool_call.get("input", {}), ensure_ascii=False)[:200]
            if self.event_bus is not None:
                self.event_bus.tool_start(tool_call["name"], input_summary, session_id=session_id)
            if self.consent_manager is not None and not self.consent_manager.is_granted() and tool_call["name"] in blocked_tools:
                tool_result = {"ok": False, "error": f"Read-only mode: {tool_call['name']} requires /consent first."}
                duration = round(time.perf_counter() - started, 3)
                if self.event_bus is not None:
                    self.event_bus.tool_end(tool_call["name"], "error", duration, session_id=session_id)
                outcomes.append({"name": tool_call["name"], "input": tool_call.get("input", {}), "result": tool_result})
                continue
            skill = next((item for item in skills if item.name == tool_call["name"]), None)
            if not skill:
                if self.mcp_runtime is not None and self.mcp_runtime.has_tool(tool_call["name"]):
                    try:
                        if self.event_bus is not None:
                            self.event_bus.tool_progress(tool_call["name"], "Calling MCP tool", session_id=session_id)
                        tool_result = self.mcp_runtime.call_tool(tool_call["name"], tool_call.get("input", {}))
                    except Exception as exc:
                        tool_result = {"ok": False, "error": str(exc)}
                else:
                    tool_result = self._missing_skill_message(tool_call["name"])
            else:
                if self.event_bus is not None:
                    self.event_bus.tool_progress(tool_call["name"], "Executing tool", session_id=session_id)
                tool_result = skill.handler(
                    tool_call["input"],
                    workspace=workspace,
                    memory_store=self.memory_store,
                    session_id=session_id,
                    model_config=model_config,
                    shell_runner=self.shell_runner,
                    process_manager=self.process_manager,
                    audit_logger=self.audit_logger,
                )
            duration = round(time.perf_counter() - started, 3)
            status = "ok"
            if isinstance(tool_result, dict) and tool_result.get("ok") is False:
                status = "error"
            if self.event_bus is not None:
                self.event_bus.tool_end(tool_call["name"], status, duration, session_id=session_id)
            if self.session_manager is not None:
                self.session_manager.record_tool_call(
                    session_id,
                    name=tool_call["name"],
                    input_summary=input_summary,
                    status=status,
                    duration=duration,
                    metadata={"input": tool_call.get("input", {})},
                )
            outcomes.append({"name": tool_call["name"], "input": tool_call.get("input", {}), "result": tool_result})
            if self.audit_logger is not None:
                self.audit_logger.append(
                    "tool_result",
                    tool_call["name"],
                    {
                        "session_id": session_id,
                        "input": tool_call.get("input", {}),
                        "result_preview": (tool_result if isinstance(tool_result, str) else json.dumps(tool_result, ensure_ascii=False))[:1000],
                    },
                )
            rendered = tool_result if isinstance(tool_result, str) else json.dumps(tool_result, indent=2, ensure_ascii=False)
            if provider in {"anthropic", "gcp"}:
                anthropic_tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call["id"],
                        "content": rendered,
                    }
                )
            else:
                messages.append({"role": "tool", "content": rendered, "tool_call_id": tool_call["id"]})
        if provider in {"anthropic", "gcp"}:
            messages.append({"role": "user", "content": anthropic_tool_results})
        return outcomes

    def _any_outcome_failed(self, outcomes: List[Dict[str, Any]]) -> bool:
        for outcome in outcomes:
            result = outcome.get("result")
            if isinstance(result, dict) and result.get("ok") is False:
                return True
        return False

    def _outcome_failure_summary(self, outcomes: List[Dict[str, Any]]) -> str:
        lines = []
        for outcome in outcomes[-4:]:
            result = outcome.get("result")
            if isinstance(result, dict) and result.get("ok") is False:
                reason = result.get("error") or result.get("stderr") or result.get("step") or "unknown error"
                lines.append(f"{outcome.get('name')}: {reason}")
        return "\n".join(lines)

    def _run_openai_compat(
        self,
        client,
        model: str,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        on_text_delta: Callable[[str], None] | None = None,
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, int]]:
        import openai

        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=[{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in tools] if tools else None,
                stream=True,
                stream_options={"include_usage": True},
                max_tokens=4096,
            )
        except openai.RateLimitError as exc:
            return f"Quota exceeded for {model}: {exc}", [], {}
        except openai.APIConnectionError as exc:
            return f"Connection error while contacting {model}: {exc}", [], {}
        except openai.APIStatusError as exc:
            return f"API status error from {model}: {exc}", [], {}
        except Exception as exc:
            return f"API error from {model}: {exc}", [], {}
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
                        bucket = tool_calls_raw.setdefault(tc.index, {"id": tc.id or "", "name": "", "arguments": ""})
                        if tc.id:
                            bucket["id"] = tc.id
                        if tc.function and tc.function.name:
                            bucket["name"] += tc.function.name
                        if tc.function and tc.function.arguments:
                            bucket["arguments"] += tc.function.arguments
        except openai.APIConnectionError as exc:
            return f"Connection dropped while streaming from {model}: {exc}", [], {}
        except Exception as exc:
            if tools and ("Failed to call a function" in str(exc) or "failed_generation" in str(exc)):
                return self._run_openai_compat(client, model, messages, [], on_text_delta=on_text_delta)
            return f"Streaming error from {model}: {exc}", [], {}
        tool_calls = []
        for raw in tool_calls_raw.values():
            try:
                arguments = json.loads(raw["arguments"]) if raw["arguments"] else {}
            except Exception:
                arguments = {}
            tool_calls.append({"id": raw["id"], "name": raw["name"], "input": arguments})
        return full_text, tool_calls, usage

    def _run_anthropic(
        self,
        client,
        model: str,
        system_prompt: str,
        history_messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        on_text_delta: Callable[[str], None] | None = None,
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
                messages=[{"role": m["role"], "content": m["content"]} for m in history_messages if m["role"] != "system"],
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
            return f"Anthropic-compatible API error from {model}: {exc}", [], {}
        if getattr(message, "usage", None):
            usage = {
                "input_tokens": int(getattr(message.usage, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(message.usage, "output_tokens", 0) or 0),
            }
        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "input": block.input})
        return final_text, tool_calls, usage

    def _record_usage(self, model: str, usage: Dict[str, int]):
        if not self.cost_tracker or not usage:
            return
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        if input_tokens or output_tokens:
            self.cost_tracker.record(model, input_tokens, output_tokens)

    def run(
        self,
        user_text: str,
        session_history: List[Dict[str, Any]],
        session_id: str,
        workspace: str,
        model_config: dict,
        on_text_delta: Callable[[str], None] | None = None,
        return_meta: bool = False,
    ):
        skills = self.skill_registry.load_all()
        actionable = self._is_actionable_request(user_text)
        tools = [skill.to_tool_definition() for skill in skills] if actionable else []
        if self.mcp_runtime is not None:
            tools.extend(self.mcp_runtime.tool_definitions() if actionable else [])
        plan = self._make_plan(user_text, skills) if actionable else []
        task = self.task_manager.create(user_text, session_id, plan=plan) if self.task_manager and actionable else None
        memory_blocks = self.memory_store.context_blocks(session_id=session_id, query=user_text)
        system_prompt = self._system_prompt(workspace, memory_blocks, skills, model_config)
        messages = self._trim_messages(self._serialize_messages(system_prompt, session_history, user_text))
        direct_tool_call = self._infer_direct_tool_call(user_text, skills) if actionable else None
        if direct_tool_call is not None:
            tool_outcomes = self._execute_tool_calls(
                skills,
                [direct_tool_call],
                "direct",
                messages,
                workspace,
                session_id,
                model_config,
            )
            final_text = self._verified_summary(tool_outcomes)
            if task is not None:
                final_status = "completed"
                if self._any_outcome_failed(tool_outcomes):
                    final_status = "partial_failure"
                self.task_manager.complete(task, final_status, tool_outcomes)
            if return_meta:
                return {"text": final_text, "usage": {}}
            return final_text
        client = get_client(model_config)
        provider = str(model_config.get("provider") or model_config.get("type") or "").strip().lower()
        model = model_config.get("model", "")

        response_text = ""
        forced_tool_retry = False
        tool_outcomes: List[Dict[str, Any]] = []
        repair_attempts = 0
        latest_usage: Dict[str, int] = {}
        for _ in range(8):
            if task is not None:
                task.attempts += 1
                self.task_manager.update(task)
            messages = self._trim_messages(messages)
            if provider in {"anthropic", "gcp"}:
                response_text, tool_calls, usage = self._run_anthropic(client, model, system_prompt, messages, tools, on_text_delta=on_text_delta)
            else:
                response_text, tool_calls, usage = self._run_openai_compat(client, model, messages, tools, on_text_delta=on_text_delta)
            if usage:
                latest_usage = usage
                self._record_usage(model, usage)

            if not tool_calls:
                if actionable:
                    direct_tool_call = self._infer_direct_tool_call(user_text, skills)
                    if direct_tool_call:
                        messages.append({"role": "assistant", "content": response_text})
                        tool_outcomes.extend(self._execute_tool_calls(
                            skills,
                            [direct_tool_call],
                            provider,
                            messages,
                            workspace,
                            session_id,
                            model_config,
                        ))
                        forced_tool_retry = True
                        continue
                if actionable and not forced_tool_retry:
                    messages.append(
                        {
                            "role": "user",
                            "content": "You must now use tools to perform or verify this actionable request. Do not answer with a plan, fake terminal output, or claim work was completed without evidence. Use the available skills, then report only verified results.",
                        }
                    )
                    forced_tool_retry = True
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
                if return_meta:
                    return {"text": response_text, "usage": latest_usage}
                return response_text

            messages.append({"role": "assistant", "content": response_text})
            tool_outcomes.extend(self._execute_tool_calls(
                skills,
                tool_calls,
                provider,
                messages,
                workspace,
                session_id,
                model_config,
            ))
            if self._any_outcome_failed(tool_outcomes) and repair_attempts < 2:
                repair_attempts += 1
                messages.append(
                    {
                        "role": "user",
                        "content": "One or more tool executions failed. Read the real errors below, repair the plan, and retry with tools only.\n" + self._outcome_failure_summary(tool_outcomes),
                    }
                )
                continue
            if actionable:
                messages.append(
                    {
                        "role": "user",
                        "content": "Return a concise completion summary grounded only in the real tool results from this run. Include verified paths, process ids, or concrete failures when available. Do not fabricate extra steps.",
                    }
                )
                continue
        final_text = response_text or self._verified_summary(tool_outcomes)
        if actionable and tool_outcomes:
            if self._looks_like_unverified_plan(response_text):
                final_text = self._verified_summary(tool_outcomes)
        if task is not None:
            final_status = "completed"
            if self._any_outcome_failed(tool_outcomes):
                final_status = "partial_failure"
            self.task_manager.complete(task, final_status, tool_outcomes)
        if return_meta:
            return {"text": final_text, "usage": latest_usage}
        return final_text
