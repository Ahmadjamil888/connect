from __future__ import annotations

from tools.pc_manager import open_application

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "name_or_path": {"type": "string"},
    },
    "required": ["name_or_path"],
}


def run(inputs, **_kwargs):
    return open_application(str(inputs["name_or_path"]))
