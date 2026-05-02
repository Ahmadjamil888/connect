from __future__ import annotations

from typing import Any

from imos.adapters.webapps.common import BaseWebAdapter


class Microsoft365Adapter(BaseWebAdapter):
    def __init__(self, name: str = "microsoft365", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["outlook", "onedrive", "word", "excel", "sharepoint"])
        self.client_id = (config or {}).get("MS365_CLIENT_ID", "")
        self.client_secret = (config or {}).get("MS365_CLIENT_SECRET", "")
        self.tenant_id = (config or {}).get("MS365_TENANT_ID", "")
