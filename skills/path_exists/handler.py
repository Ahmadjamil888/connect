from __future__ import annotations

from pathlib import Path

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
    },
    "required": ["path"],
}


def run(inputs, *, workspace: str, **_kwargs):
    path = (Path(workspace) / str(inputs["path"])).resolve()
    exists = path.exists()
    payload = {
        "ok": exists,
        "path": str(path),
        "exists": exists,
        "is_file": path.is_file() if exists else False,
        "is_dir": path.is_dir() if exists else False,
    }
    if exists and path.is_file():
        payload["size"] = path.stat().st_size
    return payload
