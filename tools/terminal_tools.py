from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any


def run_command(command: str, cwd: str | None = None, timeout: int = 120) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=str(Path(cwd).expanduser().resolve()) if cwd else None,
            timeout=timeout,
            shell=True,
            capture_output=True,
            text=True,
        )
        status = "success" if result.returncode == 0 else "error"
        return {
            "status": status,
            "command": command,
            "cwd": str(Path(cwd).expanduser().resolve()) if cwd else None,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "command": command}


def run_command_interactive(command: str, cwd: str | None = None) -> dict[str, Any]:
    try:
        proc = subprocess.Popen(
            command,
            cwd=str(Path(cwd).expanduser().resolve()) if cwd else None,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        lines: list[str] = []
        started = time.time()
        if proc.stdout is not None:
            for line in proc.stdout:
                lines.append(line.rstrip())
        proc.wait()
        status = "success" if proc.returncode == 0 else "error"
        return {
            "status": status,
            "command": command,
            "cwd": str(Path(cwd).expanduser().resolve()) if cwd else None,
            "output_lines": lines,
            "combined_output": "\n".join(lines),
            "exit_code": proc.returncode,
            "duration_seconds": round(time.time() - started, 3),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "command": command}
