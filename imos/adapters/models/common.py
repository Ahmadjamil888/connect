from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import aiohttp

from imos.adapters.base import IMOSAdapter
from imos.models import IMOSResult, IMOSTask


class AsyncModelAdapter(IMOSAdapter):
    def __init__(
        self,
        name: str,
        provider_name: str,
        config: dict[str, Any] | None = None,
        capabilities: list[str] | None = None,
        default_model: str | None = None,
    ) -> None:
        super().__init__(
            name=name,
            adapter_type="model",
            capabilities=capabilities
            or ["chat", "stream", "vision", "tool_use", "system_prompt_injection", "model_selection"],
            config=config,
        )
        self.provider_name = provider_name
        self.default_model = default_model
        self.session: aiohttp.ClientSession | None = None

    async def connect(self) -> bool:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        healthy = await self.health_check()
        self.status = "connected" if healthy else "error"
        return healthy

    async def disconnect(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
        self.status = "disconnected"

    async def get_capabilities(self) -> list[str]:
        return list(self.capabilities)

    async def send(self, task: IMOSTask) -> IMOSResult:
        started = time.perf_counter()
        try:
            payload = await self._perform_request(task, stream=False, callback=None)
            return IMOSResult(
                task_id=task.task_id,
                adapter_name=self.name,
                success=True,
                output=payload.get("output"),
                duration_ms=int((time.perf_counter() - started) * 1000),
                metadata=payload.get("metadata", {}),
            )
        except Exception as exc:
            self.status = "error"
            return IMOSResult(
                task_id=task.task_id,
                adapter_name=self.name,
                success=False,
                output=None,
                error=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
                metadata={"provider": self.provider_name},
            )

    async def stream(self, task: IMOSTask, callback) -> IMOSResult:
        started = time.perf_counter()
        try:
            payload = await self._perform_request(task, stream=True, callback=callback)
            return IMOSResult(
                task_id=task.task_id,
                adapter_name=self.name,
                success=True,
                output=payload.get("output"),
                duration_ms=int((time.perf_counter() - started) * 1000),
                metadata=payload.get("metadata", {}),
            )
        except Exception as exc:
            self.status = "error"
            return IMOSResult(
                task_id=task.task_id,
                adapter_name=self.name,
                success=False,
                output=None,
                error=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
                metadata={"provider": self.provider_name},
            )

    async def _perform_request(self, task: IMOSTask, stream: bool, callback) -> dict[str, Any]:
        raise NotImplementedError

    async def _invoke_callback(self, callback, token: str) -> None:
        maybe = callback(token)
        if hasattr(maybe, "__await__"):
            await maybe

    def _system_prompt(self, task: IMOSTask) -> str | None:
        return str(task.metadata.get("system_prompt") or task.context.get("system_prompt") or "").strip() or None

    def _selected_model(self, task: IMOSTask) -> str:
        return (
            str(task.metadata.get("model") or task.context.get("model") or self.config.get("model") or self.default_model or "")
            .strip()
        )

    def _temperature(self, task: IMOSTask, default: float = 0.2) -> float:
        value = task.metadata.get("temperature")
        if value is None:
            value = task.context.get("temperature")
        if value is None:
            value = self.config.get("temperature")
        if value in (None, ""):
            value = default
        return float(value)

    def _max_tokens(self, task: IMOSTask, default: int = 1024) -> int:
        value = task.metadata.get("max_tokens")
        if value is None:
            value = task.context.get("max_tokens")
        if value is None:
            value = self.config.get("max_tokens")
        if value in (None, ""):
            value = default
        return int(value)

    def _images(self, task: IMOSTask) -> list[Any]:
        images = task.metadata.get("images") or task.context.get("images") or []
        return images if isinstance(images, list) else []

    def _tools(self, task: IMOSTask) -> list[dict[str, Any]]:
        tools = task.metadata.get("tools") or task.context.get("tools") or []
        return tools if isinstance(tools, list) else []

    def _usage(self, prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int | None = None) -> dict[str, Any]:
        total = total_tokens if total_tokens is not None else prompt_tokens + completion_tokens
        return {
            "provider": self.provider_name,
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total,
            },
        }

    async def _retry(self, func, *args, **kwargs):
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                last_error = exc
                if attempt == 2:
                    break
                await asyncio.sleep(2**attempt)
        raise RuntimeError(str(last_error) if last_error else "request failed")


class OpenAICompatibleMixin(AsyncModelAdapter):
    base_url: str
    api_key: str
    auth_header: str = "Authorization"
    auth_prefix: str = "Bearer "
    default_headers: dict[str, str] = {}

    async def health_check(self) -> bool:
        try:
            await self._get_json(f"{self.base_url.rstrip('/')}/models")
            self.status = "connected"
            return True
        except Exception:
            try:
                await self._get_json(f"{self.base_url.rstrip('/')}/tags")
                self.status = "connected"
                return True
            except Exception:
                self.status = "error"
                return False

    async def _perform_request(self, task: IMOSTask, stream: bool, callback) -> dict[str, Any]:
        payload = {
            "model": self._selected_model(task),
            "messages": self._build_messages(task),
            "temperature": self._temperature(task),
            "max_tokens": self._max_tokens(task),
            "stream": stream,
        }
        tools = self._tools(task)
        if tools:
            payload["tools"] = tools

        if stream:
            return await self._retry(self._stream_chat, payload, callback)
        return await self._retry(self._chat, payload)

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.default_headers}
        if self.api_key:
            headers[self.auth_header] = f"{self.auth_prefix}{self.api_key}".strip()
        return headers

    def _build_messages(self, task: IMOSTask) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        system_prompt = self._system_prompt(task)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        images = self._images(task)
        if images:
            content: list[dict[str, Any]] = [{"type": "text", "text": task.prompt}]
            for image in images:
                if isinstance(image, dict) and image.get("image_url"):
                    content.append({"type": "image_url", "image_url": {"url": image["image_url"]}})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": task.prompt})
        return messages

    async def _chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = await self._post_json(f"{self.base_url.rstrip('/')}/chat/completions", payload)
        output = data["choices"][0]["message"].get("content", "")
        usage = data.get("usage", {})
        return {
            "output": output,
            "metadata": self._usage(
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                total_tokens=int(usage.get("total_tokens", 0) or 0),
            )
            | {"raw_response": data},
        }

    async def _stream_chat(self, payload: dict[str, Any], callback) -> dict[str, Any]:
        aggregated: list[str] = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        async with await self._request("POST", f"{self.base_url.rstrip('/')}/chat/completions", json=payload) as response:
            async for raw_line in response.content:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                chunk = json.loads(data_str)
                choice = (chunk.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                token = delta.get("content") or ""
                if token:
                    aggregated.append(token)
                    await self._invoke_callback(callback, token)
                if chunk.get("usage"):
                    usage = chunk["usage"]
        return {
            "output": "".join(aggregated),
            "metadata": self._usage(
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                total_tokens=int(usage.get("total_tokens", 0) or 0),
            ),
        }

    async def _request(self, method: str, url: str, **kwargs):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        response = await self.session.request(method, url, headers=self._build_headers(), timeout=aiohttp.ClientTimeout(total=120), **kwargs)
        response.raise_for_status()
        return response

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with await self._request("POST", url, json=payload) as response:
            return await response.json()

    async def _get_json(self, url: str) -> dict[str, Any]:
        async with await self._request("GET", url) as response:
            return await response.json()
