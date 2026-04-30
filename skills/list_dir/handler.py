from __future__ import annotations

from pathlib import Path

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
    },
}


def run(inputs, *, workspace: str, **_kwargs):
    root = Path(workspace) / str(inputs.get("path", "."))
    return "\n".join(sorted(item.name for item in root.iterdir()))
