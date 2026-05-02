from __future__ import annotations

from typing import Any

from imos.adapters.webapps.common import BaseWebAdapter


class NotionAdapter(BaseWebAdapter):
    def __init__(self, name: str = "notion", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.api_key = (config or {}).get("NOTION_API_KEY", "")
        self.database_id = (config or {}).get("NOTION_DATABASE_ID", "")

    async def create(self, parent_id: str, title: str, content: str) -> Any:
        headers = {"Authorization": f"Bearer {self.api_key}", "Notion-Version": "2022-06-28"}
        payload = {"parent": {"database_id": parent_id or self.database_id}, "properties": {"title": {"title": [{"text": {"content": title}}]}}, "children": [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]}}]}
        return await self._request("POST", "https://api.notion.com/v1/pages", payload=payload, headers=headers)

    async def search(self, query: str) -> Any:
        headers = {"Authorization": f"Bearer {self.api_key}", "Notion-Version": "2022-06-28"}
        return await self._request("POST", "https://api.notion.com/v1/search", payload={"query": query}, headers=headers)
