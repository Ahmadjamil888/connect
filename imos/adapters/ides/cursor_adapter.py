from __future__ import annotations

from pathlib import Path
from typing import Any

from imos.adapters.ides.common import MCPServerBase


class CursorAdapter(MCPServerBase):
    def __init__(self, name: str = "cursor", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, mcp_config_path=Path.home() / ".cursor" / "mcp.json")
