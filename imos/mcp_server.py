from __future__ import annotations

import asyncio
import json
import sys
import argparse
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

from imos.config import IMOS_HOME
from imos.orchestrator import IMOSOrchestrator
from imos.registry import AdapterRegistry


class IMOSMCPServer:
    def __init__(self) -> None:
        self.registry = AdapterRegistry()
        self.orchestrator = IMOSOrchestrator(self.registry)
        self.app = FastAPI(title="IMOS MCP Server")
        self._wire_routes()

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {"name": "imos_run", "description": "Run any IMOS task from the IDE"},
            {"name": "imos_write_file", "description": "Write content to a file"},
            {"name": "imos_read_file", "description": "Read a file"},
            {"name": "imos_run_shell", "description": "Run a shell command"},
            {"name": "imos_git_commit", "description": "Commit current changes"},
            {"name": "imos_send_message", "description": "Send a message via a messaging adapter"},
            {"name": "imos_search_web", "description": "Search the web"},
            {"name": "imos_list_adapters", "description": "List all registered adapters"},
        ]

    async def initialize(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        await self.registry.auto_discover()
        return {"protocolVersion": "0.1", "serverInfo": {"name": "imos-mcp", "version": "0.1.0"}, "capabilities": {"tools": True, "resources": True, "prompts": True}}

    async def tools_list(self) -> dict[str, Any]:
        return {"tools": self.tool_definitions()}

    async def tools_call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "imos_run":
            result = await self.orchestrator.run(arguments["prompt"], context=arguments.get("context", {}))
            return {"content": result.final_response}
        if name == "imos_write_file":
            path = Path(arguments["path"])
            path.write_text(arguments["content"], encoding="utf-8")
            return {"content": f"Wrote {path}"}
        if name == "imos_read_file":
            return {"content": Path(arguments["path"]).read_text(encoding="utf-8", errors="replace")}
        if name == "imos_run_shell":
            process = await asyncio.create_subprocess_shell(arguments["command"], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            return {"content": stdout.decode() + stderr.decode()}
        if name == "imos_git_commit":
            process = await asyncio.create_subprocess_shell(
                f'git add -A && git commit -m "{arguments.get("message", "imos commit")}"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            return {"content": stdout.decode() + stderr.decode()}
        if name == "imos_send_message":
            adapters = self.registry.get_by_type("messaging")
            if not adapters:
                return {"content": "No messaging adapters configured"}
            result = await adapters[0].send_message(arguments["message"], channel=arguments.get("channel"))
            return {"content": str(result)}
        if name == "imos_search_web":
            from tools.research import search_and_read

            return {"content": search_and_read(arguments["query"])}
        if name == "imos_list_adapters":
            return {"content": [{"name": item.name, "type": item.adapter_type, "status": item.status} for item in self.registry.get_all()]}
        raise KeyError(f"Unknown MCP tool: {name}")

    async def resources_list(self) -> dict[str, Any]:
        return {"resources": [{"uri": "imos://adapters", "name": "Adapters"}, {"uri": "imos://history", "name": "History"}]}

    async def resources_read(self, uri: str) -> dict[str, Any]:
        if uri == "imos://adapters":
            return {"contents": [{"mimeType": "application/json", "text": json.dumps([{"name": item.name, "type": item.adapter_type, "status": item.status} for item in self.registry.get_all()], indent=2)}]}
        if uri == "imos://history":
            return {"contents": [{"mimeType": "application/json", "text": json.dumps(self.orchestrator.context_manager.recent_history(), indent=2)}]}
        return {"contents": []}

    async def prompts_list(self) -> dict[str, Any]:
        return {"prompts": [{"name": "imos_plan", "description": "Ask IMOS to decompose and execute a task"}]}

    async def prompts_get(self, name: str) -> dict[str, Any]:
        if name != "imos_plan":
            raise KeyError(name)
        return {"name": name, "messages": [{"role": "user", "content": "Plan and execute this task through IMOS."}]}

    def _wire_routes(self) -> None:
        @self.app.post("/mcp")
        async def mcp_post(request: Request):
            payload = await request.json()
            return JSONResponse(await self._dispatch(payload))

        @self.app.get("/mcp/sse")
        async def mcp_sse():
            async def stream():
                yield f"data: {json.dumps(await self.initialize())}\n\n"
                yield f"data: {json.dumps(await self.tools_list())}\n\n"

            return StreamingResponse(stream(), media_type="text/event-stream")

    async def _dispatch(self, payload: dict[str, Any]) -> dict[str, Any]:
        method = payload.get("method")
        params = payload.get("params", {})
        mapping = {
            "initialize": self.initialize,
            "tools/list": self.tools_list,
            "tools/call": lambda: self.tools_call(params["name"], params.get("arguments", {})),
            "resources/list": self.resources_list,
            "resources/read": lambda: self.resources_read(params["uri"]),
            "prompts/list": self.prompts_list,
            "prompts/get": lambda: self.prompts_get(params["name"]),
        }
        if method not in mapping:
            return {"error": {"message": f"Unknown MCP method: {method}"}}
        result = await mapping[method]()
        return {"jsonrpc": "2.0", "id": payload.get("id"), "result": result}

    async def serve_stdio(self) -> None:
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                break
            payload = json.loads(line)
            response = await self._dispatch(payload)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

    async def serve_http(self, host: str = "127.0.0.1", port: int = 8767) -> None:
        config = uvicorn.Config(self.app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


def install_mcp_configs() -> list[str]:
    cursor_path = Path.home() / ".cursor" / "mcp.json"
    windsurf_path = Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
    payload = {"imos": {"command": "python", "args": ["-m", "imos.mcp_server"]}}
    written = []
    for path in [cursor_path, windsurf_path]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        written.append(str(path))
    return written


async def main_async() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--http", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    args, _unknown = parser.parse_known_args(sys.argv[1:])
    server = IMOSMCPServer()
    await server.initialize()
    if args.http:
        await server.serve_http(host=args.host, port=args.port)
        return
    await server.serve_stdio()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
