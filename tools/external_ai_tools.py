from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


def _missing(binary: str, install: str) -> dict[str, Any]:
    return {"status": "not_installed", "error": f"{binary} binary not found", "install": install}


def _run(args: list[str], project_path: str, timeout: int = 300) -> dict[str, Any]:
    binary = shutil.which(args[0])
    if not binary:
        installs = {
            "claude": "npm install -g @anthropic-ai/claude-code",
            "codex": "npm install -g @openai/codex",
            "aider": "pip install aider-chat",
        }
        return _missing(args[0], installs.get(args[0], f"Install {args[0]} and add it to PATH"))
    try:
        cwd = str(Path(project_path).expanduser().resolve())
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "status": "success" if result.returncode == 0 else "error",
            "command": args,
            "cwd": cwd,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "command": args, "project_path": project_path}


def run_claude_code(project_path: str, task: str) -> dict[str, Any]:
    return _run(["claude", "--print", task], project_path, timeout=300)


def run_codex(project_path: str, task: str) -> dict[str, Any]:
    return _run(["codex", "--approval-mode", "full-auto", task], project_path, timeout=300)


def run_aider(project_path: str, task: str, files: list[str] | None = None) -> dict[str, Any]:
    args = ["aider", "--yes", "--message", task]
    if files:
        args.extend(files)
    return _run(args, project_path, timeout=300)
