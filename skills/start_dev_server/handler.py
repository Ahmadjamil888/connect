from __future__ import annotations

import subprocess
from pathlib import Path

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "project_dir": {"type": "string"},
        "command": {"type": "string"},
    },
    "required": ["project_dir"],
}


def run(inputs, *, workspace: str, **_kwargs):
    project_dir = Path(workspace) / str(inputs["project_dir"])
    command = str(inputs.get("command", "npm.cmd run dev")).strip() or "npm.cmd run dev"
    if not project_dir.exists():
        return {"ok": False, "error": f"Project directory not found: {project_dir}"}

    process = subprocess.Popen(
        command,
        cwd=project_dir,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    process_manager = _kwargs.get("process_manager")
    payload = {
        "ok": True,
        "pid": process.pid,
        "project_dir": str(project_dir),
        "command": command,
    }
    if process_manager is not None:
        record = process_manager.register(
            name="dev_server",
            command=command,
            cwd=str(project_dir),
            process=process,
            metadata={"project_dir": str(project_dir)},
        )
        payload["process_id"] = record.process_id
        payload["log_path"] = record.log_path
    return payload
