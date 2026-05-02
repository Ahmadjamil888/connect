from __future__ import annotations

import json
from typing import Any

from imos.adapters.messaging.common import BaseMessagingAdapter


class DiscordAdapter(BaseMessagingAdapter):
    def __init__(self, name: str = "discord", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.bot_token = (config or {}).get("DISCORD_BOT_TOKEN") or (config or {}).get("bot_token", "")
        self.channel_id = str((config or {}).get("DISCORD_CHANNEL_ID") or (config or {}).get("channel_id", ""))

    async def health_check(self) -> bool:
        try:
            await self._get_json("https://discord.com/api/v10/users/@me", headers={"Authorization": f"Bot {self.bot_token}"})
            self.status = "connected"
            return True
        except Exception:
            self.status = "error"
            return False

    async def send_message(self, message: str, channel: str | None = None) -> Any:
        url = f"https://discord.com/api/v10/channels/{channel or self.channel_id}/messages"
        return await self._post_json(url, {"content": message}, headers={"Authorization": f"Bot {self.bot_token}"})

    async def fetch_messages(self) -> Any:
        url = f"https://discord.com/api/v10/channels/{self.channel_id}/messages?limit=20"
        return await self._get_json(url, headers={"Authorization": f"Bot {self.bot_token}"})
