from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from imos.adapters.ides.common import MCPServerBase


class WindsurfAdapter(MCPServerBase):
    def __init__(self, name: str = "windsurf", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, mcp_config_path=Path.home() / ".codeium" / "windsurf" / "mcp_config.json")
        self.local_api_url = (config or {}).get("codeium_api_url", "http://localhost:8766")

    async def connect(self) -> bool:
        await super().connect()
        config_path = Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "imos": {"command": "python", "args": ["-m", "imos.mcp_server"]},
                    "direct_api": {"url": self.local_api_url},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return True
