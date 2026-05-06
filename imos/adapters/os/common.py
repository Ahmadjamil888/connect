from __future__ import annotations

import time
from typing import Any

from imos.adapters.base import IMOSAdapter
from imos.models import IMOSResult, IMOSTask


class BaseOSAdapter(IMOSAdapter):
    def __init__(self, name: str, config: dict[str, Any] | None = None, capabilities: list[str] | None = None) -> None:
        super().__init__(name=name, adapter_type="os", capabilities=capabilities or [], config=config)

    async def connect(self) -> bool:
        self.status = "connected"
        return True

    async def disconnect(self) -> None:
        self.status = "disconnected"

    async def get_capabilities(self) -> list[str]:
        return list(self.capabilities)

    async def send(self, task: IMOSTask) -> IMOSResult:
        started = time.perf_counter()
        action = task.metadata.get("action") or task.subtask_type
        try:
            params = dict(task.metadata.get("params", {}) or {})
            if not params and isinstance(task.metadata, dict):
                for key in ("command", "cwd", "timeout", "url", "path", "pattern"):
                    if key in task.metadata and task.metadata.get(key) is not None:
                        params[key] = task.metadata.get(key)
            aliases = {
                "shell_command": "run_shell",
                "terminal": "run_shell",
                "powershell": "run_shell",
                "command_line": "run_shell",
                "browser_action": "open_browser",
            }
            action = aliases.get(str(action), action)
            handler = getattr(self, str(action), None)
            if handler is None:
                raise AttributeError(f"Unsupported OS action: {action}")
            if str(action) == "run_shell" and not params.get("command"):
                params["command"] = task.prompt.strip()
            result = await handler(**params)
            return IMOSResult(task.task_id, self.name, True, output=result, duration_ms=int((time.perf_counter() - started) * 1000))
        except Exception as exc:
            return IMOSResult(task.task_id, self.name, False, error=str(exc), duration_ms=int((time.perf_counter() - started) * 1000))
