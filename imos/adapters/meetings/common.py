from __future__ import annotations

import time
from typing import Any

import aiohttp

from imos.adapters.base import IMOSAdapter
from imos.models import IMOSResult, IMOSTask


class BaseMeetingAdapter(IMOSAdapter):
    def __init__(self, name: str, config: dict[str, Any] | None = None, capabilities: list[str] | None = None) -> None:
        super().__init__(name=name, adapter_type="meeting", capabilities=capabilities or ["create_meeting", "list_meetings", "get_meeting", "cancel_meeting"], config=config)
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
            if action == "list_meetings":
                output = await self.list_meetings()
            elif action == "get_meeting":
                output = await self.get_meeting(task.metadata["meeting_id"])
            elif action == "cancel_meeting":
                output = await self.cancel_meeting(task.metadata["meeting_id"])
            else:
                output = await self.create_meeting(task.prompt, task.metadata)
            return IMOSResult(task.task_id, self.name, True, output=output, duration_ms=int((time.perf_counter() - started) * 1000))
        except Exception as exc:
            return IMOSResult(task.task_id, self.name, False, error=str(exc), duration_ms=int((time.perf_counter() - started) * 1000))

    async def create_meeting(self, prompt: str, metadata: dict[str, Any]) -> Any:
        raise NotImplementedError

    async def list_meetings(self) -> Any:
        raise NotImplementedError

    async def get_meeting(self, meeting_id: str) -> Any:
        raise NotImplementedError

    async def cancel_meeting(self, meeting_id: str) -> Any:
        raise NotImplementedError
