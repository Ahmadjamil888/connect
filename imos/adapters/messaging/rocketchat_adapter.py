from __future__ import annotations

from typing import Any

from imos.adapters.messaging.common import BaseMessagingAdapter


class RocketchatAdapter(BaseMessagingAdapter):
    def __init__(self, name: str = "rocketchat", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.url = ((config or {}).get("ROCKETCHAT_URL") or "").rstrip("/")
        self.user_id = (config or {}).get("ROCKETCHAT_USER_ID", "")
        self.auth_token = (config or {}).get("ROCKETCHAT_AUTH_TOKEN", "")
        self.channel = (config or {}).get("ROCKETCHAT_CHANNEL", "")

    async def health_check(self) -> bool:
        return bool(self.url and self.auth_token and self.user_id)

    async def send_message(self, message: str, channel: str | None = None) -> Any:
        headers = {"X-Auth-Token": self.auth_token, "X-User-Id": self.user_id}
        return await self._post_json(f"{self.url}/api/v1/chat.postMessage", {"channel": channel or self.channel, "text": message}, headers=headers)
