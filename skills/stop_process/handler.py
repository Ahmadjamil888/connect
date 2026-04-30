from __future__ import annotations

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "process_id": {"type": "string"},
    },
    "required": ["process_id"],
}


def run(inputs, **_kwargs):
    process_manager = _kwargs.get("process_manager")
    if process_manager is None:
        return {"ok": False, "error": "Process manager is not available."}
    return process_manager.stop(str(inputs["process_id"]).strip())
