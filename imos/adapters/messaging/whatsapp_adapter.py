from __future__ import annotations

import aiohttp
from typing import Any

from imos.adapters.messaging.common import BaseMessagingAdapter


class WhatsappAdapter(BaseMessagingAdapter):
    def __init__(self, name: str = "whatsapp", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.provider = (config or {}).get("WHATSAPP_PROVIDER", "meta")
        self.phone_number_id = (config or {}).get("WHATSAPP_PHONE_NUMBER_ID", "")
        self.token = (config or {}).get("WHATSAPP_TOKEN", "")
        self.account_sid = (config or {}).get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = (config or {}).get("TWILIO_AUTH_TOKEN", "")
        self.to_number = (config or {}).get("to_number", "")

    async def health_check(self) -> bool:
        return bool(self.token or self.auth_token)

    async def send_message(self, message: str, channel: str | None = None) -> Any:
        if self.provider == "twilio":
            return await self._send_twilio(message, channel or self.to_number)
        url = f"https://graph.facebook.com/v19.0/{self.phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": channel or self.to_number,
            "type": "text",
            "text": {"body": message},
        }
        return await self._post_json(url, payload, headers=headers)

    async def _send_twilio(self, message: str, to_number: str) -> Any:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(auth=aiohttp.BasicAuth(self.account_sid, self.auth_token))
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        data = {"To": f"whatsapp:{to_number}", "From": f"whatsapp:{(self.config or {}).get('from_number', '')}", "Body": message}
        async with self.session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=60)) as response:
            response.raise_for_status()
            return await response.json()
