from __future__ import annotations

from pathlib import Path
from typing import Any

from imos.adapters.ides.common import BaseIDEAdapter


SUBLIME_PLUGIN = """import sublime\nimport sublime_plugin\nimport socket\n\nclass ImosHeartbeatCommand(sublime_plugin.ApplicationCommand):\n    def run(self):\n        sock = socket.socket()\n        try:\n            sock.connect(('127.0.0.1', 8766))\n            sock.sendall(b'heartbeat')\n        finally:\n            sock.close()\n"""


class SublimeAdapter(BaseIDEAdapter):
    def __init__(self, name: str = "sublime", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.plugin_path = Path.home() / "AppData" / "Roaming" / "Sublime Text" / "Packages" / "IMOS" / "imos_bridge.py"

    async def connect(self) -> bool:
        await super().connect()
        self.plugin_path.parent.mkdir(parents=True, exist_ok=True)
        self.plugin_path.write_text(SUBLIME_PLUGIN, encoding="utf-8")
        self.status = "connected"
        return True
