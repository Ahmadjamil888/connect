import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import psutil


def list_processes(filter_name: str = None) -> List[Dict[str, Any]]:
    rows = []
    for proc in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
        try:
            info = proc.info
            name = info.get("name") or ""
            if filter_name and filter_name.lower() not in name.lower():
                continue
            rows.append(info)
        except Exception:
            continue
    return rows


def kill_process(name: str = None, pid: int = None) -> str:
    if pid is not None:
        psutil.Process(pid).kill()
        return f"Killed PID {pid}"
    if name:
        killed = 0
        for proc in psutil.process_iter(["name"]):
            try:
                if name.lower() in (proc.info.get("name") or "").lower():
                    proc.kill()
                    killed += 1
            except Exception:
                continue
        return f"Killed {killed} process(es) matching {name}"
    return "Error: provide name or pid"


def system_info() -> Dict[str, Any]:
    disk_path = "C:\\" if os.name == "nt" else "/"
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(disk_path)
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "cpu_count": psutil.cpu_count(),
        "ram_total_gb": round(vm.total / (1024**3), 2),
        "ram_used_percent": vm.percent,
        "disk_total_gb": round(disk.total / (1024**3), 2),
        "disk_used_percent": disk.percent,
    }


def clean_temp(confirm: bool = False) -> str:
    if not confirm:
        return "Refusing to clean temp files without confirm=true"
    targets = {Path(tempfile.gettempdir())}
    if os.name == "nt":
        windows_temp = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Temp"
        targets.add(windows_temp)
    removed = 0
    errors = 0
    for target in targets:
        if not target.exists():
            continue
        for child in target.iterdir():
            try:
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=False)
                else:
                    child.unlink()
                removed += 1
            except Exception:
                errors += 1
    return f"Temp cleanup complete. Removed={removed}, errors={errors}"


def open_application(name_or_path: str) -> str:
    try:
        os.startfile(name_or_path)  # type: ignore[attr-defined]
        return f"Opened {name_or_path}"
    except Exception:
        try:
            subprocess.Popen([name_or_path], shell=False)
            return f"Opened {name_or_path}"
        except Exception as exc:
            return f"Error opening {name_or_path}: {exc}"
