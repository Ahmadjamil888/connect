from __future__ import annotations

import time
from typing import Any

import aiohttp

from imos.adapters.base import IMOSAdapter
from imos.models import IMOSResult, IMOSTask


class BaseVCSAdapter(IMOSAdapter):
    def __init__(self, name: str, config: dict[str, Any] | None = None, capabilities: list[str] | None = None) -> None:
        super().__init__(name=name, adapter_type="vcs", capabilities=capabilities or ["repo", "files", "commits", "branches", "pull_requests", "issues"], config=config)
        self.session: aiohttp.ClientSession | None = None

    async def connect(self) -> bool:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        self.status = "connected"
        return True

    async def disconnect(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
        self.status = "disconnected"

    async def get_capabilities(self) -> list[str]:
        return list(self.capabilities)

    async def send(self, task: IMOSTask) -> IMOSResult:
        started = time.perf_counter()
        action = task.metadata.get("action") or task.subtask_type
        try:
            handler = getattr(self, str(action), None)
            if handler is None:
                raise AttributeError(f"Unsupported VCS action: {action}")
            result = await handler(**task.metadata.get("params", {}))
            return IMOSResult(task.task_id, self.name, True, output=result, duration_ms=int((time.perf_counter() - started) * 1000))
        except Exception as exc:
            return IMOSResult(task.task_id, self.name, False, error=str(exc), duration_ms=int((time.perf_counter() - started) * 1000))
