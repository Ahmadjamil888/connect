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
    path = Path(workspace) / str(inputs["path"])
    return path.read_text(encoding="utf-8", errors="replace")
