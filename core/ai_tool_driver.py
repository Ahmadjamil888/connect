from __future__ import annotations

import time
from typing import Any

from core.browser_driver import browser
from core.vision import ask_vision
from tools.computer_control import press_key, screenshot


def _update_runtime(**changes: Any) -> None:
    try:
        from core.runtime_session import runtime_session

        runtime_session.update_state(**changes)
    except Exception:
        pass


class AIToolDriver:
    TOOLS = {
        "chatgpt": "https://chat.openai.com",
        "claude": "https://claude.ai",
        "gemini": "https://gemini.google.com",
        "perplexity": "https://perplexity.ai",
        "lovable": "https://lovable.dev",
        "bolt": "https://bolt.new",
        "v0": "https://v0.dev",
        "replit": "https://replit.com",
        "stackblitz": "https://stackblitz.com",
        "grok": "https://grok.x.ai",
        "copilot": "https://copilot.microsoft.com",
        "mistral": "https://chat.mistral.ai",
        "meta": "https://meta.ai",
    }

    def __init__(self):
        self.driver = browser
        self.active_tool = None
        self.active_url = None

    def open_tool(self, tool_name: str, url: str | None = None) -> dict[str, Any]:
        target = url or self.TOOLS.get(str(tool_name or "").lower())
        if not target:
            target = f"https://www.google.com/search?q={tool_name}+AI"
        self.active_tool = tool_name
        self.active_url = target
        _update_runtime(active_tool=tool_name, active_url=target)
        return self.driver.open_url(target)

    def send_prompt(self, prompt: str, wait_for_response: bool = True) -> dict[str, Any]:
        result = self.driver.find_and_type("chat input, prompt box, or message field", prompt, submit=True)
        if not result.get("ok"):
            press_key("shift+enter")
            time.sleep(0.2)
            press_key("enter")
        if not wait_for_response:
            return {"ok": True}
        return self.wait_for_ai_response()

    def wait_for_ai_response(self, timeout: int = 300) -> dict[str, Any]:
        start = time.time()
        while time.time() - start < timeout:
            shot = screenshot()
            if shot.get("ok"):
                status = ask_vision(
                    shot["path"],
                    "Look at this AI chat interface screenshot. Is the AI currently generating/typing a response, or has it finished? Reply GENERATING or DONE.",
                )
                if "DONE" in str(status).upper():
                    response = self.read_last_response()
                    return {"ok": True, "response": response}
            time.sleep(3)
        return {"ok": False, "error": "Response timed out"}

    def read_last_response(self) -> str:
        shot = screenshot()
        if not shot.get("ok"):
            return ""
        return str(
            ask_vision(
                shot["path"],
                "What is the last response from the AI assistant on this screen? Return the full text of the most recent AI message only.",
            )
            or ""
        )

    def continue_conversation(self, messages: list[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for message in messages:
            result = self.send_prompt(message)
            results.append({"prompt": message, "result": result})
            if self.detect_blocker():
                results.append({"blocker": True, "message": "Login or credits required"})
                break
        return results

    def detect_blocker(self) -> bool:
        shot = screenshot()
        if not shot.get("ok"):
            return False
        check = ask_vision(
            shot["path"],
            "Is there a sign-in wall, login prompt, credit limit message, upgrade prompt, or paywall visible? Reply YES or NO.",
        )
        return "YES" in str(check).upper()


ai_tool = AIToolDriver()
