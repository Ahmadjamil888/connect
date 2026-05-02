from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.webapps.common import BaseWebAdapter


class TrelloAdapter(BaseWebAdapter):
    def __init__(self, name: str = "trello", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["boards", "lists", "cards", "members", "labels", "checklists"])
        self.api_key = (config or {}).get("TRELLO_API_KEY", "")
        self.api_secret = (config or {}).get("TRELLO_API_SECRET", "")
        self.token = (config or {}).get("TRELLO_TOKEN", "")
