"""Unified IMOS operator runtime: thinking, service detection, and tool dispatch."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Any, Callable

THINK_SYSTEM_PROMPT = """You are the IMOS operator reasoning layer — the coordination brain of an intelligent machine operating system.
IMOS unifies models, IDEs, terminals, browser automation, apps, and local execution in one persistent runtime with shared memory, routing, permissions, and auditability.
Analyze the user message and decide how one runtime should handle it across browser, desktop, files, apps, and AI agents (Cursor, Codex, Claude Code, configured cloud models).

Output only valid JSON:
{
  "mode": "chat|execute",
  "analysis": "one paragraph of operator reasoning",
  "reasoning_steps": ["short step 1", "short step 2"],
  "agents": ["auto"],
  "services": ["browser", "desktop", "filesystem", "ide"],
  "reply": "direct reply if mode is chat, else empty string"
}

Use mode execute when the user wants building, opening, clicking, typing, dragging, deleting, rewriting files, automating apps, or running code.
Use agents auto unless they named a specific agent. Prefer real execution over explanation when action is implied.
"""

PLANNER_TOOLS_DOC = """
Available tools:
- run_shell: {command, directory?}
- open_url: {url, instruction?}
- open_app: {app: cursor|vscode|terminal}
- write_file, append_file, read_file, rewrite_file, delete_file, list_dir, make_dir
- http_request: {method, url, headers?, body?, save_to?}
- browser: {action: navigate|click|type|scroll|read|screenshot|drag|press, url?, selector?, text?, x?, y?, x2?, y2?, key?, path?}
- desktop: {action: click|type|drag|hotkey|screenshot|open_app, x?, y?, x1?, y1?, x2?, y2?, text?, keys?, name?}
- ai_agent: {prompt, agent?: auto|claude|codex|cursor|configured, directory?}
- transfer_context: {target: lovable|cursor|claude|chatgpt|codex|generic}
- lovable: {prompt}
- scaffold_saas: {description, project_name}
"""


def list_connected_services() -> list[dict[str, Any]]:
    """Full catalog with availability flags (delegates to services_catalog)."""
    from core.services_catalog import list_all_services

    return list_all_services()


def pick_agent_order(prompt: str, agent: str = "auto") -> list[str]:
    agent = (agent or "auto").strip().lower()
    if agent != "auto":
        return [agent]
    lowered = prompt.lower()
    if any(k in lowered for k in ("codex", "openai cli")):
        return ["codex", "claude", "cursor", "configured"]
    if any(k in lowered for k in ("cursor", "composer", "ide")):
        return ["cursor", "codex", "claude", "configured"]
    if any(k in lowered for k in ("claude code", "claude")):
        return ["claude", "codex", "cursor", "configured"]
    if any(k in lowered for k in ("implement", "refactor", "fix bug", "build", "scaffold", "saas", "app")):
        return ["cursor", "codex", "claude", "configured"]
    return ["configured", "claude", "codex", "cursor"]


def run_ai_agent(prompt: str, project_path: str, agent: str = "auto") -> dict[str, Any]:
    from tools import agent_bridges
    from tools import external_ai_tools

    directory = str(Path(project_path).expanduser().resolve())
    last_error = ""
    for name in pick_agent_order(prompt, agent):
        try:
            if name == "claude":
                outcome = external_ai_tools.run_claude_code(directory, prompt)
                if outcome.get("status") == "success":
                    return {"status": "ok", "agent": "claude", "output": outcome.get("stdout", "")}
                last_error = outcome.get("stderr") or outcome.get("error", "")
            elif name == "codex":
                outcome = external_ai_tools.run_codex(directory, prompt)
                if outcome.get("status") == "success":
                    return {"status": "ok", "agent": "codex", "output": outcome.get("stdout", "")}
                last_error = outcome.get("stderr") or outcome.get("error", "")
            elif name == "cursor":
                agent_bridges.open_cursor_workspace(directory)
                outcome = agent_bridges.chat_with_claude_code(prompt, directory)
                if outcome.get("success"):
                    return {
                        "status": "ok",
                        "agent": "cursor",
                        "output": outcome.get("output") or outcome.get("reply", ""),
                        "fallback_used": outcome.get("fallback_used"),
                    }
                last_error = outcome.get("error", "")
            elif name == "configured":
                outcome = agent_bridges.chat_with_configured_model(prompt)
                if outcome.get("success"):
                    return {"status": "ok", "agent": "configured", "output": outcome.get("reply", "")}
                last_error = outcome.get("error", "")
        except Exception as exc:
            last_error = str(exc)
    return {"status": "failed", "error": last_error or "no AI agent available"}


def think(
    user_message: str,
    get_response: Callable[..., str],
    export_messages: Callable[[], list[dict]],
) -> dict[str, Any]:
    messages = list(export_messages()) + [{"role": "user", "content": user_message}]
    raw = get_response(messages=messages, system=THINK_SYSTEM_PROMPT)
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        data = json.loads(raw[start : end + 1])
    except Exception:
        data = {
            "mode": "execute",
            "analysis": user_message,
            "reasoning_steps": ["Parse request", "Plan tools", "Execute with session context"],
            "agents": ["auto"],
            "services": ["browser", "desktop", "filesystem"],
            "reply": "",
        }
    mode = str(data.get("mode", "execute")).strip().lower()
    if mode not in {"chat", "execute"}:
        mode = "execute"
    data["mode"] = mode
    data.setdefault("analysis", "")
    data.setdefault("reasoning_steps", [])
    data.setdefault("agents", ["auto"])
    data.setdefault("services", [])
    data.setdefault("reply", "")
    return data


def _browser_action(params: dict) -> dict[str, Any]:
    from tools import browser as browser_tools

    action = str(params.get("action", "navigate")).strip().lower()
    if action == "navigate":
        return browser_tools.navigate(params["url"])
    if action == "click":
        return browser_tools.click_element(
            selector=params.get("selector"),
            text=params.get("text"),
            x=params.get("x"),
            y=params.get("y"),
        )
    if action in {"type", "fill"}:
        return browser_tools.type_into(
            selector=params.get("selector"),
            text_label=params.get("text_label"),
            value=params.get("text", ""),
        )
    if action == "scroll":
        return browser_tools.scroll(params.get("direction", "down"), int(params.get("amount", 500)))
    if action in {"read", "get_text"}:
        return browser_tools.get_page_text()
    if action == "screenshot":
        return browser_tools.get_page_screenshot_b64()
    if action == "drag":
        return browser_tools.drag(int(params["x1"]), int(params["y1"]), int(params["x2"]), int(params["y2"]))
    if action == "press":
        return browser_tools.press_key(params.get("key", "Enter"))
    return {"ok": False, "error": f"unsupported browser action: {action}"}


def _desktop_action(params: dict) -> dict[str, Any]:
    from tools import computer_control
    from tools import screen_control

    action = str(params.get("action", "")).strip().lower()
    if action == "click":
        return computer_control.click(int(params["x"]), int(params["y"]))
    if action == "type":
        return computer_control.type_text(str(params.get("text", "")))
    if action == "drag":
        screen_control.drag(int(params["x1"]), int(params["y1"]), int(params["x2"]), int(params["y2"]))
        return {"ok": True, "result": "dragged"}
    if action in {"hotkey", "press"}:
        keys = params.get("keys") or params.get("key", "")
        computer_control.press_key(str(keys))
        return {"ok": True, "keys": keys}
    if action == "screenshot":
        return computer_control.screenshot(params.get("path"))
    if action == "open_app":
        return computer_control.open_app(str(params.get("name", "")))
    return {"ok": False, "error": f"unsupported desktop action: {action}"}


def run_operator_tool(
    tool: str,
    params: dict,
    *,
    project_root: Path,
    legacy_browser: Any,
    current_provider: str,
    current_model: str,
    execute_legacy: Callable[[dict], dict],
) -> dict[str, Any]:
    """Dispatch unified operator tools; fall back to legacy execute_tool for core tools."""

    if tool == "browser":
        outcome = _browser_action(params or {})
        ok = outcome.get("ok", False)
        return {"status": "ok" if ok else "failed", "tool": tool, "result": json.dumps(outcome)[:600]}

    if tool == "desktop":
        outcome = _desktop_action(params or {})
        ok = outcome.get("ok", outcome.get("status") == "success")
        return {"status": "ok" if ok else "failed", "tool": tool, "result": json.dumps(outcome)[:600]}

    if tool == "ai_agent":
        prompt = str(params.get("prompt", "")).strip()
        directory = params.get("directory", ".")
        agent = str(params.get("agent", "auto")).strip().lower()
        outcome = run_ai_agent(prompt, str(project_root / directory) if directory != "." else str(project_root), agent)
        status = "ok" if outcome.get("status") == "ok" else "failed"
        text = outcome.get("output") or outcome.get("error", "")
        return {"status": status, "tool": tool, "result": f"[{outcome.get('agent', agent)}] {text[:500]}"}

    if tool == "rewrite_file":
        destination = (project_root / params["path"]).resolve()
        os.makedirs(destination.parent, exist_ok=True)
        with open(destination, "w", encoding="utf-8") as handle:
            handle.write(params["content"])
        return {"status": "ok", "tool": tool, "result": f"Rewrote file: {destination}"}

    if tool == "delete_file":
        target = (project_root / params["path"]).resolve()
        if target.is_dir():
            import shutil as sh

            sh.rmtree(target)
        elif target.exists():
            target.unlink()
        return {"status": "ok", "tool": tool, "result": f"Deleted: {target}"}

    if tool == "open_service":
        service = str(params.get("service", "")).strip().lower()
        urls = {
            "lovable": "https://lovable.dev",
            "cursor": "cursor://",
            "github": "https://github.com",
            "chatgpt": "https://chat.openai.com",
            "claude": "https://claude.ai",
        }
        url = urls.get(service) or params.get("url", "")
        if url.startswith("cursor"):
            from tools.ide_tools import open_cursor

            open_cursor(str(project_root))
            return {"status": "ok", "tool": tool, "result": "Opened Cursor"}
        webbrowser.open(url)
        return {"status": "ok", "tool": tool, "result": f"Opened service {service}: {url}"}

    return execute_legacy({"tool": tool, "params": params or {}})
