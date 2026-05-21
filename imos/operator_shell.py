"""IMOS primary CLI — Claude Code-style shell with mandatory auth and real execution."""

from __future__ import annotations

import sys
import webbrowser


def run() -> None:
    from dotenv import load_dotenv
    from pathlib import Path

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    from imos import auth
    from imos import terminal_ui as ui

    if not auth.require_auth_mandatory():
        sys.exit(1)

    import ai_assistant

    ai_assistant.run_operator_cli(ui_module=ui)


def run_login_only() -> bool:
    from imos import auth
    return auth.cmd_login()
