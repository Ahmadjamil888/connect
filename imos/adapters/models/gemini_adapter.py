from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.models.common import AsyncModelAdapter


class GeminiAdapter(AsyncModelAdapter):
    supported_models = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro"]

    def __init__(self, name: str = "gemini", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, provider_name="gemini", config=config, default_model="gemini-2.0-flash")
        self.module = None

    async def connect(self) -> bool:
        try:
            import google.generativeai as genai
        except ModuleNotFoundError:
            self.status = "error"
            return False
        genai.configure(api_key=(self.config or {}).get("GOOGLE_GEMINI_API_KEY") or (self.config or {}).get("api_key"))
        self.module = genai
        return await self.health_check()

    async def health_check(self) -> bool:
        if self.module is None:
            return False
        try:
            await asyncio.to_thread(self.module.list_models)
            self.status = "connected"
            return True
        except Exception:
            self.status = "error"
            return False

    async def _perform_request(self, task, stream: bool, callback):
        if self.module is None and not await self.connect():
            raise RuntimeError("Gemini client unavailable")
        model = self.module.GenerativeModel(self._selected_model(task), system_instruction=self._system_prompt(task))
        content = [task.prompt]
        for image in self._images(task):
            if isinstance(image, dict) and image.get("image_url"):
                content.append(image["image_url"])
        if stream:
            response = await asyncio.to_thread(model.generate_content, content, stream=True)
            chunks: list[str] = []
            for chunk in response:
                token = getattr(chunk, "text", "") or ""
                if token:
                    chunks.append(token)
                    await self._invoke_callback(callback, token)
            return {"output": "".join(chunks), "metadata": self._usage()}
        response = await asyncio.to_thread(model.generate_content, content)
        usage = getattr(response, "usage_metadata", None)
        return {
            "output": getattr(response, "text", ""),
            "metadata": self._usage(
                prompt_tokens=int(getattr(usage, "prompt_token_count", 0)),
                completion_tokens=int(getattr(usage, "candidates_token_count", 0)),
                total_tokens=int(getattr(usage, "total_token_count", 0)),
            ),
        }
