from __future__ import annotations

from typing import Any

from imos.adapters.webapps.common import BaseWebAdapter


class LinearAdapter(BaseWebAdapter):
    def __init__(self, name: str = "linear", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["issues", "projects", "cycles", "teams"])
        self.api_key = (config or {}).get("LINEAR_API_KEY", "")

    async def query(self, query: str, variables: dict[str, Any] | None = None) -> Any:
        return await self._request("POST", "https://api.linear.app/graphql", payload={"query": query, "variables": variables or {}}, headers={"Authorization": self.api_key})
