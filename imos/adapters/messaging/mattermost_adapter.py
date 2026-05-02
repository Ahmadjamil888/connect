from __future__ import annotations

from typing import Any

from imos.adapters.messaging.common import BaseMessagingAdapter


class MattermostAdapter(BaseMessagingAdapter):
    def __init__(self, name: str = "mattermost", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.url = ((config or {}).get("MATTERMOST_URL") or "").rstrip("/")
        self.token = (config or {}).get("MATTERMOST_TOKEN", "")
        self.channel_id = (config or {}).get("MATTERMOST_CHANNEL_ID", "")

    async def health_check(self) -> bool:
        return bool(self.url and self.token)

    async def send_message(self, message: str, channel: str | None = None) -> Any:
        return await self._post_json(
            f"{self.url}/api/v4/posts",
            {"channel_id": channel or self.channel_id, "message": message},
            headers={"Authorization": f"Bearer {self.token}"},
        )
