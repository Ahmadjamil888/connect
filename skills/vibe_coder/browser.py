from __future__ import annotations

import time
from typing import Any

from core.ai_tool_driver import ai_tool
from core.browser_driver import browser
from core.runtime_session import runtime_session
from core.vision import ask_vision, ask_vision_coordinates
from tools.computer_control import click, press_key, screenshot, type_text


def _screen_text() -> str:
    shot = screenshot()
    if not shot.get("ok"):
        return ""
    return str(ask_vision(shot["path"], "Read the visible UI text on this screen. Return concise plain text only.") or "")


def _try_click(description: str) -> bool:
    shot = screenshot()
    if not shot.get("ok"):
        return False
    coords = ask_vision_coordinates(
        shot["path"],
        f"Where is the clickable UI element labeled or described as '{description}'? Return x,y pixel coordinates only. If not visible return NOT_FOUND.",
    )
    if not coords:
        return False
    click(coords["x"], coords["y"])
    time.sleep(0.8)
    return True


def _resolve_pre_prompt_blockers(tool_name: str) -> dict[str, Any]:
    for _ in range(4):
        text = _screen_text().lower()
        if not text:
            return {"ok": True}
        if any(token in text for token in ["log in", "login", "sign in", "continue with google", "continue with github"]):
            for label in ["sign in", "log in", "continue with google", "continue with github", "continue"]:
                if _try_click(label):
                    time.sleep(2)
                    break
            text = _screen_text().lower()
            if any(token in text for token in ["email", "password", "forgot password", "choose an account", "continue as"]):
                return {
                    "ok": False,
                    "status": "auth_required",
                    "error": f"{tool_name} requires account sign-in. Sign in in the opened browser window, then continue the same chat.",
                }
        clicked = False
        for label in ["accept", "allow", "authorize", "continue", "got it", "ok", "close", "dismiss", "skip"]:
            if label in text and _try_click(label):
                clicked = True
                break
        if not clicked:
            return {"ok": True}
    return {"ok": True}


def _post_submit_state(tool_name: str) -> dict[str, Any]:
    text = _screen_text().lower()
    if any(token in text for token in ["out of credits", "credits exhausted", "upgrade to continue", "usage limit"]):
        return {"status": "exhausted"}
    if any(token in text for token in ["sign in", "log in"]) and any(token in text for token in ["email", "password", "google", "github"]):
        return {
            "status": "auth_required",
            "error": f"{tool_name} needs sign-in before it can continue generating. Sign in in the browser window, then send a follow-up prompt.",
        }
    return {"status": "ok"}


def _compose_follow_up(message: str, project_name: str = "", session_messages: list[str] | None = None) -> str:
    history = [item.strip() for item in (session_messages or []) if item and item.strip()]
    recent = history[-6:]
    lines = []
    if project_name:
        lines.append(f"Project: {project_name}")
    if recent:
        lines.append("Conversation context:")
        lines.extend(f"- {item}" for item in recent)
    lines.append("Apply this new instruction to the existing project without restarting from scratch:")
    lines.append(message.strip())
    return "\n".join(lines)


def automate_publish(tool_name: str, project_name: str = "", target: str = "publish") -> dict[str, Any]:
    runtime_session.update_state(active_tool=tool_name)
    blocker = _resolve_pre_prompt_blockers(tool_name)
    if not blocker.get("ok"):
        return blocker
    for label in [
        "publish",
        "deploy",
        "share",
        "go live",
        "launch",
        "export",
        "push to github",
        "github",
        "connect github",
        "continue",
        "confirm",
    ]:
        if _try_click(label):
            time.sleep(1.5)
    post_submit = _post_submit_state(tool_name)
    if post_submit.get("status") == "auth_required":
        return post_submit
    if post_submit.get("status") == "exhausted":
        return post_submit
    follow_up = f"Publish or deploy this project now. Target: {target or 'publish'}."
    return continue_conversation(tool_name, [follow_up], project_name=project_name, session_messages=[follow_up])


def wait_for_completion(tool_name: str, timeout: int = 600, check_interval: int = 10) -> dict:
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
    blocker = _resolve_pre_prompt_blockers(tool_name)
    if not blocker.get("ok"):
        return {"status": blocker.get("status", "error"), "error": blocker.get("error", "Blocked before prompt")}
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
    press_key("ctrl+a")
    time.sleep(0.1)
    type_text(prompt)
    press_key("enter")
    post_submit = _post_submit_state(tool_name)
    if post_submit.get("status") != "ok":
        return post_submit
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


def continue_conversation(
    tool_name: str,
    follow_ups: list[str],
    project_name: str = "",
    session_messages: list[str] | None = None,
) -> dict:
    runtime_session.update_state(active_tool=tool_name)
    for message in follow_ups:
        print(f"  [{tool_name}] sending: {message}")
        blocker = _resolve_pre_prompt_blockers(tool_name)
        if not blocker.get("ok"):
            return blocker
        shot = screenshot()
        if not shot.get("ok"):
            return {"ok": False, "error": "Could not capture screen"}
        coords = ask_vision_coordinates(
            shot["path"],
            "Where is the chat input or prompt text box? Return x,y pixel coordinates only.",
        )
        if not coords:
            browser.find_and_click("chat input or message box")
            shot = screenshot()
            if not shot.get("ok"):
                return {"ok": False, "error": "Could not recapture screen"}
            coords = ask_vision_coordinates(
                shot["path"],
                "Where is the chat input or prompt text box? Return x,y pixel coordinates only.",
            )
            if not coords:
                return {"ok": False, "error": "Lost input box"}
        click(coords["x"], coords["y"])
        time.sleep(0.3)
        press_key("ctrl+a")
        time.sleep(0.1)
        type_text(_compose_follow_up(message, project_name=project_name, session_messages=session_messages))
        press_key("enter")
        post_submit = _post_submit_state(tool_name)
        if post_submit.get("status") == "exhausted":
            return {"status": "exhausted"}
        if post_submit.get("status") == "auth_required":
            return post_submit
        result = wait_for_completion(tool_name, timeout=300)
        if result.get("status") == "exhausted":
            return {"status": "exhausted"}
        if result.get("status") != "complete":
            return result
    return {"status": "complete"}
