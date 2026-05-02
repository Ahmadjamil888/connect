from __future__ import annotations

from typing import Any

from imos.adapters.messaging.common import BaseMessagingAdapter


class TelegramAdapter(BaseMessagingAdapter):
    def __init__(self, name: str = "telegram", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.bot_token = (config or {}).get("TELEGRAM_BOT_TOKEN") or (config or {}).get("bot_token", "")
        self.chat_id = str((config or {}).get("TELEGRAM_CHAT_ID") or (config or {}).get("chat_id", ""))
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def health_check(self) -> bool:
        try:
            await self._get_json(f"{self.base_url}/getMe")
            self.status = "connected"
            return True
        except Exception:
            self.status = "error"
            return False

    async def send_message(self, message: str, channel: str | None = None) -> Any:
        return await self._post_json(f"{self.base_url}/sendMessage", {"chat_id": channel or self.chat_id, "text": message})

    async def fetch_messages(self) -> Any:
        return await self._get_json(f"{self.base_url}/getUpdates")
