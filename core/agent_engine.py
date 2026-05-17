from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


SYSTEM_PROMPT = """
ABSOLUTE RULES:
1. NEVER report success for a tool you haven't called.
2. NEVER fabricate URLs, file paths, deploy links, or output.
3. If a tool returns error, report it honestly and propose recovery.
4. If you lack a tool for something, say exactly: "I cannot do X - I need a tool for that."
5. Always show PROOF: real paths, real terminal output, real URLs from tool results.
"""


class ConsentManager:
    def __init__(self) -> None:
        self.blanket_grants: set[str] = set()

    def request(self, scope: str, description: str) -> bool:
        if scope in self.blanket_grants:
            return True
        print(f"[consent] {scope}: {description}")
        answer = input("[y] allow once, [a] allow for session, [n] deny: ").strip().lower()
        if answer == "a":
            self.blanket_grants.add(scope)
            return True
        return answer == "y"


class AuditLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (Path.home() / ".connect" / "audit.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, tool: str, args: dict[str, Any], status: str, summary: str) -> None:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "args": args,
            "status": status,
            "summary": summary,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def tail(self, count: int = 20) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-count:]
        rows: list[dict[str, Any]] = []
        for line in lines:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows


@dataclass
class AgentEngine:
    registry: Any
    consent: ConsentManager = field(default_factory=ConsentManager)
    audit: AuditLog = field(default_factory=AuditLog)
    history: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        load_dotenv()

    def _openai_client(self):
        from openai import OpenAI

        if os.getenv("OPENAI_API_KEY"):
            return OpenAI(api_key=os.getenv("OPENAI_API_KEY")), os.getenv("OPENAI_MODEL", "gpt-4o")
        if os.getenv("GROQ_API_KEY"):
            return OpenAI(api_key=os.getenv("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1"), os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        return None, None

    def _anthropic_client(self):
        if not os.getenv("ANTHROPIC_API_KEY"):
            return None, None
        import anthropic

        return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")), os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

    def _normalize_tool_result(self, result: Any) -> dict[str, Any]:
        if isinstance(result, dict) and "status" in result:
            return result
        return {"status": "error", "error": f"Tool returned invalid result: {result!r}"}

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        meta = self.registry.get(name)
        if meta is None:
            result = {"status": "error", "error": f"Unknown tool: {name}"}
            self.audit.append(name, arguments, result["status"], result["error"])
            return result
        scope = meta["consent_scope"]
        if scope and not self.consent.request(scope, meta["description"]):
            result = {"status": "error", "error": f"Consent denied for scope: {scope}"}
            self.audit.append(name, arguments, result["status"], result["error"])
            return result
        raw = meta["fn"](**arguments)
        result = self._normalize_tool_result(raw)
        summary = result.get("error") or result.get("path") or result.get("url") or result.get("deploy_url") or result.get("current_url") or result.get("stdout", "")[:200] or result.get("content", "")[:200] or result["status"]
        self.audit.append(name, arguments, result["status"], str(summary))
        return result

    def _chat_openai(self, prompt: str) -> str:
        client, model = self._openai_client()
        if client is None:
            raise RuntimeError("No OpenAI-compatible provider configured")
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *self.history, {"role": "user", "content": prompt}]
        tools = self.registry.tool_schemas()
        for _ in range(8):
            response = client.chat.completions.create(model=model, messages=messages, tools=tools)
            choice = response.choices[0].message
            if choice.tool_calls:
                messages.append({"role": "assistant", "content": choice.content or "", "tool_calls": choice.tool_calls})
                for call in choice.tool_calls:
                    args = json.loads(call.function.arguments or "{}")
                    result = self._execute_tool(call.function.name, args)
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, ensure_ascii=False)})
                continue
            final = str(choice.content or "").strip()
            self.history.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": final}])
            return final
        raise RuntimeError("Tool loop exceeded maximum iterations")

    def _chat_anthropic(self, prompt: str) -> str:
        client, model = self._anthropic_client()
        if client is None:
            raise RuntimeError("No Anthropic provider configured")
        messages: list[dict[str, Any]] = []
        for item in self.history:
            messages.append({"role": item["role"], "content": item["content"]})
        messages.append({"role": "user", "content": prompt})
        tools = self.registry.anthropic_tool_schemas()
        for _ in range(8):
            response = client.messages.create(model=model, system=SYSTEM_PROMPT, max_tokens=2000, messages=messages, tools=tools)
            tool_blocks = [block for block in response.content if getattr(block, "type", "") == "tool_use"]
            if tool_blocks:
                assistant_content: list[dict[str, Any]] = []
                for block in response.content:
                    if getattr(block, "type", "") == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                    elif getattr(block, "type", "") == "tool_use":
                        assistant_content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
                messages.append({"role": "assistant", "content": assistant_content})
                user_content: list[dict[str, Any]] = []
                for block in tool_blocks:
                    result = self._execute_tool(block.name, block.input or {})
                    user_content.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, ensure_ascii=False)})
                messages.append({"role": "user", "content": user_content})
                continue
            parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
            final = "\n".join(parts).strip()
            self.history.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": final}])
            return final
        raise RuntimeError("Tool loop exceeded maximum iterations")

    def ask(self, prompt: str) -> str:
        try:
            if os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY"):
                return self._chat_openai(prompt)
            if os.getenv("ANTHROPIC_API_KEY"):
                return self._chat_anthropic(prompt)
            return "No LLM provider configured. Set OPENAI_API_KEY, GROQ_API_KEY, or ANTHROPIC_API_KEY in your environment."
        except Exception as exc:
            return f"Agent error: {exc}"
