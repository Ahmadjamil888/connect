from __future__ import annotations

from typing import Any

from imos.adapters.meetings.common import BaseMeetingAdapter


class CalendlyAdapter(BaseMeetingAdapter):
    def __init__(self, name: str = "calendly", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["list_available_times", "create_meeting", "list_meetings", "get_meeting", "cancel_meeting"])
        self.api_token = (config or {}).get("CALENDLY_API_TOKEN", "")
        self.organization_uri = (config or {}).get("organization_uri", "")
        self.user_uri = (config or {}).get("user_uri", "")

    async def health_check(self) -> bool:
        return bool(self.api_token)

    async def create_meeting(self, prompt: str, metadata: dict[str, Any]) -> Any:
        return {"scheduling_url": metadata.get("scheduling_url"), "prompt": prompt}

    async def list_meetings(self) -> Any:
        return await self._get_json("https://api.calendly.com/scheduled_events", headers={"Authorization": f"Bearer {self.api_token}"})

    async def get_meeting(self, meeting_id: str) -> Any:
        return await self._get_json(f"https://api.calendly.com/scheduled_events/{meeting_id}", headers={"Authorization": f"Bearer {self.api_token}"})

    async def cancel_meeting(self, meeting_id: str) -> Any:
        if self.session is None or self.session.closed:
            await self.connect()
        async with self.session.delete(
            f"https://api.calendly.com/scheduled_events/{meeting_id}/cancellation",
            headers={"Authorization": f"Bearer {self.api_token}"},
        ) as response:
            return {"status": response.status}
