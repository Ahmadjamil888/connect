import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from dotenv import load_dotenv
from groq import Groq


load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

REASONING_MODEL = "compound-beta"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
FAST_MODEL = "llama-3.1-8b-instant"
TOOL_FALLBACK_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are NEXUS, an autonomous AI operator running on Windows.

You control a real PC. Every action you take has real consequences.

YOUR DECISION PROCESS (follow this every single time):
1. Look at what is currently on screen
2. Read the current goal and recent action history
3. Think: "What is the SINGLE most useful next action right now?"
4. If you need information you don't have: use research_web FIRST
5. If you need to see what happened: use take_screenshot FIRST
6. Choose ONE tool and call it
7. Never assume an action worked verify with screenshot after browser/UI actions
8. If a tool fails once, try a DIFFERENT approach never repeat the same failed call

RESEARCH RULE (CRITICAL):
Before making ANY technical decision (framework, library, service, approach),
you MUST call research_web to find current best practices. Do not use training
knowledge alone for technical choices. The web is more current than you.

FAILURE RULE:
If a tool fails, do NOT replan from the beginning. Continue from where you are.
Think about WHY it failed and try a different method.

COMPLETION RULE:
When the goal is fully done and verified, output exactly: GOAL_COMPLETE
"""


def _build_synthetic_response(payload: Dict[str, Any]):
    if payload.get("status") == "GOAL_COMPLETE":
        message = SimpleNamespace(content="GOAL_COMPLETE", tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    tool_name = str(payload.get("tool_name", "")).strip()
    tool_args = payload.get("tool_args", {})
    tool_call = SimpleNamespace(
        function=SimpleNamespace(name=tool_name, arguments=json.dumps(tool_args))
    )
    message = SimpleNamespace(content="", tool_calls=[tool_call])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def think(goal: str, screen_b64: str, history: List[Dict[str, Any]], tools: List[dict]):
    """
    Single reasoning step. Returns one tool call or GOAL_COMPLETE.
    This is the ENTIRE brain. No planner. No task graph. Just this.
    """
    desktop = Path.home() / "Desktop"
    environment_hint = {
        "cwd": str(Path.cwd()),
        "home": str(Path.home()),
        "desktop": str(desktop if desktop.exists() else Path.home()),
    }
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Current Goal: {goal}\n\nEnvironment:\n{json.dumps(environment_hint, indent=2)}\n\nRecent Actions:\n{json.dumps(history[-8:], indent=2)}\n\n"
                "A screen snapshot was captured for local observation, but you should choose the next action mainly "
                "from goal state and recent history. What is the next single action? If complete, say GOAL_COMPLETE."
            ),
        },
    ]

    tool_calling_requests = [
        {
            "model": TOOL_FALLBACK_MODEL,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "max_tokens": 1024,
            "temperature": 0.1,
        },
        {
            "model": FAST_MODEL,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "max_tokens": 1024,
            "temperature": 0.1,
        },
    ]
    last_error = None
    for request in tool_calling_requests:
        try:
            return client.chat.completions.create(**request)
        except Exception as exc:
            last_error = exc
            continue

    fallback_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Current Goal: {goal}\n\nRecent Actions:\n{json.dumps(history[-8:], indent=2)}\n\n"
                "Return strict JSON only.\n"
                'If complete: {"status":"GOAL_COMPLETE"}\n'
                'Otherwise: {"tool_name":"one_of_the_available_tools","tool_args":{}}\n'
                f"Available tools: {[tool['function']['name'] for tool in tools]}\n"
                f"Environment: {json.dumps(environment_hint)}"
            ),
        },
    ]
    for model_name in [TOOL_FALLBACK_MODEL, FAST_MODEL]:
        try:
            fallback_response = client.chat.completions.create(
                model=model_name,
                messages=fallback_messages,
                max_tokens=256,
                temperature=0.1,
            )
            content = fallback_response.choices[0].message.content or ""
            start = content.find("{")
            end = content.rfind("}")
            payload = json.loads(content[start : end + 1])
            return _build_synthetic_response(payload)
        except Exception as exc:
            last_error = exc
            continue
    raise RuntimeError(str(last_error) if last_error else "No available model could decide the next action.")
