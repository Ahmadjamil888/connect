from __future__ import annotations

from typing import Any

from imos.adapters.models.common import AsyncModelAdapter


class HuggingfaceAdapter(AsyncModelAdapter):
    def __init__(self, name: str = "huggingface", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, provider_name="huggingface", config=config, default_model=(config or {}).get("model_id", "gpt2"))
        self.api_key = (config or {}).get("HUGGINGFACE_API_KEY") or (config or {}).get("api_key", "")
        self.base_url = "https://api-inference.huggingface.co/models"

    async def health_check(self) -> bool:
        try:
            await self._post_json(f"{self.base_url}/{self.default_model}", {"inputs": "ping"})
            self.status = "connected"
            return True
        except Exception:
            self.status = "error"
            return False

    async def _perform_request(self, task, stream: bool, callback):
        payload = {"inputs": task.prompt, "parameters": {"temperature": self._temperature(task), "max_new_tokens": self._max_tokens(task)}}
        data = await self._retry(self._post_json, f"{self.base_url}/{self._selected_model(task) or self.default_model}", payload)
        if isinstance(data, list):
            output = data[0].get("generated_text", "") if data and isinstance(data[0], dict) else str(data)
        elif isinstance(data, dict):
            output = data.get("generated_text") or data.get("summary_text") or data.get("label") or str(data)
        else:
            output = str(data)
        if stream:
            for token in output.split():
                await self._invoke_callback(callback, token + " ")
        return {"output": output, "metadata": self._usage()}

    async def _post_json(self, url: str, payload: dict[str, Any]):
        import aiohttp

        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with self.session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as response:
            response.raise_for_status()
            return await response.json()
