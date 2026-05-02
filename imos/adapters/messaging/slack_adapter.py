from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.messaging.common import BaseMessagingAdapter


class SlackAdapter(BaseMessagingAdapter):
    def __init__(self, name: str = "slack", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.bot_token = (config or {}).get("SLACK_BOT_TOKEN") or (config or {}).get("bot_token", "")
        self.channel = (config or {}).get("SLACK_CHANNEL") or (config or {}).get("channel", "")
        self.client = None

    async def connect(self) -> bool:
        await super().connect()
        try:
            from slack_sdk import WebClient
        except ModuleNotFoundError:
            self.status = "error"
            return False
        self.client = WebClient(token=self.bot_token)
        return await self.health_check()

    async def health_check(self) -> bool:
        if not self.client:
            return False
        try:
            await asyncio.to_thread(self.client.auth_test)
            self.status = "connected"
            return True
        except Exception:
            self.status = "error"
            return False

    async def send_message(self, message: str, channel: str | None = None) -> Any:
        if self.client is None and not await self.connect():
            raise RuntimeError("Slack client unavailable")
        return await asyncio.to_thread(self.client.chat_postMessage, channel=channel or self.channel, text=message)

    async def send_file(self, path: str, caption: str | None = None) -> Any:
        if self.client is None and not await self.connect():
            raise RuntimeError("Slack client unavailable")
        return await asyncio.to_thread(self.client.files_upload_v2, channel= self.channel, file=path, initial_comment=caption or "")

    async def fetch_messages(self) -> Any:
        if self.client is None and not await self.connect():
            raise RuntimeError("Slack client unavailable")
        response = await asyncio.to_thread(self.client.conversations_history, channel=self.channel, limit=20)
        return response.get("messages", [])
