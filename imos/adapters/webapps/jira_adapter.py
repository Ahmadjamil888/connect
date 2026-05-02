from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.webapps.common import BaseWebAdapter


class JiraAdapter(BaseWebAdapter):
    def __init__(self, name: str = "jira", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["issues", "projects", "sprints", "boards", "transitions"])
        self.server = (config or {}).get("JIRA_SERVER", "")
        self.email = (config or {}).get("JIRA_EMAIL", "")
        self.token = (config or {}).get("JIRA_API_TOKEN", "")
        self.client = None

    async def connect(self) -> bool:
        try:
            from jira import JIRA
        except ModuleNotFoundError:
            self.status = "error"
            return False
        self.client = await asyncio.to_thread(JIRA, server=self.server, basic_auth=(self.email, self.token))
        self.status = "connected"
        return True
