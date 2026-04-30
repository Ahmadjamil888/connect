from __future__ import annotations

from pathlib import Path

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "content": {"type": "string"},
    },
    "required": ["path", "content"],
}


def run(inputs, *, workspace: str, **_kwargs):
    path = Path(workspace) / str(inputs["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(inputs["content"]), encoding="utf-8")
    return {
        "ok": True,
        "path": str(path),
        "bytes_written": len(str(inputs["content"]).encode("utf-8")),
        "verified": path.exists(),
    }
