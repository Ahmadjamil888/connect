#!/usr/bin/env python3
"""Compatibility wrapper plus IMOS dashboard API."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse

from ai_assistant import main
from imos.config import get_adapter_config, list_configured_adapters, merged_settings, remove_adapter_config, save_adapter_config, save_settings
from imos.orchestrator import IMOSOrchestrator
from imos.registry import AdapterRegistry
from imos.runtime import IMOS_SYSTEM_PROMPT_BASE
from imos.session_runtime import IMOSSessionRuntime


PROJECT_ROOT = Path(__file__).resolve().parent
IMOS_HTML = PROJECT_ROOT / "project_site" / "imos_dashboard.html"

app = FastAPI(title="NEXUS + IMOS")
registry = AdapterRegistry()
orchestrator = IMOSOrchestrator(registry)
session_runtime = IMOSSessionRuntime(orchestrator)
live_clients: list[WebSocket] = []

DEFAULT_PERMISSION_PROFILE: dict[str, Any] = {
    "pc_control": True,
    "browser_control": True,
    "ide_control": True,
    "app_access": True,
    "admin_mode": False,
    "shell_execution": True,
    "file_system_access": True,
    "ask_every_time_for_destructive": True,
    "preference_memory": True,
    "notes": "",
}


def _permission_profile() -> dict[str, Any]:
    settings = merged_settings()
    current = settings.get("permission_profile", {})
    merged = dict(DEFAULT_PERMISSION_PROFILE)
    if isinstance(current, dict):
        merged.update(current)
    return merged


async def _broadcast(event: dict[str, Any]) -> None:
    stale = []
    for client in live_clients:
        try:
            await client.send_json(event)
        except Exception:
            stale.append(client)
    for client in stale:
        if client in live_clients:
            live_clients.remove(client)


@app.get("/imos", response_class=HTMLResponse)
async def imos_dashboard():
    if IMOS_HTML.exists():
        return FileResponse(IMOS_HTML)
    return HTMLResponse("<h1>IMOS dashboard missing</h1>", status_code=500)


@app.post("/imos/run")
async def imos_run(payload: dict[str, Any]):
    prompt = payload.get("prompt", "")
    context = payload.get("context", {})
    session_name = str(payload.get("session_name", "dashboard")).strip() or "dashboard"
    session_id = str(payload.get("session_id", "")).strip() or None
    await _broadcast({"type": "task_started", "prompt": prompt})
    result = await session_runtime.run_turn(prompt, session_id=session_id, session_name=session_name, context=context)
    await _broadcast({"type": "task_finished", "prompt": prompt, "result": result.final_response})
    return {
        "final_response": result.final_response,
        "subtask_results": [asdict(item) for item in result.subtask_results],
        "duration_ms": result.duration_ms,
        "adapters_used": result.adapters_used,
        "metadata": result.metadata,
    }


@app.get("/imos/adapters")
async def imos_adapters():
    await registry.auto_discover()
    return [{"name": item.name, "type": item.adapter_type, "status": item.status, "capabilities": item.capabilities} for item in registry.get_all()]


@app.get("/imos/catalog")
async def imos_catalog():
    return registry.available_catalog()


@app.post("/imos/adapters")
async def register_adapter(payload: dict[str, Any]):
    name = payload["name"]
    save_adapter_config(name, payload)
    await registry.auto_discover()
    return {"status": "registered", "name": name}


@app.get("/imos/adapters/{name}")
async def get_adapter(name: str):
    return get_adapter_config(name)


@app.delete("/imos/adapters/{name}")
async def delete_adapter(name: str):
    remove_adapter_config(name)
    registry.unregister(name)
    return {"status": "removed", "name": name}


@app.post("/imos/adapters/{name}/test")
async def test_adapter(name: str):
    await registry.auto_discover()
    adapter = registry.get(name)
    if not adapter:
        return {"status": False, "error": "Adapter not found"}
    return {"status": await adapter.health_check()}


@app.get("/imos/history")
async def imos_history():
    return orchestrator.context_manager.recent_history(50)


@app.get("/imos/sessions")
async def imos_sessions():
    return session_runtime.list_sessions()


@app.get("/imos/sessions/{session_id}")
async def imos_session_detail(session_id: str):
    return session_runtime.export_session(session_id)


@app.get("/imos/status")
async def imos_status():
    await registry.auto_discover()
    history = orchestrator.context_manager.recent_history(200)
    return {
        "adapters_online": len([item for item in registry.get_all() if item.status == "connected"]),
        "configured_adapters": len(list_configured_adapters()),
        "tasks_run_today": len(history),
        "session_count": len(session_runtime.list_sessions()),
        "integration_count": len(registry.available_catalog()),
        "settings": merged_settings(),
    }


@app.post("/imos/settings")
async def update_imos_settings(payload: dict[str, Any]):
    settings = merged_settings()
    settings.update(payload)
    save_settings(settings)
    return {"status": "updated", "settings": settings}


@app.get("/imos/settings")
async def get_imos_settings():
    return merged_settings()


@app.get("/imos/permissions")
async def get_imos_permissions():
    return _permission_profile()


@app.post("/imos/permissions")
async def update_imos_permissions(payload: dict[str, Any]):
    settings = merged_settings()
    updated = _permission_profile()
    updated.update(payload)
    settings["permission_profile"] = updated
    save_settings(settings)
    await _broadcast({"type": "permission_profile_updated", "data": updated})
    return {"status": "updated", "permissions": updated}


@app.get("/imos/capabilities")
async def imos_capabilities():
    await registry.auto_discover()
    return sorted({capability for adapter in registry.get_all() for capability in adapter.capabilities})


@app.get("/imos/system-prompt")
async def imos_system_prompt():
    return {"prompt": IMOS_SYSTEM_PROMPT_BASE}


@app.websocket("/imos/ws")
async def imos_ws(websocket: WebSocket):
    await websocket.accept()
    live_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "echo", "data": data})
    except WebSocketDisconnect:
        if websocket in live_clients:
            live_clients.remove(websocket)


if __name__ == "__main__":
    main()
