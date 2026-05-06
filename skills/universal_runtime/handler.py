from __future__ import annotations

from typing import Any

from core.ai_tool_driver import ai_tool
from core.browser_driver import browser
from core.runtime_session import runtime_session
from core.social_driver import social
from tools.computer_control import open_app, screenshot

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "tool": {"type": "string"},
        "prompt": {"type": "string"},
        "url": {"type": "string"},
        "platform": {"type": "string"},
        "contact": {"type": "string"},
        "message": {"type": "string"},
        "text": {"type": "string"},
        "image_path": {"type": "string"},
    },
    "required": ["action"],
}


def run(inputs, *, workspace: str, **_kwargs):
    action = str(inputs.get("action", "")).strip().lower()
    runtime_session.log_operation(action or "runtime", {"inputs": dict(inputs)})
    if action == "ai_tool":
        tool_name = str(inputs.get("tool", "")).strip()
        prompt = str(inputs.get("prompt", "")).strip()
        opened = ai_tool.open_tool(tool_name)
        if not opened.get("ok"):
            result = opened
        elif prompt:
            result = ai_tool.send_prompt(prompt)
        else:
            result = {"ok": True, "tool": tool_name}
    elif action == "browser_open":
        result = browser.open_url(str(inputs.get("url", "")).strip())
    elif action == "browser_scroll":
        result = browser.scroll_down()
    elif action == "browser_back":
        result = browser.go_back()
    elif action == "browser_close_tab":
        result = browser.close_tab()
    elif action == "message":
        result = social.send_message(
            str(inputs.get("platform", "")).strip() or "whatsapp",
            str(inputs.get("contact", "")).strip(),
            str(inputs.get("message", "")).strip(),
        )
    elif action == "post":
        result = social.post_content(
            str(inputs.get("platform", "")).strip(),
            str(inputs.get("text", "")).strip(),
            str(inputs.get("image_path", "")).strip() or None,
        )
    elif action == "open_app":
        result = open_app(str(inputs.get("tool", "")).strip())
    elif action == "screenshot":
        result = screenshot()
    else:
        result = {"ok": False, "error": f"Unknown universal runtime action: {action}"}
    runtime_session.complete_operation(action or "runtime", {"result": result})
    return result
