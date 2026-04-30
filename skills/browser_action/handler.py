from __future__ import annotations

from browser.controller import run_browser

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["navigate", "click", "type", "fill", "screenshot", "get_html", "get_text", "execute_js", "console_errors", "page_info", "close"],
        },
        "url": {"type": "string"},
        "selector": {"type": "string"},
        "text": {"type": "string"},
        "script": {"type": "string"},
        "headless": {"type": "boolean"},
    },
    "required": ["action"],
}


def run(inputs, *, workspace: str, **_kwargs):
    payload = dict(inputs)
    payload.setdefault("workspace", workspace)
    return run_browser(payload)
