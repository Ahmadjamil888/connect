from __future__ import annotations

import time
from typing import Any

import aiohttp

from imos.adapters.messaging.common import BaseMessagingAdapter


class MatrixAdapter(BaseMessagingAdapter):
    def __init__(self, name: str = "matrix", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.homeserver = (config or {}).get("MATRIX_HOMESERVER", "https://matrix.org").rstrip("/")
        self.user_id = (config or {}).get("MATRIX_USER_ID", "")
        self.password = (config or {}).get("MATRIX_PASSWORD", "")
        self.access_token = (config or {}).get("MATRIX_ACCESS_TOKEN", "")
        self.room_id = (config or {}).get("MATRIX_ROOM_ID", "")

    async def connect(self) -> bool:
        await super().connect()
        if not self.access_token and self.password:
            self.access_token = await self._login()
        self.status = "connected" if self.access_token else "error"
        return bool(self.access_token)

    async def health_check(self) -> bool:
        return bool(self.access_token or await self.connect())

    async def send_message(self, message: str, channel: str | None = None) -> Any:
        token = self.access_token or await self._login()
        txn = str(int(time.time() * 1000))
        url = f"{self.homeserver}/_matrix/client/v3/rooms/{channel or self.room_id}/send/m.room.message/{txn}"
        headers = {"Authorization": f"Bearer {token}"}
        return await self._put_json(url, {"msgtype": "m.text", "body": message}, headers=headers)

    async def _login(self) -> str:
        data = {"type": "m.login.password", "identifier": {"type": "m.id.user", "user": self.user_id}, "password": self.password}
        payload = await self._post_json(f"{self.homeserver}/_matrix/client/v3/login", data)
        return payload.get("access_token", "")

    async def _put_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> Any:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        async with self.session.put(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as response:
            response.raise_for_status()
            return await response.json()
