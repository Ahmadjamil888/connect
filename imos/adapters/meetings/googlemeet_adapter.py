from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.meetings.common import BaseMeetingAdapter


class GooglemeetAdapter(BaseMeetingAdapter):
    def __init__(self, name: str = "googlemeet", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.credentials_file = (config or {}).get("GOOGLE_CREDENTIALS_JSON", "")

    async def connect(self) -> bool:
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
        except ModuleNotFoundError:
            self.status = "error"
            return False
        creds = Credentials.from_service_account_file(self.credentials_file, scopes=["https://www.googleapis.com/auth/calendar"])
        self.service = await asyncio.to_thread(build, "calendar", "v3", credentials=creds)
        self.status = "connected"
        return True

    async def health_check(self) -> bool:
        return hasattr(self, "service")

    async def create_meeting(self, prompt: str, metadata: dict[str, Any]) -> Any:
        if not await self.health_check():
            await self.connect()
        event = {
            "summary": metadata.get("summary", prompt[:100]),
            "description": prompt,
            "start": {"dateTime": metadata["start_time"]},
            "end": {"dateTime": metadata["end_time"]},
            "conferenceData": {"createRequest": {"requestId": metadata.get("request_id", "imos-meet")}},
        }
        return await asyncio.to_thread(
            self.service.events().insert(calendarId=metadata.get("calendar_id", "primary"), body=event, conferenceDataVersion=1).execute
        )

    async def list_meetings(self) -> Any:
        return await asyncio.to_thread(self.service.events().list(calendarId="primary").execute)

    async def get_meeting(self, meeting_id: str) -> Any:
        return await asyncio.to_thread(self.service.events().get(calendarId="primary", eventId=meeting_id).execute)

    async def cancel_meeting(self, meeting_id: str) -> Any:
        return await asyncio.to_thread(self.service.events().delete(calendarId="primary", eventId=meeting_id).execute)
