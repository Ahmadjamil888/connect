from __future__ import annotations

from typing import Any

from imos.adapters.models.common import AsyncModelAdapter


class OllamaAdapter(AsyncModelAdapter):
    def __init__(self, name: str = "ollama", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, provider_name="ollama", config=config, default_model="llama3")
        host = ((config or {}).get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
        self.base_url = host if host.startswith("http") else f"http://{host}"
        self.available_models: list[str] = []

    async def health_check(self) -> bool:
        try:
            data = await self._get_json(f"{self.base_url}/api/tags")
            self.available_models = [item.get("name", "") for item in data.get("models", [])]
            self.status = "connected"
            return True
        except Exception:
            self.status = "disconnected"
            self.available_models = []
            return False

    async def _perform_request(self, task, stream: bool, callback):
        await self.connect()
        payload = {
            "model": self._selected_model(task) or self.default_model,
            "prompt": task.prompt,
            "system": self._system_prompt(task) or "",
            "stream": stream,
            "options": {"temperature": self._temperature(task)},
        }
        if stream:
            async with await self._request("POST", f"{self.base_url}/api/generate", json=payload) as response:
                chunks: list[str] = []
                async for raw_line in response.content:
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    chunk = __import__("json").loads(line)
                    token = chunk.get("response", "")
                    if token:
                        chunks.append(token)
                        await self._invoke_callback(callback, token)
                return {"output": "".join(chunks), "metadata": self._usage()}
        data = await self._post_json(f"{self.base_url}/api/generate", payload)
        return {"output": data.get("response", ""), "metadata": self._usage()}

    async def _request(self, method: str, url: str, **kwargs):
        import aiohttp

        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        response = await self.session.request(method, url, timeout=aiohttp.ClientTimeout(total=120), **kwargs)
        response.raise_for_status()
        return response

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with await self._request("POST", url, json=payload) as response:
            return await response.json()

    async def _get_json(self, url: str) -> dict[str, Any]:
        async with await self._request("GET", url) as response:
            return await response.json()
