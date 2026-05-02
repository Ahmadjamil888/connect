from __future__ import annotations

from typing import Any

from imos.adapters.models.common import OpenAICompatibleMixin


class OpenrouterAdapter(OpenAICompatibleMixin):
    def __init__(self, name: str = "openrouter", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, provider_name="openrouter", config=config, default_model="mistralai/mistral-7b-instruct")
        self.base_url = "https://openrouter.ai/api/v1"
        self.api_key = (config or {}).get("OPENROUTER_API_KEY") or (config or {}).get("api_key", "")
        self.default_headers = {"HTTP-Referer": "https://local.imos", "X-Title": "IMOS"}
