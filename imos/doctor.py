from __future__ import annotations

import json
from pathlib import Path

from imos.config import list_configured_adapters
from imos.registry import AdapterRegistry
from core import model_manager
from service.status import read_service_status
from setup.autostart import safe_autostart_status


async def doctor_report(
    *,
    session_manager=None,
    dashboard_service=None,
    routing_rules=None,
    event_bus=None,
    process_manager=None,
    listener_service=None,
    consent_manager=None,
    contact_book=None,
    voice_manager=None,
    state_root: Path | None = None,
) -> str:
    registry = AdapterRegistry()
    await registry.auto_discover()
    lines = ["IMOS Runtime", ""]
    service_status = read_service_status(state_root) if state_root is not None else {"running": False, "tray": False}
    if session_manager is not None:
        session = session_manager.get_active()
        lines.append(f"  Session:    {session.name} ({session.status})")
        lines.append(f"  Sessions:   {len(session_manager.list_sessions())}")
    if dashboard_service is not None:
        dashboard = dashboard_service.status()
        dashboard_state = "running" if dashboard.get("running") else "stopped"
        lines.append(f"  Dashboard:  {dashboard.get('url', '')} ({dashboard_state})")
    if process_manager is not None:
        mcp_process = next(
            (
                row
                for row in process_manager.list()
                if row.get("name") == "imos-mcp-server" and str(row.get("status")) == "running"
            ),
            None,
        )
        endpoint = "http://127.0.0.1:8765/mcp"
        state = "stopped"
        if mcp_process is not None:
            endpoint = str((mcp_process.get("metadata") or {}).get("url", endpoint))
            state = "running"
        lines.append(f"  MCP:        {endpoint} ({state})")
    if event_bus is not None:
        lines.append(f"  Event bus:  {'active' if event_bus.status().get('active') else 'inactive'}")
    if listener_service is not None:
        listener = listener_service.status()
        if listener.get("active"):
            lines.append(f"  Listener:   active (wake: {listener.get('wake_word', 'IMOS')})")
        else:
            lines.append("  Listener:   inactive")
    if voice_manager is not None:
        voice = voice_manager.status()
        lines.append(f"  Voice:      {voice.get('provider')} ({voice.get('provider_label')})")
    if state_root is not None:
        auto = safe_autostart_status(Path.cwd())
        lines.append(f"  Autostart:  {'enabled' if auto.get('enabled') else 'disabled'}")
    if consent_manager is not None:
        lines.append(f"  Consent:    {'granted' if consent_manager.is_granted() else 'declined'}")
    lines.append("")
    lines.append("Providers:")
    for adapter in registry.get_all():
        health = "healthy" if await adapter.health_check() else "unhealthy"
        lines.append(f"  {adapter.name:<11} {health}")
    if routing_rules is not None:
        lines.append("")
        lines.append("Routing:")
        for name, provider in routing_rules.list_rules().items():
            lines.append(f"  {name:<17} {provider or '-'}")
    provider_rows = model_manager.load_providers()
    if provider_rows:
        lines.append("")
        lines.append("Model providers:")
        for item in provider_rows:
            health = model_manager.test_provider(item["id"])
            status = "healthy" if health.get("ok") else "unhealthy"
            latency = f" {health.get('latency', 0)}ms" if health.get("latency") else ""
            marker = " default" if item.get("is_default") else ""
            lines.append(f"  {item['id']:<17} {item['type']:<10} {status}{latency}{marker}")
    return "\n".join(lines)
