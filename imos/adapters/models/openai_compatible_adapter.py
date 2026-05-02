from __future__ import annotations

from typing import Any

from imos.adapters.models.common import OpenAICompatibleMixin


class OpenAICompatibleAdapter(OpenAICompatibleMixin):
    def __init__(self, name: str = "openai_compatible", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, provider_name="openai_compatible", config=config, default_model=(config or {}).get("model", "gpt-4o-mini"))
        self.base_url = ((config or {}).get("base_url") or "http://localhost:8000/v1").rstrip("/")
        self.api_key = (config or {}).get("api_key", "")
