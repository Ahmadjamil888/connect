from __future__ import annotations

import json
from pathlib import Path

from imos.config import list_configured_adapters
from imos.registry import AdapterRegistry


async def doctor_report() -> str:
    registry = AdapterRegistry()
    await registry.auto_discover()
    lines = ["IMOS Doctor", ""]
    lines.append("Configured adapters:")
    for adapter in list_configured_adapters():
        missing = []
        for key, value in adapter.items():
            if key.isupper() and not value:
                missing.append(key)
        lines.append(f"- {adapter.get('name')} ({adapter.get('adapter_type')}): missing_credentials={missing}")
    lines.append("")
    lines.append("Health:")
    for adapter in registry.get_all():
        lines.append(f"- {adapter.name}: {'ok' if await adapter.health_check() else 'unhealthy'}")
    lines.append("")
    lines.append("MCP configs:")
    for path in [Path.home() / ".cursor" / "mcp.json", Path.home() / ".codeium" / "windsurf" / "mcp_config.json"]:
        lines.append(f"- {path}: {'installed' if path.exists() else 'missing'}")
    return "\n".join(lines)
