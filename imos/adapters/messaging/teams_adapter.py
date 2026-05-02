from __future__ import annotations

from typing import Any

import aiohttp

from imos.adapters.messaging.common import BaseMessagingAdapter


class TeamsAdapter(BaseMessagingAdapter):
    def __init__(self, name: str = "teams", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.client_id = (config or {}).get("TEAMS_CLIENT_ID", "")
        self.client_secret = (config or {}).get("TEAMS_CLIENT_SECRET", "")
        self.tenant_id = (config or {}).get("TEAMS_TENANT_ID", "")
        self.channel_id = (config or {}).get("TEAMS_CHANNEL_ID", "")
        self.team_id = (config or {}).get("TEAMS_TEAM_ID", "")
        self._access_token = ""

    async def connect(self) -> bool:
        await super().connect()
        self._access_token = await self._token()
        self.status = "connected" if self._access_token else "error"
        return bool(self._access_token)

    async def health_check(self) -> bool:
        return bool(self._access_token or await self.connect())

    async def send_message(self, message: str, channel: str | None = None) -> Any:
        token = self._access_token or await self._token()
        url = f"https://graph.microsoft.com/v1.0/teams/{self.team_id}/channels/{channel or self.channel_id}/messages"
        payload = {"body": {"contentType": "html", "content": message.replace("\n", "<br/>")}}
        return await self._post_json(url, payload, headers={"Authorization": f"Bearer {token}"})

    async def _token(self) -> str:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        async with self.session.post(
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
            data=data,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as response:
            response.raise_for_status()
            payload = await response.json()
            return payload.get("access_token", "")
