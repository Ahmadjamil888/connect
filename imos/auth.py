"""
IMOS Authentication.
Handles user sign-in, sign-out, and session management for IMOS.
- imos login  → opens browser to IMOS sign-in, waits for callback, saves session
- imos logout → clears saved session
- is_authenticated() → checks if user has a valid session
- require_auth() → called at startup; blocks until user logs in if not authenticated
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Auth key — internal, never shown to users
_AUTH_KEY = "pk_test_bmVhdC1zcGFuaWVsLTExLmNsZXJrLmFjY291bnRzLmRldiQ"

# Auth state lives in ~/.imos/auth/ — separate from workspace so it persists
AUTH_DIR = Path.home() / ".imos" / "auth"
AUTH_DIR.mkdir(parents=True, exist_ok=True)

O = "\033[38;5;208m"
W = "\033[1;37m"
G = "\033[32m"
R = "\033[31m"
D = "\033[90m"
X = "\033[0m"


def _get_manager():
    """Return a configured auth manager."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from gateway_runtime.auth import ClerkAuthManager
    pk = os.environ.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "").strip() or _AUTH_KEY
    sk = os.environ.get("CLERK_SECRET_KEY", "").strip()
    return ClerkAuthManager(
        workspace_root=AUTH_DIR,
        publishable_key=pk,
        enabled=True,
        secret_key=sk,
    )


def is_authenticated() -> bool:
    """Return True if the user has a valid saved session."""
    try:
        mgr = _get_manager()
        return mgr.is_signed_in()
    except Exception:
        return False


def current_user() -> dict:
    """Return current user info dict."""
    try:
        mgr = _get_manager()
        return mgr.current_user()
    except Exception:
        return {"signed_in": False}


def cmd_login(timeout: int = 300) -> bool:
    """
    Run the IMOS CLI login flow.
    Opens browser to IMOS sign-in, waits for callback, saves session.
    Returns True on success.
    """
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    print(f"\n{O}IMOS Login{X}")
    print(f"{D}  Opening your browser to sign in...{X}")
    print(f"{D}  Waiting up to {timeout//60} minutes. Press Ctrl+C to cancel.{X}\n")

    try:
        mgr = _get_manager()
        ok, message = mgr.start_cli_login(timeout_seconds=timeout)
        if ok:
            state = mgr.load_state()
            print(f"\n{G}  ✓ Signed in successfully!{X}")
            if state.email:
                print(f"  {D}Account:{X} {W}{state.email}{X}")
            print()
            return True
        else:
            print(f"\n{R}  ✗ Sign-in failed: {message}{X}\n")
            return False
    except KeyboardInterrupt:
        print(f"\n{D}  Login cancelled.{X}\n")
        return False
    except Exception as e:
        print(f"\n{R}  ✗ Login error: {e}{X}")
        print(f"{D}  Make sure you have internet access and try again.{X}\n")
        return False


def cmd_logout():
    """Clear the saved IMOS session."""
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

def cmd_logout():
    """Clear the saved IMOS session."""
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    try:
        mgr = _get_manager()
        state = mgr.load_state()
        if not state.signed_in:
            print(f"\n{D}  Not currently signed in.{X}\n")
            return
        email = state.email or "unknown"
        mgr.clear_state()
        print(f"\n{G}  ✓ Signed out ({email}){X}\n")
    except Exception as e:
        print(f"\n{R}  Logout error: {e}{X}\n")


def cmd_whoami_clerk():
    """Print IMOS session info."""
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    try:
        mgr = _get_manager()
        state = mgr.load_state()
        if state.signed_in:
            print(f"\n{G}  ● IMOS{X}  Signed in")
            if state.email:
                print(f"    {D}Account:{X} {W}{state.email}{X}")
            if state.updated_at:
                import datetime
                ts = datetime.datetime.fromtimestamp(state.updated_at).strftime("%Y-%m-%d %H:%M")
                print(f"    {D}Since:{X}   {ts}")
        else:
            print(f"\n{D}  ○ IMOS{X}  Not signed in  {D}(run: imos login){X}")
        print()
    except Exception as e:
        print(f"\n{R}  Auth status error: {e}{X}\n")


def require_auth(skip_if_no_key: bool = False) -> bool:
    """
    Called at IMOS startup. If user is not authenticated, prompt them to log in.
    Returns True if authenticated.
    """
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    pk = os.environ.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "").strip() or _AUTH_KEY
    if not pk:
        if skip_if_no_key:
            return True
        return False

    if is_authenticated():
        state = current_user()
        email = state.get("email", "")
        print(f"{G}  ✓ Signed in{X}" + (f" as {W}{email}{X}" if email else "") + "\n")
        return True

    # Not authenticated — must log in
    print(f"\n{O}  IMOS requires you to sign in first.{X}")
    print(f"{D}  Your session is saved locally — you only need to do this once.{X}\n")

    try:
        choice = input(f"{O}  › {X}Sign in now? [Y/n]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        return False

    if choice in ("n", "no"):
        print(f"{D}  Skipped. Some features may be unavailable.{X}\n")
        return False

    return cmd_login()
