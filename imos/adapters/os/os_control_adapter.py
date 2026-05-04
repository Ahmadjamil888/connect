from __future__ import annotations

import asyncio
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psutil

from imos.adapters.os.common import BaseOSAdapter


class OsControlAdapter(BaseOSAdapter):
    def __init__(self, name: str = "os_control", config: dict[str, Any] | None = None) -> None:
        super().__init__(
            name=name,
            config=config,
            capabilities=[
                "list_processes",
                "start_process",
                "kill_process",
                "get_process_tree",
                "read_file",
                "write_file",
                "copy_file",
                "move_file",
                "delete_path",
                "search_files",
                "scan_unwanted_files",
                "delete_unwanted_files",
                "watch_path",
                "run_shell",
                "stream_shell",
                "registry_read",
                "registry_write",
                "registry_delete",
                "scheduled_tasks",
                "services",
                "get_env",
                "set_env",
                "delete_env",
                "system_info",
                "clipboard_read",
                "clipboard_write",
                "notify",
                "screenshot",
                "window_management",
                "keyboard_mouse",
                "audio_control",
                "power_management",
            ],
        )

    async def health_check(self) -> bool:
        return True

    def _check_policy(self, action: str, confirm: bool = False) -> None:
        destructive = {"kill_process", "delete_path", "registry_delete", "set_env", "delete_env", "shutdown", "restart", "hibernate", "sleep"}
        if action in destructive and not (confirm or self.config.get("allow_destructive")):
            raise PermissionError(f"{action} requires confirm=True or allow_destructive")

    async def list_processes(self) -> Any:
        return [
            {"pid": proc.pid, "name": proc.info.get("name"), "cpu_percent": proc.info.get("cpu_percent"), "memory_percent": proc.info.get("memory_percent")}
            for proc in psutil.process_iter(["name", "cpu_percent", "memory_percent"])
        ]

    async def start_process(self, command: str) -> Any:
        process = await asyncio.create_subprocess_shell(command)
        return {"pid": process.pid, "command": command}

    async def kill_process(self, pid: int | None = None, name: str | None = None, confirm: bool = False) -> Any:
        self._check_policy("kill_process", confirm)
        if pid is not None:
            psutil.Process(pid).kill()
            return {"killed_pid": pid}
        killed = 0
        for proc in psutil.process_iter(["name"]):
            if name and name.lower() in (proc.info.get("name") or "").lower():
                proc.kill()
                killed += 1
        return {"killed": killed}

    async def get_process_tree(self, pid: int) -> Any:
        proc = psutil.Process(pid)
        return {"pid": proc.pid, "children": [{"pid": child.pid, "name": child.name()} for child in proc.children(recursive=True)]}

    async def read_file(self, path: str) -> Any:
        return Path(path).read_text(encoding="utf-8", errors="replace")

    async def write_file(self, path: str, content: str) -> Any:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": str(target)}

    async def copy_file(self, src: str, dst: str) -> Any:
        shutil.copy2(src, dst)
        return {"src": src, "dst": dst}

    async def move_file(self, src: str, dst: str) -> Any:
        shutil.move(src, dst)
        return {"src": src, "dst": dst}

    async def delete_path(self, path: str, confirm: bool = False) -> Any:
        self._check_policy("delete_path", confirm)
        target = Path(path)
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        return {"deleted": path}

    async def search_files(self, pattern: str, root: str = ".") -> Any:
        return [str(item) for item in Path(root).rglob(pattern)]

    async def scan_unwanted_files(self, root: str | None = None) -> Any:
        roots = []
        if root:
            roots.append(Path(root))
        else:
            env_roots = [
                os.getenv("TEMP"),
                os.getenv("TMP"),
                str(Path.home() / "Downloads"),
                str(Path.home() / "Desktop"),
            ]
            seen_roots: set[str] = set()
            for item in env_roots:
                if not item:
                    continue
                normalized = str(Path(item).resolve())
                if normalized in seen_roots:
                    continue
                seen_roots.add(normalized)
                roots.append(Path(normalized))
        patterns = ["*.tmp", "*.temp", "*.bak", "*.old", "*.log", "*.dmp"]
        matches: list[str] = []
        seen_matches: set[str] = set()
        for base in roots:
            if not base.exists():
                continue
            for pattern in patterns:
                try:
                    for item in base.rglob(pattern):
                        candidate = str(item)
                        if candidate in seen_matches:
                            continue
                        seen_matches.add(candidate)
                        matches.append(candidate)
                        if len(matches) >= 200:
                            return {"roots": [str(path) for path in roots], "patterns": patterns, "matches": matches}
                except Exception:
                    continue
        return {"roots": [str(path) for path in roots], "patterns": patterns, "matches": matches}

    async def delete_unwanted_files(self, root: str | None = None, confirm: bool = False) -> Any:
        self._check_policy("delete_path", confirm)
        scan = await self.scan_unwanted_files(root=root)
        deleted: list[str] = []
        failed: list[dict[str, str]] = []
        for match in scan.get("matches", []):
            target = Path(match)
            try:
                if target.exists() and target.is_file():
                    target.unlink()
                    deleted.append(str(target))
            except Exception as exc:
                failed.append({"path": str(target), "error": str(exc)})
        return {
            "roots": scan.get("roots", []),
            "patterns": scan.get("patterns", []),
            "deleted": deleted,
            "failed": failed,
            "deleted_count": len(deleted),
        }

    async def run_shell(self, command: str, timeout: int = 60, cwd: str | None = None) -> Any:
        process = await asyncio.create_subprocess_shell(command, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return {"stdout": stdout.decode(), "stderr": stderr.decode(), "returncode": process.returncode}

    async def stream_shell(self, command: str, cwd: str | None = None) -> Any:
        process = await asyncio.create_subprocess_shell(command, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        lines = []
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            lines.append(line.decode(errors="replace"))
        await process.wait()
        return {"stdout": "".join(lines), "returncode": process.returncode}

    async def registry_read(self, hive: str, path: str, name: str) -> Any:
        if platform.system() != "Windows":
            return {"error": "Registry only available on Windows"}
        import winreg

        handle = getattr(winreg, hive)
        with winreg.OpenKey(handle, path) as key:
            value, value_type = winreg.QueryValueEx(key, name)
            return {"value": value, "type": value_type}

    async def registry_write(self, hive: str, path: str, name: str, value: Any, value_type: int, confirm: bool = False) -> Any:
        self._check_policy("registry_write", confirm)
        if platform.system() != "Windows":
            return {"error": "Registry only available on Windows"}
        import winreg

        handle = getattr(winreg, hive)
        with winreg.CreateKey(handle, path) as key:
            winreg.SetValueEx(key, name, 0, value_type, value)
        return {"written": name}

    async def registry_delete(self, hive: str, path: str, name: str, confirm: bool = False) -> Any:
        self._check_policy("registry_delete", confirm)
        if platform.system() != "Windows":
            return {"error": "Registry only available on Windows"}
        import winreg

        handle = getattr(winreg, hive)
        with winreg.OpenKey(handle, path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
        return {"deleted": name}

    async def scheduled_tasks(self, action: str = "list", task_name: str | None = None, command: str | None = None) -> Any:
        if platform.system() != "Windows":
            return {"error": "Scheduled tasks only available on Windows"}
        if action == "list":
            return await self.run_shell("schtasks /query /fo csv")
        if action == "run":
            return await self.run_shell(f'schtasks /run /tn "{task_name}"')
        if action == "delete":
            return await self.run_shell(f'schtasks /delete /tn "{task_name}" /f')
        if action == "create":
            return await self.run_shell(f'schtasks /create /sc once /st 23:59 /tn "{task_name}" /tr "{command}"')
        return {"error": "Unknown scheduled task action"}

    async def services(self, action: str = "list", service_name: str | None = None) -> Any:
        if platform.system() != "Windows":
            return {"error": "Service control only available on Windows"}
        if action == "list":
            return await self.run_shell("sc query type= service state= all")
        if action in {"start", "stop"}:
            return await self.run_shell(f"sc {action} {service_name}")
        if action == "restart":
            await self.run_shell(f"sc stop {service_name}")
            return await self.run_shell(f"sc start {service_name}")
        return {"error": "Unknown service action"}

    async def get_env(self, key: str) -> Any:
        return {"key": key, "value": os.getenv(key)}

    async def set_env(self, key: str, value: str, confirm: bool = False) -> Any:
        self._check_policy("set_env", confirm)
        os.environ[key] = value
        return {"key": key, "value": value}

    async def delete_env(self, key: str, confirm: bool = False) -> Any:
        self._check_policy("delete_env", confirm)
        os.environ.pop(key, None)
        return {"deleted": key}

    async def system_info(self) -> Any:
        disk_root = "C:\\" if platform.system() == "Windows" else "/"
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.2),
            "ram_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage(disk_root).percent,
            "uptime_seconds": int(time.time() - psutil.boot_time()),
            "os": platform.platform(),
            "hostname": socket.gethostname(),
            "ips": list({addr.address for _, addrs in psutil.net_if_addrs().items() for addr in addrs if "." in addr.address}),
        }

    async def clipboard_read(self) -> Any:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        value = root.clipboard_get()
        root.destroy()
        return {"clipboard": value}

    async def clipboard_write(self, text: str) -> Any:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return {"written": len(text)}

    async def notify(self, title: str, message: str) -> Any:
        if platform.system() == "Windows":
            return await self.run_shell(f'powershell -Command "New-BurntToastNotification -Text \'{title}\', \'{message}\'"')
        if platform.system() == "Darwin":
            return await self.run_shell(f"osascript -e 'display notification \"{message}\" with title \"{title}\"'")
        return await self.run_shell(f'notify-send "{title}" "{message}"')

    async def screenshot(self, path: str) -> Any:
        from PIL import ImageGrab

        image = ImageGrab.grab()
        image.save(path)
        return {"path": path}

    async def keyboard_mouse(self, action: str, **kwargs) -> Any:
        import pyautogui

        if action == "type":
            pyautogui.write(kwargs.get("text", ""))
        elif action == "press":
            pyautogui.press(kwargs.get("key", "enter"))
        elif action == "move":
            pyautogui.moveTo(kwargs.get("x", 0), kwargs.get("y", 0))
        elif action == "click":
            pyautogui.click(kwargs.get("x"), kwargs.get("y"))
        elif action == "scroll":
            pyautogui.scroll(kwargs.get("amount", 0))
        return {"action": action}

    async def audio_control(self, action: str, value: int | None = None) -> Any:
        if platform.system() != "Windows":
            return {"error": "Audio control not implemented on this platform"}
        if action == "mute":
            return await self.run_shell("powershell -Command \"(New-Object -ComObject WScript.Shell).SendKeys([char]173)\"")
        return {"status": action, "value": value}

    async def power_management(self, action: str, confirm: bool = False) -> Any:
        self._check_policy(action, confirm)
        commands = {
            "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            "hibernate": "shutdown /h",
            "restart": "shutdown /r /t 0",
            "shutdown": "shutdown /s /t 0",
        }
        return await self.run_shell(commands[action])
