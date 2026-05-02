from __future__ import annotations

from typing import Any

from imos.adapters.webapps.common import BaseWebAdapter


class RestApiAdapter(BaseWebAdapter):
    def __init__(self, name: str = "rest_api", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["get", "post", "put", "patch", "delete"])
        self.base_url = ((config or {}).get("base_url") or "").rstrip("/")
        self.auth = (config or {}).get("auth", {})
        self.endpoints = (config or {}).get("endpoints", [])

    async def request(self, endpoint_name: str, params: dict[str, Any] | None = None) -> Any:
        endpoint = next(item for item in self.endpoints if item["name"] == endpoint_name)
        headers = dict((config or {}).get("headers", {})) if (config := self.config) else {}
        if self.auth.get("type") == "bearer":
            headers["Authorization"] = f"Bearer {self.auth['token']}"
        body = dict(endpoint.get("body_template", {}))
        body.update(params or {})
        return await self._request(endpoint["method"], f"{self.base_url}{endpoint['path']}", payload=body, headers=headers)
