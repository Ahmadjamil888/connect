from __future__ import annotations

from typing import Any

from imos.adapters.models.common import OpenAICompatibleMixin


class LmstudioAdapter(OpenAICompatibleMixin):
    def __init__(self, name: str = "lmstudio", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, provider_name="lmstudio", config=config, default_model=(config or {}).get("model", "local-model"))
        host = ((config or {}).get("LMSTUDIO_HOST") or "http://localhost:1234").rstrip("/")
        self.base_url = f"{host}/v1" if not host.endswith("/v1") else host
        self.api_key = (config or {}).get("api_key", "lmstudio")
        self.available_models: list[str] = []

    async def health_check(self) -> bool:
        try:
            data = await self._get_json(f"{self.base_url}/models")
            self.available_models = [item.get("id", "") for item in data.get("data", [])]
            self.status = "connected"
            return True
        except Exception:
            self.status = "disconnected"
            return False
