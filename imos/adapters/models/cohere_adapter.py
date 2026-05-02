from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.models.common import AsyncModelAdapter


class CohereAdapter(AsyncModelAdapter):
    supported_models = ["command-r-plus", "command-r", "command"]

    def __init__(self, name: str = "cohere", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, provider_name="cohere", config=config, default_model="command-r-plus")
        self.client = None

    async def connect(self) -> bool:
        try:
            import cohere
        except ModuleNotFoundError:
            self.status = "error"
            return False
        self.client = cohere.ClientV2(api_key=(self.config or {}).get("COHERE_API_KEY") or (self.config or {}).get("api_key"))
        return await self.health_check()

    async def health_check(self) -> bool:
        return self.client is not None

    async def _perform_request(self, task, stream: bool, callback):
        if self.client is None and not await self.connect():
            raise RuntimeError("Cohere client unavailable")
        messages = [{"role": "user", "content": task.prompt}]
        if self._system_prompt(task):
            messages.insert(0, {"role": "system", "content": self._system_prompt(task)})
        response = await asyncio.to_thread(
            self.client.chat,
            model=self._selected_model(task),
            messages=messages,
            temperature=self._temperature(task),
            max_tokens=self._max_tokens(task),
        )
        text = getattr(response, "text", "") or getattr(response.message, "content", "")
        if isinstance(text, list):
            text = "".join(getattr(block, "text", "") for block in text)
        if stream:
            for token in str(text).split():
                await self._invoke_callback(callback, token + " ")
        usage = getattr(response, "usage", None)
        return {
            "output": str(text),
            "metadata": self._usage(
                prompt_tokens=int(getattr(getattr(usage, "tokens", None), "input_tokens", 0)),
                completion_tokens=int(getattr(getattr(usage, "tokens", None), "output_tokens", 0)),
            ),
        }
