from __future__ import annotations

from tools.pc_manager import clean_temp

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "confirm": {"type": "boolean"},
    },
}


def run(inputs, **_kwargs):
    return clean_temp(confirm=bool(inputs.get("confirm", False)))
