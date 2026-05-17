from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any


def open_application(app_name: str) -> dict[str, Any]:
    try:
        if sys.platform == "darwin":
            proc = subprocess.Popen(["open", "-a", app_name])
            return {"status": "success", "app_name": app_name, "pid": proc.pid}
        if os.name == "nt":
            candidates = [app_name]
            app_lower = app_name.lower()
            mappings = {
                "cursor": [os.path.expandvars(r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe")],
                "vscode": [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"), "code"],
                "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "chrome.exe"],
            }
            candidates.extend(mappings.get(app_lower, []))
            binary = next((candidate for candidate in candidates if Path(candidate).exists() or shutil.which(candidate)), None)
            if not binary:
                return {"status": "error", "error": f"Application not found: {app_name}"}
            proc = subprocess.Popen([binary])
            return {"status": "success", "app_name": app_name, "binary": binary, "pid": proc.pid}
        binary = shutil.which(app_name)
        if not binary:
            return {"status": "error", "error": f"Application not found: {app_name}"}
        proc = subprocess.Popen([binary])
        return {"status": "success", "app_name": app_name, "binary": binary, "pid": proc.pid}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "app_name": app_name}


def take_screenshot(path: str) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "darwin":
            result = subprocess.run(["screencapture", str(target)], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return {"status": "error", "error": result.stderr or "screencapture failed"}
        elif os.name == "nt":
            from PIL import ImageGrab

            image = ImageGrab.grab()
            image.save(target)
        else:
            binary = shutil.which("scrot")
            if not binary:
                return {"status": "error", "error": "scrot is not installed"}
            result = subprocess.run([binary, str(target)], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return {"status": "error", "error": result.stderr or "scrot failed"}
        return {"status": "success", "path": str(target), "bytes_written": target.stat().st_size}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "path": path}


def get_clipboard() -> dict[str, Any]:
    try:
        if sys.platform == "darwin":
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False)
        elif os.name == "nt":
            result = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"], capture_output=True, text=True, check=False)
        else:
            result = subprocess.run(["xclip", "-o", "-selection", "clipboard"], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return {"status": "error", "error": result.stderr or "clipboard read failed"}
        return {"status": "success", "content": result.stdout}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def set_clipboard(text: str) -> dict[str, Any]:
    try:
        if sys.platform == "darwin":
            result = subprocess.run(["pbcopy"], input=text, capture_output=True, text=True, check=False)
        elif os.name == "nt":
            result = subprocess.run(["clip"], input=text, capture_output=True, text=True, shell=True, check=False)
        else:
            result = subprocess.run(["xclip", "-selection", "clipboard"], input=text, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return {"status": "error", "error": result.stderr or "clipboard write failed"}
        return {"status": "success", "characters_written": len(text)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def list_processes(filter: str | None = None) -> dict[str, Any]:
    try:
        if os.name == "nt":
            result = subprocess.run(["tasklist", "/FO", "CSV"], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return {"status": "error", "error": result.stderr or "tasklist failed"}
            import csv
            from io import StringIO

            rows = []
            for row in csv.DictReader(StringIO(result.stdout)):
                name = row.get("Image Name", "")
                if filter and filter.lower() not in name.lower():
                    continue
                rows.append({"pid": row.get("PID"), "name": name, "mem": row.get("Mem Usage"), "cpu": None})
            return {"status": "success", "processes": rows, "count": len(rows)}
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return {"status": "error", "error": result.stderr or "ps failed"}
        rows = []
        for line in result.stdout.splitlines()[1:]:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            name = parts[10]
            if filter and filter.lower() not in name.lower():
                continue
            rows.append({"pid": parts[1], "name": name, "cpu": parts[2], "mem": parts[3]})
        return {"status": "success", "processes": rows, "count": len(rows)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def kill_process(pid: int | None = None, name: str | None = None) -> dict[str, Any]:
    try:
        if pid is not None:
            if os.name == "nt":
                result = subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    return {"status": "error", "error": result.stderr or "taskkill failed", "pid": pid}
            else:
                os.kill(pid, signal.SIGTERM)
            return {"status": "success", "pid": pid}
        if name:
            if os.name == "nt":
                result = subprocess.run(["taskkill", "/IM", name, "/F"], capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    return {"status": "error", "error": result.stderr or "taskkill failed", "name": name}
            else:
                result = subprocess.run(["pkill", "-f", name], capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    return {"status": "error", "error": result.stderr or "pkill failed", "name": name}
            return {"status": "success", "name": name}
        return {"status": "error", "error": "pid or name is required"}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "pid": pid, "name": name}
