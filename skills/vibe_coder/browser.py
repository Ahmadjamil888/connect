from __future__ import annotations

import time

from core.ai_tool_driver import ai_tool
from core.runtime_session import runtime_session
from core.vision import ask_vision_coordinates
from tools.computer_control import click, press_key, screenshot, type_text


def wait_for_completion(tool_name: str, timeout: int = 600, check_interval: int = 10) -> dict:
    from core.vision import ask_vision

    start = time.time()
    while time.time() - start < timeout:
        shot = screenshot()
        if not shot.get("ok"):
            time.sleep(check_interval)
            continue
        result = ask_vision(
            shot["path"],
            (
                f"Look at this screenshot of {tool_name}. "
                f"Tell me ONE of: GENERATING, COMPLETE, "
                f"CREDITS_EXHAUSTED, ERROR, UNKNOWN. "
                f"Reply with just the single word."
            ),
        )
        status = str(result or "").strip().upper()
        print(f"  [{tool_name}] status: {status}")
        if status == "COMPLETE":
            return {"status": "complete"}
        if status == "CREDITS_EXHAUSTED":
            return {"status": "exhausted"}
        if status == "ERROR":
            return {"status": "error"}
        time.sleep(check_interval)
    return {"status": "timeout"}


def _open_and_submit(tool_name: str, url: str, prompt: str, input_prompt: str) -> dict:
    runtime_session.update_state(active_tool=tool_name, active_url=url)
    opened = ai_tool.open_tool(tool_name, url=url)
    if not opened.get("ok"):
        return {"status": "error", "error": opened.get("error", f"Could not open {tool_name}")}
    time.sleep(2)
    shot = screenshot()
    if not shot.get("ok"):
        return {"status": "error", "error": "Could not capture screen"}
    coords = ask_vision_coordinates(
        shot["path"],
        input_prompt,
    )
    if not coords:
        return {"status": "error", "error": f"Could not find prompt input on {tool_name}"}
    click(coords["x"], coords["y"])
    time.sleep(0.3)
    type_text(prompt)
    press_key("enter")
    return wait_for_completion(tool_name)


def run_on_lovable(prompt: str, project_name: str) -> dict:
    return _open_and_submit(
        "lovable",
        "https://lovable.dev",
        prompt,
        "Where is the prompt input box on lovable.dev? Return x,y pixel coordinates only.",
    )


def run_on_bolt(prompt: str, project_name: str) -> dict:
    return _open_and_submit(
        "bolt",
        "https://bolt.new",
        prompt,
        "Where is the main prompt input box on bolt.new? Return x,y pixel coordinates only.",
    )


def run_on_v0(prompt: str, project_name: str) -> dict:
    return _open_and_submit(
        "v0",
        "https://v0.dev",
        prompt,
        "Where is the prompt input box on v0.dev? Return x,y pixel coordinates only.",
    )


def run_on_replit(prompt: str, project_name: str) -> dict:
    return _open_and_submit(
        "replit",
        "https://replit.com",
        prompt,
        "Where is the prompt input box or create app input on replit.com? Return x,y pixel coordinates only.",
    )


def run_on_stackblitz(prompt: str, project_name: str) -> dict:
    return _open_and_submit(
        "stackblitz",
        "https://stackblitz.com",
        prompt,
        "Where is the prompt input box or starter input on stackblitz.com? Return x,y pixel coordinates only.",
    )


def continue_conversation(tool_name: str, follow_ups: list[str]) -> dict:
    runtime_session.update_state(active_tool=tool_name)
    for message in follow_ups:
        print(f"  [{tool_name}] sending: {message}")
        shot = screenshot()
        if not shot.get("ok"):
            return {"ok": False, "error": "Could not capture screen"}
        coords = ask_vision_coordinates(
            shot["path"],
            "Where is the chat input or prompt text box? Return x,y pixel coordinates only.",
        )
        if not coords:
            return {"ok": False, "error": "Lost input box"}
        click(coords["x"], coords["y"])
        time.sleep(0.3)
        type_text(message)
        press_key("enter")
        result = wait_for_completion(tool_name, timeout=300)
        if result.get("status") == "exhausted":
            return {"status": "exhausted"}
        if result.get("status") != "complete":
            return result
    return {"status": "complete"}
