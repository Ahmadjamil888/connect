from __future__ import annotations

import subprocess

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {"type": "string"},
        "timeout_seconds": {"type": "integer"},
    },
    "required": ["command"],
}


def run(inputs, *, workspace: str, **_kwargs):
    shell_runner = _kwargs.get("shell_runner")
    command = str(inputs["command"])
    timeout_seconds = int(inputs.get("timeout_seconds", 120) or 120)
    if shell_runner is not None:
        result = shell_runner.run(command, cwd=workspace, timeout=timeout_seconds)
        return {
            "ok": result.ok,
            "command": result.command,
            "cwd": result.cwd,
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "duration_seconds": result.duration_seconds,
            "log_path": result.log_path,
        }
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=workspace,
        timeout=timeout_seconds,
    )
    return {
        "ok": result.returncode == 0,
        "command": command,
        "cwd": workspace,
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }
