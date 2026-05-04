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

from skills.computer_control.handler import run as computer_control_handler_run

ALL_TOOLS = {
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
    "type_text",
]
