from __future__ import annotations

import abc
from typing import Any, Awaitable, Callable

from imos.models import IMOSResult, IMOSTask


class IMOSAdapter(abc.ABC):
    allowed_adapter_types = {
        "model",
        "ide",
        "messaging",
        "meeting",
        "tool",
        "payment",
        "webapp",
        "vcs",
        "browser",
        "os",
    }

    def __init__(
        self,
        name: str,
        adapter_type: str,
        capabilities: list[str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        if adapter_type not in self.allowed_adapter_types:
            raise ValueError(f"Unsupported adapter type: {adapter_type}")
        self.name = name
        self.adapter_type = adapter_type
        self.capabilities = capabilities or []
        self.status = "disconnected"
        self.config = config or {}
        self._event_callbacks: dict[str, list[Callable[..., Awaitable[None]]]] = {}

    @abc.abstractmethod
    async def connect(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    async def disconnect(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def send(self, task: IMOSTask) -> IMOSResult:
        raise NotImplementedError

    @abc.abstractmethod
    async def health_check(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_capabilities(self) -> list[str]:
        raise NotImplementedError

    async def stream(
        self,
        task: IMOSTask,
        callback: Callable[[str], Awaitable[None]] | Callable[[str], None],
    ) -> IMOSResult:
        result = await self.send(task)
        if result.output is not None:
            maybe = callback(str(result.output))
            if hasattr(maybe, "__await__"):
                await maybe
        return result

    async def on_event(
        self,
        event_type: str,
        callback: Callable[..., Awaitable[None]],
    ) -> None:
        self._event_callbacks.setdefault(event_type, []).append(callback)

    async def emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        for callback in self._event_callbacks.get(event_type, []):
            await callback(payload)
