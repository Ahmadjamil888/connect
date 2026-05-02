from __future__ import annotations

from typing import Any

from imos.adapters.models.common import AsyncModelAdapter


class OpenAIAdapter(AsyncModelAdapter):
    supported_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1", "o1-mini", "o3-mini"]

    def __init__(self, name: str = "openai", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, provider_name="openai", config=config, default_model="gpt-4o")
        self.client = None

    async def connect(self) -> bool:
        try:
            from openai import AsyncOpenAI
        except ModuleNotFoundError:
            self.status = "error"
            return False
        self.client = AsyncOpenAI(api_key=(self.config or {}).get("OPENAI_API_KEY") or (self.config or {}).get("api_key"))
        return await self.health_check()

    async def health_check(self) -> bool:
        if self.client is None:
            return False
        try:
            await self.client.models.list()
            self.status = "connected"
            return True
        except Exception:
            self.status = "error"
            return False

    async def _perform_request(self, task, stream: bool, callback):
        if self.client is None and not await self.connect():
            raise RuntimeError("OpenAI client unavailable")
        payload = {
            "model": self._selected_model(task),
            "messages": self._build_messages(task),
            "max_tokens": self._max_tokens(task),
        }
        if payload["model"] not in {"o1", "o1-mini", "o3-mini"}:
            payload["temperature"] = self._temperature(task)
        tools = self._tools(task)
        if tools:
            payload["tools"] = tools
        if stream:
            response = await self._retry(self.client.chat.completions.create, **payload, stream=True)
            chunks: list[str] = []
            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                token = getattr(delta, "content", None) or ""
                if token:
                    chunks.append(token)
                    await self._invoke_callback(callback, token)
            return {"output": "".join(chunks), "metadata": self._usage()}
        response = await self._retry(self.client.chat.completions.create, **payload)
        usage = getattr(response, "usage", None)
        return {
            "output": response.choices[0].message.content if response.choices else "",
            "metadata": self._usage(
                prompt_tokens=int(getattr(usage, "prompt_tokens", 0)),
                completion_tokens=int(getattr(usage, "completion_tokens", 0)),
                total_tokens=int(getattr(usage, "total_tokens", 0)),
            ),
        }

    def _build_messages(self, task) -> list[dict[str, Any]]:
        system_prompt = self._system_prompt(task)
        images = self._images(task)
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if images:
            content: list[dict[str, Any]] = [{"type": "text", "text": task.prompt}]
            for image in images:
                if isinstance(image, dict) and image.get("image_url"):
                    content.append({"type": "image_url", "image_url": {"url": image["image_url"]}})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": task.prompt})
        return messages
