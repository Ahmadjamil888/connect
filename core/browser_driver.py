from __future__ import annotations

import time
from typing import Any

from core.vision import ask_vision, ask_vision_coordinates
from core.events import event_bus
from tools.computer_control import click, open_app, press_key, screenshot, type_text


def _update_runtime(**changes: Any) -> None:
    try:
        from core.runtime_session import runtime_session

        runtime_session.update_state(**changes)
    except Exception:
        pass


class BrowserDriver:
    def open_url(self, url: str) -> dict[str, Any]:
        event_bus.publish("tool_progress", message=f"Opening browser for {url}")
        result = {"ok": False, "error": "No browser found"}
        for browser_name in ["edge", "chrome", "firefox"]:
            result = open_app(browser_name)
            if result.get("ok"):
                _update_runtime(active_tool=browser_name, active_url=url)
                break
        if not result.get("ok"):
            return {"ok": False, "error": "No browser found"}
        time.sleep(2)
        press_key("ctrl+l")
        time.sleep(0.2)
        type_text(url)
        press_key("enter")
        time.sleep(3)
        return self.wait_for_load(url)

    def wait_for_load(self, url_hint: str, timeout: int = 30) -> dict[str, Any]:
        start = time.time()
        saw_screen = False
        while time.time() - start < timeout:
            shot = screenshot()
            if shot.get("ok"):
                saw_screen = True
                event_bus.publish("tool_progress", message=f"Waiting for page to load: {url_hint}")
                status = ask_vision(
                    shot["path"],
                    "Look at this browser screenshot. Is the page content visible (text, images, buttons), or is it still loading (spinner, blank page, progress bar)? Reply with READY or LOADING only.",
                )
                normalized = str(status).upper()
                if "READY" in normalized or ("LOADING" not in normalized and "GENERATING" not in normalized):
                    _update_runtime(active_url=url_hint)
                    return {"ok": True}
            time.sleep(2)
        if saw_screen:
            _update_runtime(active_url=url_hint)
            return {"ok": True, "warning": "Page load could not be confirmed visually before timeout."}
        return {"ok": False, "error": "Page did not load"}

    def find_and_click(self, description: str) -> dict[str, Any]:
        shot = screenshot()
        if not shot.get("ok"):
            return {"ok": False, "error": "Could not capture screen"}
        event_bus.publish("tool_progress", message=f"Finding and clicking: {description}")
        coords = ask_vision_coordinates(
            shot["path"],
            f"Where is: {description}? Return x,y pixel coordinates only. If not visible return NOT_FOUND.",
        )
        if not coords:
            return {"ok": False, "error": f"Could not find: {description}"}
        click(coords["x"], coords["y"])
        time.sleep(0.5)
        return {"ok": True, "clicked": description}

    def find_and_type(self, field_description: str, text: str, submit: bool = False) -> dict[str, Any]:
        shot = screenshot()
        if not shot.get("ok"):
            return {"ok": False, "error": "Could not capture screen"}
        event_bus.publish("tool_progress", message=f"Typing into: {field_description}")
        coords = ask_vision_coordinates(
            shot["path"],
            f"Where is the input field for: {field_description}? Return x,y coordinates only.",
        )
        if not coords:
            return {"ok": False, "error": f"Input not found: {field_description}"}
        click(coords["x"], coords["y"])
        time.sleep(0.3)
        press_key("ctrl+a")
        time.sleep(0.1)
        type_text(text)
        if submit:
            press_key("enter")
        return {"ok": True}

    def read_screen_text(self) -> str:
        shot = screenshot()
        if not shot.get("ok"):
            return ""
        return str(
            ask_vision(
                shot["path"],
                "Read all visible text on this screen. Return it as plain text.",
            )
            or ""
        )

    def wait_for_element(self, description: str, timeout: int = 60) -> dict[str, Any]:
        start = time.time()
        while time.time() - start < timeout:
            shot = screenshot()
            if shot.get("ok"):
                found = ask_vision(
                    shot["path"],
                    f"Is '{description}' visible on screen? Reply YES or NO.",
                )
                if "YES" in str(found).upper():
                    return {"ok": True}
            time.sleep(3)
        return {"ok": False, "error": f"'{description}' never appeared"}

    def scroll_down(self, times: int = 3) -> dict[str, Any]:
        for _ in range(max(1, times)):
            press_key("page_down")
        return {"ok": True, "times": times}

    def go_back(self) -> dict[str, Any]:
        press_key("alt+left")
        return {"ok": True}

    def close_tab(self) -> dict[str, Any]:
        press_key("ctrl+w")
        return {"ok": True}

    def get_current_url(self) -> str:
        press_key("ctrl+l")
        time.sleep(0.2)
        shot = screenshot()
        url = ""
        if shot.get("ok"):
            url = str(
                ask_vision(
                    shot["path"],
                    "What URL is shown in the browser address bar? Return the URL only.",
                )
                or ""
            ).strip()
        press_key("escape")
        if url:
            _update_runtime(active_url=url)
        return url


browser = BrowserDriver()
