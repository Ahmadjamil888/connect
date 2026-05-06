from __future__ import annotations

import time
from typing import Any

import aiohttp

from imos.adapters.base import IMOSAdapter
from imos.models import IMOSResult, IMOSTask


class BaseWebAdapter(IMOSAdapter):
    def __init__(self, name: str, config: dict[str, Any] | None = None, capabilities: list[str] | None = None) -> None:
        super().__init__(name=name, adapter_type="webapp", capabilities=capabilities or ["create", "read", "update", "delete", "search"], config=config)
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

    async def health_check(self) -> bool:
        return True

    async def get_capabilities(self) -> list[str]:
        return list(self.capabilities)

    async def send(self, task: IMOSTask) -> IMOSResult:
        started = time.perf_counter()
        action = task.metadata.get("action") or task.subtask_type
        try:
            params = dict(task.metadata.get("params", {}) or {})
            aliases = {
                "search": "search_web",
                "web_search": "search_web",
                "browser_action": "navigate",
                "open_website": "navigate",
            }
            handler_name = aliases.get(str(action), str(action))
            if handler_name == "navigate" and not params.get("url"):
                prompt = str(task.prompt or "").strip()
                if prompt.startswith(("http://", "https://")):
                    params["url"] = prompt
                elif prompt.lower().startswith("www."):
                    params["url"] = f"https://{prompt}"
                else:
                    params["url"] = "https://www.google.com"
            handler = getattr(self, handler_name, None)
            if handler is None:
                raise AttributeError(f"Unsupported webapp action: {action}")
            result = await handler(**params)
            return IMOSResult(task.task_id, self.name, True, output=result, duration_ms=int((time.perf_counter() - started) * 1000))
        except Exception as exc:
            return IMOSResult(task.task_id, self.name, False, error=str(exc), duration_ms=int((time.perf_counter() - started) * 1000))

    async def _request(self, method: str, url: str, payload: Any = None, headers: dict[str, str] | None = None, data: Any = None) -> Any:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        async with self.session.request(method, url, json=payload, data=data, headers=headers or {}, timeout=aiohttp.ClientTimeout(total=120)) as response:
            if response.status >= 400:
                raise RuntimeError(await response.text())
            content_type = response.headers.get("Content-Type", "")
            return await response.json() if "json" in content_type else await response.text()
