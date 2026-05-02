from __future__ import annotations

import aiohttp
from typing import Any

from imos.adapters.meetings.common import BaseMeetingAdapter


class ZoomAdapter(BaseMeetingAdapter):
    def __init__(self, name: str = "zoom", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["create_meeting", "list_meetings", "get_meeting", "cancel_meeting", "start_recording", "stop_recording"])
        self.client_id = (config or {}).get("ZOOM_CLIENT_ID", "")
        self.client_secret = (config or {}).get("ZOOM_CLIENT_SECRET", "")
        self.account_id = (config or {}).get("ZOOM_ACCOUNT_ID", "")
        self.user_id = (config or {}).get("ZOOM_USER_ID", "me")
        self._access_token = ""

    async def connect(self) -> bool:
        await super().connect()
        self._access_token = await self._token()
        self.status = "connected" if self._access_token else "error"
        return bool(self._access_token)

    async def health_check(self) -> bool:
        return bool(self._access_token or await self.connect())

    async def create_meeting(self, prompt: str, metadata: dict[str, Any]) -> Any:
        headers = {"Authorization": f"Bearer {self._access_token or await self._token()}"}
        payload = {
            "topic": metadata.get("topic", prompt[:100]),
            "type": 2,
            "agenda": prompt,
            "duration": metadata.get("duration", 30),
            "start_time": metadata.get("start_time"),
            "settings": {"host_video": True, "participant_video": True},
        }
        return await self._post_json(f"https://api.zoom.us/v2/users/{self.user_id}/meetings", payload, headers=headers)

    async def list_meetings(self) -> Any:
        return await self._get_json(f"https://api.zoom.us/v2/users/{self.user_id}/meetings", headers={"Authorization": f"Bearer {self._access_token or await self._token()}"})

    async def get_meeting(self, meeting_id: str) -> Any:
        return await self._get_json(f"https://api.zoom.us/v2/meetings/{meeting_id}", headers={"Authorization": f"Bearer {self._access_token or await self._token()}"})

    async def cancel_meeting(self, meeting_id: str) -> Any:
        return await self._delete(f"https://api.zoom.us/v2/meetings/{meeting_id}", headers={"Authorization": f"Bearer {self._access_token or await self._token()}"})

    async def _token(self) -> str:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        auth = aiohttp.BasicAuth(self.client_id, self.client_secret)
        data = {"grant_type": "account_credentials", "account_id": self.account_id}
        async with self.session.post("https://zoom.us/oauth/token", params=data, auth=auth) as response:
            response.raise_for_status()
            payload = await response.json()
            return payload.get("access_token", "")

    async def _post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> Any:
        async with self.session.post(url, json=payload, headers=headers) as response:
            response.raise_for_status()
            return await response.json()

    async def _get_json(self, url: str, headers: dict[str, str]) -> Any:
        async with self.session.get(url, headers=headers) as response:
            response.raise_for_status()
            return await response.json()

    async def _delete(self, url: str, headers: dict[str, str]) -> Any:
        async with self.session.delete(url, headers=headers) as response:
            if response.status >= 400:
                response.raise_for_status()
            return {"status": response.status}
