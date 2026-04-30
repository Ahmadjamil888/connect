from __future__ import annotations

TOOL_SCHEMA = {
    "type": "object",
    "properties": {},
}


def run(inputs, **_kwargs):
    process_manager = _kwargs.get("process_manager")
    if process_manager is None:
        return {"ok": False, "error": "Process manager is not available."}
    return {"ok": True, "items": process_manager.list()}
