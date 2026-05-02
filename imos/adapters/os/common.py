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
            handler = getattr(self, str(action), None)
            if handler is None:
                raise AttributeError(f"Unsupported OS action: {action}")
            result = await handler(**task.metadata.get("params", {}))
            return IMOSResult(task.task_id, self.name, True, output=result, duration_ms=int((time.perf_counter() - started) * 1000))
        except Exception as exc:
            return IMOSResult(task.task_id, self.name, False, error=str(exc), duration_ms=int((time.perf_counter() - started) * 1000))
