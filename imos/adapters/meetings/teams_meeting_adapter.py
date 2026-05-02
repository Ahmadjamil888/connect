from __future__ import annotations

from typing import Any

from imos.adapters.meetings.common import BaseMeetingAdapter
from imos.adapters.messaging.teams_adapter import TeamsAdapter


class TeamsMeetingAdapter(BaseMeetingAdapter):
    def __init__(self, name: str = "teams_meeting", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["create_meeting", "list_meetings", "get_meeting", "cancel_meeting", "get_transcript"])
        self.teams = TeamsAdapter(name=f"{name}_messaging", config=config)
        self.user_id = (config or {}).get("TEAMS_USER_ID", "")

    async def connect(self) -> bool:
        return await self.teams.connect()

    async def disconnect(self) -> None:
        await self.teams.disconnect()

    async def health_check(self) -> bool:
        return await self.teams.health_check()

    async def get_capabilities(self) -> list[str]:
        return list(self.capabilities)

    async def create_meeting(self, prompt: str, metadata: dict[str, Any]) -> Any:
        token = self.teams._access_token or await self.teams._token()
        payload = {
            "subject": metadata.get("subject", prompt[:100]),
            "startDateTime": metadata["start_time"],
            "endDateTime": metadata["end_time"],
        }
        return await self.teams._post_json(
            f"https://graph.microsoft.com/v1.0/users/{self.user_id}/onlineMeetings",
            payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    async def list_meetings(self) -> Any:
        token = self.teams._access_token or await self.teams._token()
        return await self.teams._get_json(f"https://graph.microsoft.com/v1.0/users/{self.user_id}/onlineMeetings", headers={"Authorization": f"Bearer {token}"})

    async def get_meeting(self, meeting_id: str) -> Any:
        token = self.teams._access_token or await self.teams._token()
        return await self.teams._get_json(
            f"https://graph.microsoft.com/v1.0/users/{self.user_id}/onlineMeetings/{meeting_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    async def cancel_meeting(self, meeting_id: str) -> Any:
        token = self.teams._access_token or await self.teams._token()
        if self.teams.session is None or self.teams.session.closed:
            await self.teams.connect()
        async with self.teams.session.delete(
            f"https://graph.microsoft.com/v1.0/users/{self.user_id}/onlineMeetings/{meeting_id}",
            headers={"Authorization": f"Bearer {token}"},
        ) as response:
            return {"status": response.status}
