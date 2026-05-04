from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "IMOS"


def _command(repo_root: Path) -> str:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" "{repo_root / "service" / "imos_service.py"}"'


def enable_autostart(repo_root: Path) -> dict[str, Any]:
    import winreg

    command = _command(repo_root)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, command)
    return {"ok": True, "command": command}


def disable_autostart() -> dict[str, Any]:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, RUN_NAME)
    except FileNotFoundError:
        return {"ok": True, "removed": False}
    return {"ok": True, "removed": True}


def autostart_status(repo_root: Path) -> dict[str, Any]:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, RUN_NAME)
            return {"enabled": True, "value": value, "expected": _command(repo_root)}
    except FileNotFoundError:
        return {"enabled": False, "value": "", "expected": _command(repo_root)}


def safe_autostart_status(repo_root: Path) -> dict[str, Any]:
    try:
        return autostart_status(repo_root)
    except Exception as exc:
        return {"enabled": False, "value": "", "expected": _command(repo_root), "error": str(exc)}
