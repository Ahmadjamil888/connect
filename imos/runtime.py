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

IMOS_SYSTEM_PROMPT_BASE = """You are IMOS (Intelligent Machine Operating System), an AI system running on this Windows PC.

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

WHEN BUILDING APPS:
- Use scaffold_nextjs skill for full Next.js projects with DB + deploy
- Use scaffold_react_app for simple React/Vite apps
- Use bash skill to run any shell command
- Use github_push skill to push to GitHub
- Use deploy_vercel or deploy_netlify to deploy
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

    def _system_prompt(self, workspace: str, memory_blocks: List[str], skills: List[Any]) -> str:
        skill_lines = [f"- {s.name}: {s.description}" for s in skills]
        if self.mcp_runtime is not None:
            for tool in self.mcp_runtime.list_tools():
                skill_lines.append(f"- {tool['name']}: {tool['description']} (MCP:{tool['server']})")
        sections = [
            IMOS_SYSTEM_PROMPT_BASE,
            f"Workspace: {workspace}",
            "Available tools:\n" + "\n".join(skill_lines),
        ]
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
        tools = [s.to_tool_definition() for s in skills]
        if self.mcp_runtime is not None:
            tools.extend(self.mcp_runtime.tool_definitions())

        memory_blocks = self.memory_store.context_blocks(session_id=session_id, query=user_text)
        system_prompt = self._system_prompt(workspace, memory_blocks, skills)
        messages = self._trim_messages(
            self._serialize_messages(system_prompt, session_history, user_text)
        )

        client = get_client(model_config)
        provider = model_config.get("provider", "anthropic")
        model = model_config.get("model", "")

        # Task tracking
        task = None
        if self.task_manager and self._is_actionable(user_text):
            task = self.task_manager.create(user_text, session_id)

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
                # No tool calls — push for action if request is actionable
                if self._is_actionable(user_text) and not forced_retry:
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

                # Final answer
                if task is not None:
                    status = "partial_failure" if self._any_failed(tool_outcomes) else "completed"
                    self.task_manager.complete(task, status, tool_outcomes)

                final = response_text
                if self._is_actionable(user_text) and tool_outcomes and self._looks_like_unverified_plan(response_text):
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
            if self._is_actionable(user_text):
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
        if self._is_actionable(user_text) and tool_outcomes and self._looks_like_unverified_plan(response_text):
            final_text = self._verified_summary(tool_outcomes)

        if task is not None:
            status = "partial_failure" if self._any_failed(tool_outcomes) else "completed"
            self.task_manager.complete(task, status, tool_outcomes)

        if return_meta:
            return {"text": final_text, "usage": latest_usage}
        return final_text
