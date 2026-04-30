from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import httpx


@dataclass
class MCPServer:
    name: str
    url: str
    enabled: bool = True


class MCPRuntime:
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.tool_registry: Dict[str, Dict[str, Any]] = {}

    def register_server(self, server: MCPServer):
        self.servers[server.name] = server
        if server.enabled:
            self.discover_tools(server.name)

    def discover_tools(self, server_name: str) -> List[Dict[str, Any]]:
        server = self.servers[server_name]
        response = httpx.post(f"{server.url.rstrip('/')}/tools/list", timeout=15)
        response.raise_for_status()
        items = response.json().get("tools", [])
        for tool in items:
            self.tool_registry[tool["name"]] = {
                "server": server.name,
                "schema": tool,
            }
        return items

    def list_servers(self) -> List[Dict[str, Any]]:
        return [{"name": item.name, "url": item.url, "enabled": item.enabled} for item in self.servers.values()]

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "server": info["server"],
                "description": info["schema"].get("description", ""),
                "input_schema": info["schema"].get("inputSchema", {}),
            }
            for name, info in self.tool_registry.items()
        ]

    def has_tool(self, name: str) -> bool:
        return name in self.tool_registry

    def tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": item["name"],
                "description": item["description"],
                "input_schema": item["input_schema"],
            }
            for item in self.list_tools()
        ]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self.tool_registry:
            return {"ok": False, "error": f"Tool {tool_name} not found"}
        entry = self.tool_registry[tool_name]
        server = self.servers[entry["server"]]
        response = httpx.post(
            f"{server.url.rstrip('/')}/tools/call",
            json={"name": tool_name, "arguments": arguments},
            timeout=60,
        )
        response.raise_for_status()
        return {"ok": True, "server": server.name, "result": response.json()}
