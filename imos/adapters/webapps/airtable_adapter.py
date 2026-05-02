from __future__ import annotations

from typing import Any

from imos.adapters.webapps.common import BaseWebAdapter


class AirtableAdapter(BaseWebAdapter):
    def __init__(self, name: str = "airtable", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.api_key = (config or {}).get("AIRTABLE_API_KEY", "")
        self.base_id = (config or {}).get("AIRTABLE_BASE_ID", "")

    async def create(self, table: str, fields: dict[str, Any]) -> Any:
        return await self._request("POST", f"https://api.airtable.com/v0/{self.base_id}/{table}", payload={"fields": fields}, headers={"Authorization": f"Bearer {self.api_key}"})

    async def read(self, table: str, record_id: str) -> Any:
        return await self._request("GET", f"https://api.airtable.com/v0/{self.base_id}/{table}/{record_id}", headers={"Authorization": f"Bearer {self.api_key}"})
