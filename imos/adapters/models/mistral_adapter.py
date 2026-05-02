from __future__ import annotations

from typing import Any

from imos.adapters.models.common import OpenAICompatibleMixin


class MistralAdapter(OpenAICompatibleMixin):
    supported_models = ["mistral-large", "mistral-medium", "mistral-small", "mistral-7b", "codestral"]

    def __init__(self, name: str = "mistral", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, provider_name="mistral", config=config, default_model="mistral-large")
        self.base_url = "https://api.mistral.ai/v1"
        self.api_key = (config or {}).get("MISTRAL_API_KEY") or (config or {}).get("api_key", "")
