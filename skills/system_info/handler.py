from __future__ import annotations

from tools.pc_manager import system_info

TOOL_SCHEMA = {
    "type": "object",
    "properties": {},
}


def run(inputs, **_kwargs):
    return system_info()
