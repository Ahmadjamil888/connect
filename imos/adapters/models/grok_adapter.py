from __future__ import annotations

from typing import Any

from imos.adapters.models.common import OpenAICompatibleMixin


class GrokAdapter(OpenAICompatibleMixin):
    supported_models = ["grok-2", "grok-beta"]

    def __init__(self, name: str = "grok", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, provider_name="xai", config=config, default_model="grok-2")
        self.base_url = "https://api.x.ai/v1"
        self.api_key = (config or {}).get("XAI_API_KEY") or (config or {}).get("api_key", "")
