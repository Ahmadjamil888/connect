from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _resolve_binary(candidates: list[str]) -> str | None:
    for candidate in candidates:
        if os.path.isabs(candidate) and Path(candidate).exists():
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    return None


def _launch(binary: str, path: str) -> dict[str, Any]:
    target = str(Path(path).expanduser().resolve())
    proc = subprocess.Popen([binary, target])
    return {"status": "success", "binary": binary, "path": target, "pid": proc.pid}


def open_cursor(path: str) -> dict[str, Any]:
    candidates = ["cursor"]
    if os.name == "nt":
        candidates.extend([os.path.expandvars(r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe")])
    elif sys.platform == "darwin":
        candidates.extend(["/Applications/Cursor.app/Contents/Resources/app/bin/cursor", "/Applications/Cursor.app/Contents/MacOS/Cursor"])
    binary = _resolve_binary(candidates)
    if not binary:
        return {"status": "not_installed", "error": "Cursor binary not found", "hint": "Install Cursor or add it to PATH"}
    try:
        return _launch(binary, path)
    except Exception as exc:
        return {"status": "error", "error": str(exc), "path": path}


def open_vscode(path: str) -> dict[str, Any]:
    candidates = ["code"]
    if os.name == "nt":
        candidates.extend([os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe")])
    elif sys.platform == "darwin":
        candidates.extend(["/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code", "/Applications/Visual Studio Code.app/Contents/MacOS/Electron"])
    binary = _resolve_binary(candidates)
    if not binary:
        return {"status": "not_installed", "error": "VS Code binary not found", "hint": "Install VS Code or add `code` to PATH"}
    try:
        return _launch(binary, path)
    except Exception as exc:
        return {"status": "error", "error": str(exc), "path": path}


def open_in_ide(path: str, ide: str = "auto") -> dict[str, Any]:
    if ide == "cursor":
        return open_cursor(path)
    if ide == "vscode":
        return open_vscode(path)
    cursor_result = open_cursor(path)
    if cursor_result.get("status") == "success":
        return cursor_result
    vscode_result = open_vscode(path)
    if vscode_result.get("status") == "success":
        return vscode_result
    return {
        "status": "not_installed",
        "error": "No supported IDE binary found",
        "hint": "Install Cursor or VS Code and ensure the CLI launcher is on PATH",
        "attempts": [cursor_result, vscode_result],
    }
