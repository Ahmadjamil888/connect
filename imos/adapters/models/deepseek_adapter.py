from __future__ import annotations

from typing import Any

from imos.adapters.models.common import OpenAICompatibleMixin


class DeepseekAdapter(OpenAICompatibleMixin):
    supported_models = ["deepseek-chat", "deepseek-coder"]

    def __init__(self, name: str = "deepseek", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, provider_name="deepseek", config=config, default_model="deepseek-chat")
        self.base_url = "https://api.deepseek.com/v1"
        self.api_key = (config or {}).get("DEEPSEEK_API_KEY") or (config or {}).get("api_key", "")
