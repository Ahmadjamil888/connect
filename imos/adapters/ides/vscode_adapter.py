from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from imos.adapters.ides.common import BaseIDEAdapter, cli_available


class VscodeAdapter(BaseIDEAdapter):
    def __init__(self, name: str = "vscode", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.extension_dir = Path(__file__).resolve().parent / "vscode_extension"
        self.ws_port = int((config or {}).get("websocket_port", 8766))

    async def connect(self) -> bool:
        await super().connect()
        self.status = "connected" if self.extension_dir.exists() else "error"
        return self.extension_dir.exists() or cli_available("code")

    async def open_file(self, path: str, line: int | None = None) -> str:
        target = self._resolve(path)
        if cli_available("code"):
            import asyncio

            command = ["code", "--goto", f"{target}:{line or 1}"]
            process = await asyncio.create_subprocess_exec(*command)
            await process.communicate()
        return await super().open_file(path, line)

    async def get_open_files(self) -> list[str]:
        state_file = self.extension_dir / "open_files.json"
        if state_file.exists():
            try:
                return json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                return await super().get_open_files()
        return await super().get_open_files()
