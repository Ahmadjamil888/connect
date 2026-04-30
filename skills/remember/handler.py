from __future__ import annotations

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "note": {"type": "string"},
        "kind": {"type": "string"},
    },
    "required": ["note"],
}


def run(inputs, *, memory_store, session_id: str, **_kwargs):
    note = str(inputs["note"])
    kind = str(inputs.get("kind", "memory"))
    memory_store.remember(note, kind=kind, session_id=session_id)
    return f"Remembered: {note}"
