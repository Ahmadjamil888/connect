from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.messaging.common import BaseMessagingAdapter


class SignalAdapter(BaseMessagingAdapter):
    def __init__(self, name: str = "signal", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.phone_number = (config or {}).get("SIGNAL_PHONE_NUMBER", "")
        self.cli_path = (config or {}).get("SIGNAL_CLI_PATH", "signal-cli")
        self.api_url = (config or {}).get("SIGNAL_API_URL", "")
        self.recipient = (config or {}).get("recipient", "")

    async def health_check(self) -> bool:
        return bool(self.api_url or self.cli_path)

    async def send_message(self, message: str, channel: str | None = None) -> Any:
        if self.api_url:
            return await self._post_json(f"{self.api_url}/v2/send", {"message": message, "number": self.phone_number, "recipients": [channel or self.recipient]})
        process = await asyncio.create_subprocess_exec(
            self.cli_path,
            "-a",
            self.phone_number,
            "send",
            "-m",
            message,
            channel or self.recipient,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return {"stdout": stdout.decode(), "stderr": stderr.decode(), "returncode": process.returncode}
