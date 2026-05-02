from __future__ import annotations

from typing import Any

from imos.adapters.models.common import AsyncModelAdapter


class AnthropicAdapter(AsyncModelAdapter):
    supported_models = ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5", "claude-3-5-sonnet", "claude-3-opus"]

    def __init__(self, name: str = "anthropic", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, provider_name="anthropic", config=config, default_model="claude-sonnet-4-6")
        self.client = None

    async def connect(self) -> bool:
        try:
            from anthropic import AsyncAnthropic
        except ModuleNotFoundError:
            self.status = "error"
            return False
        api_key = (self.config or {}).get("ANTHROPIC_API_KEY") or (self.config or {}).get("api_key")
        self.client = AsyncAnthropic(api_key=api_key)
        return await self.health_check()

    async def health_check(self) -> bool:
        if self.client is None:
            return False
        try:
            await self.client.messages.create(
                model=self.default_model,
                max_tokens=16,
                messages=[{"role": "user", "content": "ping"}],
            )
            self.status = "connected"
            return True
        except Exception:
            self.status = "error"
            return False

    async def _perform_request(self, task, stream: bool, callback):
        if self.client is None and not await self.connect():
            raise RuntimeError("Anthropic client unavailable")
        payload = {
            "model": self._selected_model(task),
            "max_tokens": self._max_tokens(task),
            "messages": self._build_messages(task),
        }
        system_prompt = self._system_prompt(task)
        if system_prompt:
            payload["system"] = system_prompt
        tools = self._tools(task)
        if tools:
            payload["tools"] = tools
        if stream:
            chunks: list[str] = []
            async with self.client.messages.stream(**payload) as stream_response:
                async for text in stream_response.text_stream:
                    chunks.append(text)
                    await self._invoke_callback(callback, text)
                message = await stream_response.get_final_message()
            usage = getattr(message, "usage", None)
            return {
                "output": "".join(chunks),
                "metadata": self._usage(
                    prompt_tokens=int(getattr(usage, "input_tokens", 0)),
                    completion_tokens=int(getattr(usage, "output_tokens", 0)),
                ),
            }
        response = await self._retry(self.client.messages.create, **payload)
        usage = getattr(response, "usage", None)
        text_parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
        return {
            "output": "".join(text_parts),
            "metadata": self._usage(
                prompt_tokens=int(getattr(usage, "input_tokens", 0)),
                completion_tokens=int(getattr(usage, "output_tokens", 0)),
            ),
        }

    def _build_messages(self, task) -> list[dict[str, Any]]:
        images = self._images(task)
        if not images:
            return [{"role": "user", "content": task.prompt}]
        content: list[dict[str, Any]] = [{"type": "text", "text": task.prompt}]
        for image in images:
            if isinstance(image, dict) and image.get("base64"):
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image.get("media_type", "image/png"),
                            "data": image["base64"],
                        },
                    }
                )
        return [{"role": "user", "content": content}]
