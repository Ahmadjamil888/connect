def _get_pyautogui():
    try:
        import pyautogui
    except ModuleNotFoundError as exc:
        raise RuntimeError("screen control unavailable: missing dependency 'pyautogui'") from exc
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
    return pyautogui


def click_at(x: int, y: int) -> str:
    pyautogui = _get_pyautogui()
    pyautogui.click(x, y)
    return f"Clicked at ({x}, {y})"


def type_text(text: str) -> str:
    pyautogui = _get_pyautogui()
    pyautogui.write(text, interval=0.02)
    return f"Typed {len(text)} characters"


def shortcut(keys: str) -> str:
    pyautogui = _get_pyautogui()
    normalized = [part.strip().lower().replace("ctrl", "ctrl") for part in keys.replace("+", " ").split() if part.strip()]
    pyautogui.hotkey(*normalized)
    return f"Pressed shortcut: {keys}"


def scroll(direction: str, amount: int) -> str:
    pyautogui = _get_pyautogui()
    pyautogui.scroll(amount if direction.lower() == "up" else -amount)
    return f"Scrolled {direction} by {amount}"


def drag(x1: int, y1: int, x2: int, y2: int) -> str:
    pyautogui = _get_pyautogui()
    pyautogui.moveTo(x1, y1)
    pyautogui.dragTo(x2, y2, duration=0.3, button="left")
    return f"Dragged from ({x1}, {y1}) to ({x2}, {y2})"

