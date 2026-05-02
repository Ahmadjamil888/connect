from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from imos.adapters.ides.common import MCPServerBase


class ZedAdapter(MCPServerBase):
    def __init__(self, name: str = "zed", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.settings_path = Path.home() / ".config" / "zed" / "settings.json"

    async def connect(self) -> bool:
        await super().connect()
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings = {}
        if self.settings_path.exists():
            try:
                settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
            except Exception:
                settings = {}
        settings.setdefault("context_servers", {})
        settings["context_servers"]["imos"] = {"command": "python", "args": ["-m", "imos.mcp_server"]}
        self.settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        self.status = "connected"
        return True
