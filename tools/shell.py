import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def _default_workspace() -> Path:
    if sys.platform.startswith("win"):
        return Path(r"C:\Users\Admin\connectai_workspace")
    return Path.home() / "connectai_workspace"


def _resolve_cwd(cwd: Optional[str]) -> Path:
    base = Path(cwd).expanduser() if cwd else _default_workspace()
    resolved = base.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _candidate_created_paths(command: str, cwd: Path) -> list[str]:
    parts = command.split()
    candidates: list[str] = []
    for idx, part in enumerate(parts[:-1]):
        normalized = part.lower()
        if normalized in {"create-next-app@latest", "create-next-app", "create-vite@latest", "create-vite"}:
            target = parts[idx + 1].strip("\"'")
            if target and not target.startswith("-"):
                candidates.append(str((cwd / target).resolve()))
    return candidates


def run(command: str, cwd: Optional[str] = None, timeout: int = 60) -> Dict[str, Any]:
    resolved_cwd = _resolve_cwd(cwd)
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(resolved_cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "status": "success" if result.returncode == 0 else "error",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "command": command,
            "cwd": str(resolved_cwd),
            "candidate_paths": _candidate_created_paths(command, resolved_cwd),
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "stdout": "",
            "stderr": str(exc),
            "returncode": -1,
            "command": command,
            "cwd": str(resolved_cwd),
            "candidate_paths": [],
        }

