from __future__ import annotations

import asyncio
import base64
import mimetypes
import time
from pathlib import Path
from typing import Any

import aiohttp

from imos.adapters.base import IMOSAdapter
from imos.models import IMOSResult, IMOSTask


class BaseMessagingAdapter(IMOSAdapter):
    def __init__(self, name: str, config: dict[str, Any] | None = None, capabilities: list[str] | None = None) -> None:
        super().__init__(
            name=name,
            adapter_type="messaging",
            capabilities=capabilities or ["send_message", "format_code_blocks", "send_file", "send_image", "receive_message"],
            config=config,
        )
        self.session: aiohttp.ClientSession | None = None
        self.received_callbacks: list[Any] = []

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
        action = str(task.metadata.get("action") or task.subtask_type or "send_message").lower()
        try:
            if action == "send_file":
                output = await self.send_file(task.metadata["path"], caption=task.prompt)
            elif action == "send_image":
                output = await self.send_image(task.metadata["path"], caption=task.prompt)
            elif action == "fetch_messages":
                output = await self.fetch_messages()
            elif action == "webhook_event":
                output = await self.handle_incoming_event(task.metadata)
            else:
                output = await self.send_message(task.prompt, channel=task.metadata.get("channel"))
            return IMOSResult(task.task_id, self.name, True, output=output, duration_ms=int((time.perf_counter() - started) * 1000))
        except Exception as exc:
            self.status = "error"
            return IMOSResult(task.task_id, self.name, False, error=str(exc), duration_ms=int((time.perf_counter() - started) * 1000))

    async def send_message(self, message: str, channel: str | None = None) -> Any:
        raise NotImplementedError

    async def send_file(self, path: str, caption: str | None = None) -> Any:
        payload = self._read_file_payload(path)
        return await self.send_message(f"{caption or ''}\n[file:{payload['filename']} size={len(payload['content'])}]".strip())

    async def send_image(self, path: str, caption: str | None = None) -> Any:
        payload = self._read_file_payload(path)
        return await self.send_message(f"{caption or ''}\n[image:{payload['filename']} size={len(payload['content'])}]".strip())

    async def fetch_messages(self) -> Any:
        return []

    async def handle_incoming_event(self, payload: dict[str, Any]) -> Any:
        for callback in self.received_callbacks:
            maybe = callback(payload)
            if hasattr(maybe, "__await__"):
                await maybe
        return payload

    async def on_event(self, event_type: str, callback) -> None:
        if event_type == "message":
            self.received_callbacks.append(callback)
        else:
            await super().on_event(event_type, callback)

    def format_code_block(self, content: str, language: str = "") -> str:
        return f"```{language}\n{content}\n```"

    def _read_file_payload(self, path: str) -> dict[str, Any]:
        file_path = Path(path).resolve()
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        raw = file_path.read_bytes()
        return {
            "filename": file_path.name,
            "mime_type": mime_type,
            "content": base64.b64encode(raw).decode("ascii"),
            "bytes": raw,
        }

    async def _post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> Any:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        async with self.session.post(url, json=payload, headers=headers or {}, timeout=aiohttp.ClientTimeout(total=60)) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            return await response.json() if "json" in content_type else await response.text()

    async def _get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        async with self.session.get(url, headers=headers or {}, timeout=aiohttp.ClientTimeout(total=60)) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            return await response.json() if "json" in content_type else await response.text()
