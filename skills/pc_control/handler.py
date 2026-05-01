from __future__ import annotations

import os
import shutil
from pathlib import Path

from tools.pc_manager import clean_temp, kill_process, list_processes, open_application, system_info
from tools.screen_control import click_at, drag, scroll as screen_scroll, shortcut, type_text

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "click",
                "type_text",
                "hotkey",
                "scroll",
                "drag",
                "open_app",
                "close_app",
                "list_apps",
                "open_file",
                "move_file",
                "delete_file",
                "clean_temp_files",
                "system_info",
            ],
        },
        "x": {"type": "integer"},
        "y": {"type": "integer"},
        "x2": {"type": "integer"},
        "y2": {"type": "integer"},
        "text": {"type": "string"},
        "keys": {"type": "string"},
        "direction": {"type": "string"},
        "amount": {"type": "integer"},
        "name_or_path": {"type": "string"},
        "path": {"type": "string"},
        "src": {"type": "string"},
        "dst": {"type": "string"},
        "name": {"type": "string"},
        "pid": {"type": "integer"},
        "confirm": {"type": "boolean"},
    },
    "required": ["action"],
}


def _workspace_path(workspace: str, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return Path(workspace) / candidate


def run(inputs, *, workspace: str, **_kwargs):
    action = str(inputs.get("action", "")).strip().lower()

    if action == "click":
        return {"ok": True, "result": click_at(int(inputs["x"]), int(inputs["y"]))}
    if action == "type_text":
        return {"ok": True, "result": type_text(str(inputs.get("text", "")))}
    if action == "hotkey":
        return {"ok": True, "result": shortcut(str(inputs["keys"]))}
    if action == "scroll":
        direction = str(inputs.get("direction", "up"))
        amount = int(inputs.get("amount", 500) or 500)
        return {"ok": True, "result": screen_scroll(direction, amount)}
    if action == "drag":
        return {
            "ok": True,
            "result": drag(int(inputs["x"]), int(inputs["y"]), int(inputs["x2"]), int(inputs["y2"])),
        }
    if action == "open_app":
        return {"ok": True, "result": open_application(str(inputs["name_or_path"]))}
    if action == "close_app":
        return {"ok": True, "result": kill_process(name=str(inputs.get("name", "")) or None, pid=inputs.get("pid"))}
    if action == "list_apps":
        return {"ok": True, "processes": list_processes(str(inputs.get("name", "")).strip() or None)}
    if action == "open_file":
        path = _workspace_path(workspace, str(inputs["path"]))
        os.startfile(str(path))  # type: ignore[attr-defined]
        return {"ok": True, "path": str(path), "result": f"Opened {path}"}
    if action == "move_file":
        src = _workspace_path(workspace, str(inputs["src"]))
        dst = _workspace_path(workspace, str(inputs["dst"]))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return {"ok": True, "src": str(src), "dst": str(dst), "result": f"Moved {src} to {dst}"}
    if action == "delete_file":
        if not bool(inputs.get("confirm", False)):
            return {"ok": False, "error": "Refusing to delete without confirm=true."}
        path = _workspace_path(workspace, str(inputs["path"]))
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return {"ok": True, "path": str(path), "result": f"Deleted {path}"}
    if action == "clean_temp_files":
        return {"ok": True, "result": clean_temp(confirm=bool(inputs.get("confirm", False)))}
    if action == "system_info":
        return {"ok": True, "stats": system_info()}
    return {"ok": False, "error": f"Unknown action: {action}"}
