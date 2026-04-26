from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict

from gateway_runtime.runtime import AgentRuntime


@dataclass
class GatewayController:
    runtime: AgentRuntime

    async def dispatch(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if method == "gateway.status":
            return self.runtime.gateway_status()
        if method == "jobs.list":
            return self.runtime.orchestrator.jobs()
        if method == "tools.list":
            return self.runtime.catalog.list()
        if method == "sessions.list":
            return self.runtime.sessions.list()
        if method == "sessions.history":
            return self.runtime.sessions.history(params["session_id"], int(params.get("limit", 30)))
        if method == "sessions.spawn":
            child = self.runtime.sessions.spawn(params["parent_id"], params["name"], str(params.get("profile", "coding")))
            return {"session_id": child.id, "name": child.name, "profile": child.profile}
        if method == "sessions.status":
            return self.runtime.sessions.status(params["session_id"])
        if method == "sessions.send":
            return self.runtime.run_turn(params["session_id"], params["content"])
        if method == "agent.ask":
            session_id = params.get("session_id") or self.runtime.ensure_default_session()
            return self.runtime.run_turn(session_id, params["content"])
        if method == "memory.search":
            return self.runtime.memory.search(params["query"], int(params.get("limit", 8)))
        if method == "memory.get":
            return self.runtime.memory.get_recent(str(params.get("session_id", "")), int(params.get("limit", 10)))
        if method == "canvas.snapshot":
            return self.runtime.canvas.snapshot()
        if method == "nodes.list":
            return self.runtime.nodes.list_nodes()
        if method == "workflows.list":
            return self.runtime.workflows.list_workflows()
        if method == "workflows.run":
            session_id = params.get("session_id") or self.runtime.ensure_default_session()
            return self.runtime.workflows.run_named(params["name"], params.get("payload", {}), session_id=session_id)
        if method == "config.schema.lookup":
            return self.runtime.config_lookup(params["path"])
        raise KeyError(f"unknown method: {method}")


class GatewayServer:
    def __init__(self, runtime: AgentRuntime):
        self.runtime = runtime
        self.controller = GatewayController(runtime)

    async def handle_socket(self, websocket):
        async for raw in websocket:
            response_id = None
            try:
                payload = json.loads(raw)
                response_id = payload.get("id")
                result = await self.controller.dispatch(payload["method"], payload.get("params", {}))
                response = {"id": response_id, "ok": True, "result": result}
            except Exception as exc:
                response = {"id": response_id, "ok": False, "error": str(exc)}
            await websocket.send(json.dumps(response))

    async def serve(self):
        try:
            import websockets
        except ModuleNotFoundError as exc:
            raise RuntimeError("Gateway server requires the 'websockets' package") from exc
        self.runtime.set_service_state("gateway", True, self.runtime.config.host, self.runtime.config.port)
        async with websockets.serve(self.handle_socket, self.runtime.config.host, self.runtime.config.port):
            try:
                await asyncio.Future()
            finally:
                self.runtime.set_service_state("gateway", False, self.runtime.config.host, self.runtime.config.port)
