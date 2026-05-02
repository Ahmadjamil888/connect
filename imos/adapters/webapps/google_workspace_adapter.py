from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.webapps.common import BaseWebAdapter


class GoogleWorkspaceAdapter(BaseWebAdapter):
    def __init__(self, name: str = "google_workspace", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["gmail", "drive", "docs", "sheets", "calendar", "forms"])
        self.credentials_file = (config or {}).get("GOOGLE_CREDENTIALS_JSON", "")

    async def connect(self) -> bool:
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
        except ModuleNotFoundError:
            self.status = "error"
            return False
        creds = Credentials.from_service_account_file(self.credentials_file, scopes=["https://www.googleapis.com/auth/cloud-platform", "https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/calendar"])
        self.gmail = await asyncio.to_thread(build, "gmail", "v1", credentials=creds)
        self.drive = await asyncio.to_thread(build, "drive", "v3", credentials=creds)
        self.docs = await asyncio.to_thread(build, "docs", "v1", credentials=creds)
        self.sheets = await asyncio.to_thread(build, "sheets", "v4", credentials=creds)
        self.calendar = await asyncio.to_thread(build, "calendar", "v3", credentials=creds)
        self.status = "connected"
        return True
