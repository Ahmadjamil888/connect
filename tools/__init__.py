from . import computer_control
from .computer_control import (
    click,
    click_element,
    find_on_screen,
    focus_window,
    hover,
    open_app,
    press_key,
    screenshot,
    scroll,
    type_text,
)
from .whatsapp import send_whatsapp


def computer_control_handler_run(*args, **kwargs):
    from skills.computer_control.handler import run

    return run(*args, **kwargs)


def vibe_coder_handler_run(*args, **kwargs):
    from skills.vibe_coder.handler import run

    return run(*args, **kwargs)


def universal_runtime_handler_run(*args, **kwargs):
    from skills.universal_runtime.handler import run

    return run(*args, **kwargs)

ALL_TOOLS = {
    "computer_control": computer_control_handler_run,
    "vibe_coder": vibe_coder_handler_run,
    "universal_runtime": universal_runtime_handler_run,
    "computer_control.click": click,
    "computer_control.click_element": click_element,
    "computer_control.type_text": type_text,
    "computer_control.screenshot": screenshot,
    "computer_control.open_app": open_app,
    "computer_control.hover": hover,
    "computer_control.press_key": press_key,
    "computer_control.scroll": scroll,
    "computer_control.focus_window": focus_window,
    "computer_control.find_on_screen": find_on_screen,
    "computer_control.run": computer_control_handler_run,
    "send_whatsapp": send_whatsapp,
}

__all__ = [
    "ALL_TOOLS",
    "click",
    "click_element",
    "computer_control",
    "computer_control_handler_run",
    "find_on_screen",
    "focus_window",
    "hover",
    "open_app",
    "press_key",
    "screenshot",
    "scroll",
    "send_whatsapp",
    "type_text",
    "universal_runtime_handler_run",
    "vibe_coder_handler_run",
]
