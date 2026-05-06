from __future__ import annotations

from core.events import event_bus
from skills.vibe_coder.browser import continue_conversation, run_on_lovable, wait_for_completion


def run_full_lovable_session(prompt: str, existing_project: str | None = None) -> dict:
    event_bus.publish("tool_progress", message="Lovable session starting...")
    return run_on_lovable(prompt if not existing_project else "continue", existing_project or "project")


def request_change(user_message: str) -> dict:
    event_bus.publish("tool_progress", message=f"Lovable change request: {user_message}")
    return continue_conversation("lovable", [user_message])


def enable_and_deploy() -> dict:
    event_bus.publish("tool_progress", message="Lovable deploy requested...")
    return continue_conversation("lovable", ["Deploy this project and make it live."])


def push_to_github() -> dict:
    event_bus.publish("tool_progress", message="Lovable GitHub push requested...")
    return continue_conversation("lovable", ["Push this project to GitHub."])
