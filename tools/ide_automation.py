from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from core.ai_tool_driver import ai_tool
from core.runtime_session import runtime_session
from tools import agent_bridges
from tools.computer_control import focus_window, press_key


GUI_IDE_TARGETS = {"cursor", "windsurf", "vscode", "zed"}
CLI_AGENT_TARGETS = {
    "claude-code": ("claude", "@anthropic-ai/claude-code"),
    "codex": ("codex", "codex"),
    "aider": ("aider", "aider"),
}


def _workspace_root(workspace: str, project_name: str, project_path: str = "") -> Path:
    if project_path:
        target = Path(project_path)
        return target if target.is_absolute() else Path(workspace) / target
    safe_project = project_name.strip() or "ai-project"
    return Path(workspace) / safe_project


def _launch_gui_target(target: str, project_root: Path) -> dict[str, Any]:
    if target == "cursor":
        return agent_bridges.open_cursor_workspace(project_root)
    if target == "vscode":
        return agent_bridges.open_workspace_in_app("code", project_root, install_hint="Visual Studio Code")
    if target == "windsurf":
        return agent_bridges.open_ide_with_fallback(project_root, prompt="")
    if target == "zed":
        return agent_bridges.open_workspace_in_app("zed", project_root, install_hint="Zed")
    return agent_bridges.open_best_ide(project_root, prompt="")


def _focus_for_target(target: str) -> dict[str, Any]:
    titles = {
        "cursor": ["Cursor"],
        "windsurf": ["Windsurf"],
        "vscode": ["Visual Studio Code", "Code"],
        "zed": ["Zed"],
    }.get(target, [target])
    for title in titles:
        result = focus_window(title)
        if result.get("ok"):
            return result
    return {"ok": False, "error": f"Window not found for {target}"}


def _submit_gui_prompt(target: str, prompt: str, wait_for_response: bool) -> dict[str, Any]:
    def api_fallback(reason: str) -> dict[str, Any]:
        fallback = agent_bridges.chat_with_configured_model(prompt)
        if fallback.get("success"):
            if wait_for_response:
                runtime_session.update_state(active_url=f"{target}://api-fallback")
            return {
                "ok": True,
                "response": fallback.get("reply", ""),
                "mode": "api-fallback",
                "provider": fallback.get("provider", ""),
                "model": fallback.get("model", ""),
                "fallback_reason": reason,
            }
        return {"ok": False, "error": f"{reason}. API fallback unavailable: {fallback.get('error', 'unknown error')}"}

    try:
        focus_result = _focus_for_target(target)
    except Exception as exc:
        return api_fallback(f"GUI focus automation unavailable for {target}: {exc}")
    if not focus_result.get("ok"):
        return api_fallback(focus_result.get("error", f"Window not found for {target}"))

    time.sleep(1.0)
    # Try a few common chat panel shortcuts before using vision to type into the prompt field.
    for shortcut in ("ctrl+l", "ctrl+i"):
        try:
            press_key(shortcut)
            time.sleep(0.2)
        except Exception:
            pass
    try:
        result = ai_tool.send_prompt(prompt, wait_for_response=wait_for_response)
    except Exception as exc:
        return api_fallback(f"GUI prompt automation failed for {target}: {exc}")
    if wait_for_response and result.get("ok"):
        runtime_session.update_state(active_url=f"{target}://chat")
        result["mode"] = "gui"
        return result
    if result.get("ok"):
        result["mode"] = "gui"
        return result
    return api_fallback(result.get("error", f"Could not send prompt to {target}"))


def start_ide_session(
    *,
    target: str,
    workspace: str,
    prompt: str,
    project_name: str = "",
    project_path: str = "",
    wait_for_response: bool = True,
) -> dict[str, Any]:
    normalized_target = (target or "cursor").strip().lower()
    root = _workspace_root(workspace, project_name, project_path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    runtime_session.update_state(active_tool=normalized_target, active_project=root.name)
    runtime_session.log_operation(
        "ide_orchestrator",
        {"target": normalized_target, "project_root": str(root), "prompt": prompt},
    )

    if normalized_target in CLI_AGENT_TARGETS:
        command_name, install_hint = CLI_AGENT_TARGETS[normalized_target]
        result = agent_bridges.run_cli_agent(command_name, prompt, project_path=str(root), install_hint=install_hint)
        payload = {
            "ok": bool(result.get("success")),
            "target": normalized_target,
            "project_root": str(root),
            "response": result.get("output", "") or result.get("reply", ""),
            "error": result.get("error", ""),
            "mode": "cli",
        }
        runtime_session.complete_operation("ide_orchestrator", payload)
        return payload

    launch_result = _launch_gui_target(normalized_target, root)
    if not launch_result.get("success"):
        payload = {
            "ok": False,
            "target": normalized_target,
            "project_root": str(root),
            "error": launch_result.get("error", f"Could not launch {normalized_target}."),
            "launcher": launch_result.get("launcher", ""),
            "searched": launch_result.get("searched", []),
        }
        runtime_session.complete_operation("ide_orchestrator", payload)
        return payload

    if launch_result.get("launcher") == "browser fallback":
        payload = {
            "ok": True,
            "target": normalized_target,
            "project_root": str(root),
            "urls": launch_result.get("urls", []),
            "prompt": launch_result.get("prompt", prompt),
            "mode": "browser",
            "fallback_used": True,
        }
        runtime_session.complete_operation("ide_orchestrator", payload)
        return payload

    time.sleep(2.0)
    response = _submit_gui_prompt(normalized_target, prompt, wait_for_response)
    payload = {
        "ok": bool(response.get("ok")),
        "target": normalized_target,
        "project_root": str(root),
        "pid": launch_result.get("pid"),
        "command": launch_result.get("command", ""),
        "response": response.get("response", ""),
        "error": response.get("error", ""),
        "mode": response.get("mode", "gui"),
        "provider": response.get("provider", ""),
        "model": response.get("model", ""),
        "fallback_reason": response.get("fallback_reason", ""),
    }
    runtime_session.complete_operation("ide_orchestrator", payload)
    return payload


def continue_ide_session(*, target: str, prompt: str, wait_for_response: bool = True) -> dict[str, Any]:
    normalized_target = (target or runtime_session.active_tool or "cursor").strip().lower()
    runtime_session.log_operation("ide_orchestrator_continue", {"target": normalized_target, "prompt": prompt})
    if normalized_target in CLI_AGENT_TARGETS:
        command_name, install_hint = CLI_AGENT_TARGETS[normalized_target]
        active_project = str(runtime_session.active_project or "").strip()
        project_root = (Path.cwd() / active_project).resolve() if active_project else Path.cwd().resolve()
        result = agent_bridges.run_cli_agent(command_name, prompt, project_path=str(project_root), install_hint=install_hint)
        payload = {
            "ok": bool(result.get("success")),
            "target": normalized_target,
            "response": result.get("output", "") or result.get("reply", ""),
            "error": result.get("error", ""),
            "mode": "cli" if not result.get("fallback_used") else "api-fallback",
            "provider": result.get("provider", ""),
            "model": result.get("model", ""),
            "fallback_reason": result.get("fallback_reason", ""),
        }
        runtime_session.complete_operation("ide_orchestrator_continue", payload)
        return payload
    response = _submit_gui_prompt(normalized_target, prompt, wait_for_response)
    payload = {
        "ok": bool(response.get("ok")),
        "target": normalized_target,
        "response": response.get("response", ""),
        "error": response.get("error", ""),
        "mode": response.get("mode", "gui"),
        "provider": response.get("provider", ""),
        "model": response.get("model", ""),
        "fallback_reason": response.get("fallback_reason", ""),
    }
    runtime_session.complete_operation("ide_orchestrator_continue", payload)
    return payload
