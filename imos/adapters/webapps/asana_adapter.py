from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.webapps.common import BaseWebAdapter


class AsanaAdapter(BaseWebAdapter):
    def __init__(self, name: str = "asana", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["tasks", "projects", "workspaces", "portfolios"])
        self.access_token = (config or {}).get("ASANA_ACCESS_TOKEN", "")
        self.workspace_id = (config or {}).get("ASANA_WORKSPACE_ID", "")
