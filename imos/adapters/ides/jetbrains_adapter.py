from __future__ import annotations

from pathlib import Path
from typing import Any

import aiohttp

from imos.adapters.ides.common import BaseIDEAdapter, cli_available


class JetbrainsAdapter(BaseIDEAdapter):
    def __init__(self, name: str = "jetbrains", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.gateway_url = (config or {}).get("gateway_url", "http://localhost:63342/api")

    async def connect(self) -> bool:
        await super().connect()
        if await self.health_check():
            return True
        self.status = "connected" if any(cli_available(cmd) for cmd in ["idea", "pycharm", "webstorm"]) else "error"
        return self.status == "connected"

    async def health_check(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.gateway_url, timeout=5) as response:
                    self.status = "connected" if response.status < 500 else "error"
                    return response.status < 500
        except Exception:
            return self.workspace.exists()

    async def open_file(self, path: str, line: int | None = None) -> str:
        target = self._resolve(path)
        for command in ["idea", "pycharm", "webstorm"]:
            if cli_available(command):
                import asyncio

                process = await asyncio.create_subprocess_exec(command, str(target))
                await process.communicate()
                break
        return await super().open_file(str(target), line)
