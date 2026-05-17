def _computer_control():
    from . import computer_control as module

    return module


def click(*args, **kwargs):
    return _computer_control().click(*args, **kwargs)


def click_element(*args, **kwargs):
    return _computer_control().click_element(*args, **kwargs)


def find_on_screen(*args, **kwargs):
    return _computer_control().find_on_screen(*args, **kwargs)


def focus_window(*args, **kwargs):
    return _computer_control().focus_window(*args, **kwargs)


def hover(*args, **kwargs):
    return _computer_control().hover(*args, **kwargs)


def open_app(*args, **kwargs):
    return _computer_control().open_app(*args, **kwargs)


def press_key(*args, **kwargs):
    return _computer_control().press_key(*args, **kwargs)


def screenshot(*args, **kwargs):
    return _computer_control().screenshot(*args, **kwargs)


def scroll(*args, **kwargs):
    return _computer_control().scroll(*args, **kwargs)


def type_text(*args, **kwargs):
    return _computer_control().type_text(*args, **kwargs)


def send_whatsapp(*args, **kwargs):
    from .whatsapp import send_whatsapp as _send_whatsapp

    return _send_whatsapp(*args, **kwargs)


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
