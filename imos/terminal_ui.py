"""Claude Code-inspired terminal presentation for IMOS."""

from __future__ import annotations

import os
import sys

O = "\033[38;5;208m"
W = "\033[1;37m"
G = "\033[32m"
R = "\033[31m"
D = "\033[90m"
B = "\033[1m"
X = "\033[0m"

PROMPT = f"{O}› {X}"


def supports_color() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    if not supports_color():
        return text
    return f"{code}{text}{X}"


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def banner(*, email: str = "", model: str = "", session_id: str = "", dashboard: str = "http://127.0.0.1:7070") -> None:
    from imos.brand import SOLUTION, TAGLINE

    print(_c("IMOS", O + B) + _c("  Intelligent Machine Operating System", D))
    print(_c("  " + TAGLINE, D))
    parts = []
    if email:
        parts.append(email)
    if model:
        parts.append(model)
    if session_id:
        parts.append(f"session {session_id[:8]}")
    parts.append(f"dashboard {dashboard}")
    if parts:
        print(_c("  " + " · ".join(parts), D))
    print(_c("  " + SOLUTION, D))
    print(_c("  Type a goal — models, IDEs, browser, apps, and local execution in one runtime. /help", D))
    print()


def read_user_input() -> str:
    try:
        return input(PROMPT).strip()
    except (EOFError, KeyboardInterrupt):
        raise


def user_echo(text: str) -> None:
    print(f"{_c('You', D)}  {text}")


def assistant(text: str) -> None:
    for line in str(text).splitlines() or [""]:
        print(f"{_c('IMOS', O)}  {line}")


def tool_start(name: str, detail: str = "") -> None:
    label = f"⏺ {name}"
    if detail:
        label += f"({detail})"
    print(_c(label, W))


def tool_result(text: str, *, ok: bool = True) -> None:
    color = G if ok else R
    for line in _truncate_block(text, 12):
        print(_c(f"  ⎿ {line}", color))


def tool_end(*, ok: bool = True) -> None:
    if ok:
        print(_c("  ✓ done", G))
    else:
        print(_c("  ✗ failed", R))


def status(text: str) -> None:
    print(_c(f"  {text}", D))


def error(text: str) -> None:
    print(_c(f"  {text}", R))


def thinking(text: str, *, verbose: bool = False) -> None:
    if verbose:
        print(_c(f"  ◆ {text}", D))


def _truncate_block(text: str, max_lines: int) -> list[str]:
    lines = str(text).splitlines() or [str(text)]
    if len(lines) <= max_lines:
        return lines
    return lines[: max_lines - 1] + ["…"]
