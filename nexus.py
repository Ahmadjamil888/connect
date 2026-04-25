#!/usr/bin/env python3
"""
CONNECT Autonomous AI Operator
Better than OpenClaw. Better than Claude Code.
Controls your entire PC. Builds and deploys real products.
Thinks before it acts. Researches before it decides.
"""

import os
import sys
import io
from contextlib import redirect_stdout

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

from core.loop import run as nexus_run
from tools.registry import build_registry

try:
    from colorama import just_fix_windows_console

    just_fix_windows_console()
except Exception:
    pass

RESET = "\033[0m"
BLUE = "\033[38;2;96;165;250m"
BLUE_BRIGHT = "\033[38;2;140;196;255m"
BLUE_SOFT = "\033[38;2;116;145;255m"
MUTED = "\033[38;2;155;179;214m"
DARK = "\033[38;2;18;24;38m"
CHAT_INTENTS = [
    "hello",
    "hi",
    "hey",
    "how are you",
    "what can you do",
    "help",
    "who are you",
    "what are you",
]

PIXEL_LOGO = r"""
  CCCCC   OOOOO  N   N  N   N  EEEEE   CCCCC  TTTTT
 C       O     O NN  N  NN  N  E      C         T
 C       O     O N N N  N N N  EEEE   C         T
 C       O     O N  NN  N  NN  E      C         T
  CCCCC   OOOOO  N   N  N   N  EEEEE   CCCCC    T
"""


def _line(text: str, color: str = MUTED) -> str:
    return f"{color}{text}{RESET}"


def render_banner() -> str:
    lines = [
        _line("+------------------------------+", BLUE_SOFT),
        _line("| * Welcome to CONNECT         |", BLUE_BRIGHT),
        _line("+------------------------------+", BLUE_SOFT),
        f"{BLUE}{PIXEL_LOGO}{RESET}",
        _line("        Autonomous PC Operator & SaaS Builder", BLUE_BRIGHT),
        "",
        _line("  > Thinks before acting   > Researches before building", MUTED),
        _line("  > Controls your PC       > Builds and deploys SaaS", MUTED),
        _line("  > Manages email/social   > Never loops on failures", MUTED),
        "",
        _line("Type your goal naturally. Examples:", BLUE_BRIGHT),
        _line("  build me a SaaS for restaurant booking and deploy it"),
        _line("  clean my PC and free up space"),
        _line("  check my gmail and reply to unread emails"),
        _line("  research and build a portfolio website for a photographer"),
        _line("  create a Twitter thread about AI and post it"),
        "",
        _line("Type 'exit' to quit.", BLUE_BRIGHT),
    ]
    return "\n".join(lines)


def is_simple_chat(text: str) -> bool:
    normalized = text.lower().strip()
    return any(normalized.startswith(word) for word in CHAT_INTENTS) or len(normalized.split()) < 4


def quick_chat(message: str) -> str:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are CONNECT, an autonomous AI operator. Answer conversationally and briefly. "
                        "If the user seems to want a task done, tell them to be specific, for example "
                        "'build me a website for X'."
                    ),
                },
                {"role": "user", "content": message},
            ],
            max_tokens=300,
        )
        return response.choices[0].message.content
    except Exception:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are CONNECT, a helpful AI operator. Answer briefly and clearly.",
                },
                {"role": "user", "content": message},
            ],
            max_tokens=200,
        )
        return response.choices[0].message.content


def main():
    if not os.getenv("GROQ_API_KEY"):
        print("[ERROR] GROQ_API_KEY not set in .env file")
        print("Get free key: https://console.groq.com/keys")
        sys.exit(1)

    print(render_banner())
    with redirect_stdout(io.StringIO()):
        registry = build_registry()
    print(f"{BLUE_BRIGHT}[CONNECT]{RESET} {len(registry.list_names())} tools loaded and ready.\n")

    while True:
        try:
            goal = input(f"{BLUE}CONNECT>{RESET} ").strip()
            if not goal:
                continue
            if goal.lower() in ["exit", "quit", "bye"]:
                print(f"{BLUE_BRIGHT}CONNECT shutting down.{RESET}")
                break

            if is_simple_chat(goal):
                print(f"\n{quick_chat(goal)}\n")
                continue

            result = nexus_run(goal=goal, registry=registry)
            if result.get("status") == "error":
                print(f"\n{BLUE_BRIGHT}[CONNECT]{RESET} Error: {result.get('error', 'unknown error')}\n")
            else:
                print(f"\n{BLUE_BRIGHT}[CONNECT]{RESET} Done {result['status']} in {result['steps']} steps.\n")
        except KeyboardInterrupt:
            print("\n[Interrupted] Type exit to quit.")
        except Exception as exc:
            print(f"\n[ERROR] {exc}")


if __name__ == "__main__":
    main()
