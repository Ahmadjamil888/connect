from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict


SERVICE_NAME = "ConnectAI"
DISPLAY_NAME = "CONNECT AI Gateway"


def _python_executable() -> str:
    return sys.executable


def _script_path() -> str:
    return str((Path(__file__).resolve().parent.parent / "ai_assistant.py"))


def _bin_path(mode: str, config_path: str) -> str:
    return f'"{_python_executable()}" "{_script_path()}" --service-stack --{mode} --gateway-config "{config_path}"'


def install_windows_service(mode: str, config_path: str) -> Dict[str, str]:
    command = [
        "sc.exe",
        "create",
        SERVICE_NAME,
        f'binPath= {_bin_path(mode, config_path)}',
        "start= auto",
        f"DisplayName= {DISPLAY_NAME}",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    return {"ok": str(result.returncode == 0).lower(), "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def remove_windows_service() -> Dict[str, str]:
    result = subprocess.run(["sc.exe", "delete", SERVICE_NAME], capture_output=True, text=True)
    return {"ok": str(result.returncode == 0).lower(), "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def start_windows_service() -> Dict[str, str]:
    result = subprocess.run(["sc.exe", "start", SERVICE_NAME], capture_output=True, text=True)
    return {"ok": str(result.returncode == 0).lower(), "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def stop_windows_service() -> Dict[str, str]:
    result = subprocess.run(["sc.exe", "stop", SERVICE_NAME], capture_output=True, text=True)
    return {"ok": str(result.returncode == 0).lower(), "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def status_windows_service() -> Dict[str, str]:
    result = subprocess.run(["sc.exe", "query", SERVICE_NAME], capture_output=True, text=True)
    return {"ok": str(result.returncode == 0).lower(), "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def format_result(payload: Dict[str, str]) -> str:
    return json.dumps(payload, indent=2)
