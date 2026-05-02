from __future__ import annotations

from typing import Any

from imos.adapters.webapps.common import BaseWebAdapter


class ZapierAdapter(BaseWebAdapter):
    def __init__(self, name: str = "zapier", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["trigger_webhook"])
        self.webhooks = (config or {}).get("webhooks", [])

    async def trigger_webhook(self, name: str, payload: dict[str, Any]) -> Any:
        endpoint = next(item["url"] for item in self.webhooks if item["name"] == name)
        return await self._request("POST", endpoint, payload=payload)
