from __future__ import annotations

import tempfile
from pathlib import Path

from tools import computer_control

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "type_text",
                "click",
                "click_element",
                "hover",
                "screenshot",
                "find_on_screen",
                "focus_window",
                "open_app",
                "press_key",
                "scroll",
            ],
        },
        "text": {"type": "string"},
        "x": {"type": "integer"},
        "y": {"type": "integer"},
        "amount": {"type": "integer"},
        "key": {"type": "string"},
        "title": {"type": "string"},
        "name": {"type": "string"},
        "image_path": {"type": "string"},
        "confirm": {"type": "boolean"},
        "sensitive": {"type": "boolean"},
    },
    "required": ["action"],
}


def _root_for_workspace(workspace: str) -> Path:
    preferred = Path(workspace) / ".connectai" / "computer_control"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return preferred
    except Exception:
        fallback = Path(tempfile.gettempdir()) / "connectai" / "computer_control"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _capture(audit_logger, workspace: str, label: str) -> str:
    root = _root_for_workspace(workspace)
    shot = computer_control.screenshot(root)
    if audit_logger is not None:
        audit_logger.append("computer_control_screenshot", label, {"path": shot.get("path", "")})
    return str(shot.get("path", ""))


def run(inputs, *, workspace: str, audit_logger=None, **_kwargs):
    action = str(inputs.get("action", "")).strip().lower()
    if bool(inputs.get("sensitive")) and not bool(inputs.get("confirm", False)):
        return {"ok": False, "error": "Sensitive computer control action requires confirm=true."}

    before = _capture(audit_logger, workspace, f"{action}:before")
    try:
        if action == "type_text":
            result = computer_control.type_text(str(inputs.get("text", "")))
        elif action == "click":
            result = computer_control.click(int(inputs["x"]), int(inputs["y"]))
        elif action == "click_element":
            result = computer_control.click_element(str(inputs["image_path"]))
        elif action == "hover":
            result = computer_control.hover(int(inputs["x"]), int(inputs["y"]))
        elif action == "screenshot":
            result = computer_control.screenshot(_root_for_workspace(workspace))
        elif action == "find_on_screen":
            result = computer_control.find_on_screen(str(inputs["image_path"]))
        elif action == "focus_window":
            result = computer_control.focus_window(str(inputs["title"]))
        elif action == "open_app":
            result = computer_control.open_app(str(inputs["name"]))
        elif action == "press_key":
            result = computer_control.press_key(str(inputs["key"]))
        elif action == "scroll":
            result = computer_control.scroll(inputs.get("x"), inputs.get("y"), int(inputs.get("amount", 0)))
        else:
            result = {"ok": False, "error": f"Unknown action: {action}"}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    after = _capture(audit_logger, workspace, f"{action}:after")
    if isinstance(result, dict):
        result.setdefault("before_screenshot", before)
        result.setdefault("after_screenshot", after)
    if audit_logger is not None:
        audit_logger.append("computer_control_action", action, {"inputs": inputs, "result": result})
    return result
