from __future__ import annotations

import json
from pathlib import Path

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["add", "list", "complete", "delete"]},
        "task": {"type": "string"},
        "index": {"type": "integer"},
    },
    "required": ["action"],
}


def _todo_path(workspace: str) -> Path:
    path = Path(workspace) / "data" / "todos.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]", encoding="utf-8")
    return path


def _load(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save(path: Path, items: list[dict]) -> None:
    path.write_text(json.dumps(items, indent=2), encoding="utf-8")


def run(inputs, *, workspace: str, **_kwargs):
    path = _todo_path(workspace)
    items = _load(path)
    action = str(inputs.get("action", "")).strip().lower()

    if action == "add":
        task = str(inputs.get("task", "")).strip()
        if not task:
            return {"ok": False, "error": "task is required for add"}
        items.append({"task": task, "done": False})
        _save(path, items)
        return {"ok": True, "count": len(items), "task": task}
    if action == "list":
        return {"ok": True, "items": items, "count": len(items), "path": str(path)}
    if action in {"complete", "delete"}:
        index = int(inputs.get("index", 0) or 0) - 1
        if index < 0 or index >= len(items):
            return {"ok": False, "error": "Task not found."}
        if action == "complete":
            items[index]["done"] = True
            _save(path, items)
            return {"ok": True, "completed": items[index]}
        removed = items.pop(index)
        _save(path, items)
        return {"ok": True, "deleted": removed}
    return {"ok": False, "error": f"Unknown action: {action}"}
