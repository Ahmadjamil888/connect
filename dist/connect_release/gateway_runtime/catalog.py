from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set

from ai_assistant import AdvancedTools


@dataclass
class CatalogTool:
    name: str
    group: str
    description: str
    definition: Dict[str, Any]
    implemented: bool = True


STATIC_TOOLS: List[CatalogTool] = [
    CatalogTool("sessions_list", "sessions", "List active sessions", {"type": "function", "function": {"name": "sessions_list", "description": "List active sessions", "parameters": {"type": "object", "properties": {}, "required": []}}}),
    CatalogTool("sessions_history", "sessions", "Read session history", {"type": "function", "function": {"name": "sessions_history", "description": "Read session history", "parameters": {"type": "object", "properties": {"session_id": {"type": "string"}}, "required": ["session_id"]}}}),
    CatalogTool("sessions_send", "sessions", "Send a user message into a session", {"type": "function", "function": {"name": "sessions_send", "description": "Send a message into a session", "parameters": {"type": "object", "properties": {"session_id": {"type": "string"}, "content": {"type": "string"}}, "required": ["session_id", "content"]}}}),
    CatalogTool("sessions_spawn", "sessions", "Spawn a child session", {"type": "function", "function": {"name": "sessions_spawn", "description": "Spawn a child session", "parameters": {"type": "object", "properties": {"parent_id": {"type": "string"}, "name": {"type": "string"}, "profile": {"type": "string"}}, "required": ["parent_id", "name"]}}}),
    CatalogTool("sessions_yield", "sessions", "Mark a session as waiting", {"type": "function", "function": {"name": "sessions_yield", "description": "Mark a session as yielded", "parameters": {"type": "object", "properties": {"session_id": {"type": "string"}}, "required": ["session_id"]}}}),
    CatalogTool("subagents", "sessions", "Alias for spawning sub-sessions", {"type": "function", "function": {"name": "subagents", "description": "Spawn a subagent session", "parameters": {"type": "object", "properties": {"parent_id": {"type": "string"}, "name": {"type": "string"}, "profile": {"type": "string"}}, "required": ["parent_id", "name"]}}}),
    CatalogTool("session_status", "sessions", "Get a session status", {"type": "function", "function": {"name": "session_status", "description": "Get a session status", "parameters": {"type": "object", "properties": {"session_id": {"type": "string"}}, "required": ["session_id"]}}}),
    CatalogTool("memory_search", "memory", "Search long-term memory", {"type": "function", "function": {"name": "memory_search", "description": "Search memory", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}}}),
    CatalogTool("memory_get", "memory", "Fetch recent memory for a session", {"type": "function", "function": {"name": "memory_get", "description": "Get recent memory", "parameters": {"type": "object", "properties": {"session_id": {"type": "string"}, "limit": {"type": "integer"}}, "required": []}}}),
    CatalogTool("web_fetch", "web", "Fetch a web page body", {"type": "function", "function": {"name": "web_fetch", "description": "Fetch a web page", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}}),
    CatalogTool("x_search", "web", "Search X/Twitter via provider connector", {"type": "function", "function": {"name": "x_search", "description": "Search X/Twitter", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}, implemented=False),
    CatalogTool("canvas_present", "ui", "Present data on canvas", {"type": "function", "function": {"name": "canvas_present", "description": "Present data on canvas", "parameters": {"type": "object", "properties": {"content": {"type": "string"}, "title": {"type": "string"}, "kind": {"type": "string"}}, "required": ["content"]}}}),
    CatalogTool("canvas_eval", "ui", "Evaluate canvas expression", {"type": "function", "function": {"name": "canvas_eval", "description": "Evaluate a canvas expression", "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}}),
    CatalogTool("canvas_snapshot", "ui", "Snapshot canvas state", {"type": "function", "function": {"name": "canvas_snapshot", "description": "Get a canvas snapshot", "parameters": {"type": "object", "properties": {}, "required": []}}}),
    CatalogTool("cron_add", "automation", "Add a cron job", {"type": "function", "function": {"name": "cron_add", "description": "Add a cron job", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "schedule": {"type": "string"}, "prompt": {"type": "string"}}, "required": ["name", "schedule", "prompt"]}}}),
    CatalogTool("cron_list", "automation", "List cron jobs", {"type": "function", "function": {"name": "cron_list", "description": "List cron jobs", "parameters": {"type": "object", "properties": {}, "required": []}}}),
    CatalogTool("cron_remove", "automation", "Remove a cron job", {"type": "function", "function": {"name": "cron_remove", "description": "Remove a cron job", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}}),
    CatalogTool("workflows_list", "automation", "List workflow definitions", {"type": "function", "function": {"name": "workflows_list", "description": "List workflows", "parameters": {"type": "object", "properties": {}, "required": []}}}),
    CatalogTool("workflow_run", "automation", "Run a named workflow", {"type": "function", "function": {"name": "workflow_run", "description": "Run a workflow", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "payload": {"type": "object"}}, "required": ["name"]}}}),
    CatalogTool("webhook_trigger", "automation", "Trigger a workflow webhook", {"type": "function", "function": {"name": "webhook_trigger", "description": "Trigger a workflow webhook", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "payload": {"type": "object"}}, "required": ["name"]}}}),
    CatalogTool("nodes_list", "nodes", "List paired nodes", {"type": "function", "function": {"name": "nodes_list", "description": "List paired nodes", "parameters": {"type": "object", "properties": {}, "required": []}}}),
    CatalogTool("node_pair", "nodes", "Create a mobile pairing code", {"type": "function", "function": {"name": "node_pair", "description": "Create a mobile pairing code", "parameters": {"type": "object", "properties": {"label": {"type": "string"}}, "required": []}}}),
    CatalogTool("node_notify", "nodes", "Send a notification to a node", {"type": "function", "function": {"name": "node_notify", "description": "Notify a paired node", "parameters": {"type": "object", "properties": {"node_id": {"type": "string"}, "message": {"type": "string"}}, "required": ["node_id", "message"]}}}),
    CatalogTool("node_capture_screen", "nodes", "Capture a node screen", {"type": "function", "function": {"name": "node_capture_screen", "description": "Capture node screen", "parameters": {"type": "object", "properties": {"node_id": {"type": "string"}}, "required": ["node_id"]}}}),
    CatalogTool("node_capture_camera", "nodes", "Capture a node camera frame", {"type": "function", "function": {"name": "node_capture_camera", "description": "Capture node camera", "parameters": {"type": "object", "properties": {"node_id": {"type": "string"}}, "required": ["node_id"]}}}),
    CatalogTool("node_location", "nodes", "Get node location", {"type": "function", "function": {"name": "node_location", "description": "Get node location", "parameters": {"type": "object", "properties": {"node_id": {"type": "string"}}, "required": ["node_id"]}}}),
    CatalogTool("message_send", "messaging", "Send a message to a channel target", {"type": "function", "function": {"name": "message_send", "description": "Send a message", "parameters": {"type": "object", "properties": {"target": {"type": "string"}, "content": {"type": "string"}}, "required": ["target", "content"]}}}),
    CatalogTool("image_analyze", "media", "Analyze an image artifact", {"type": "function", "function": {"name": "image_analyze", "description": "Analyze an image", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}, implemented=False),
    CatalogTool("image_generate", "media", "Generate an image", {"type": "function", "function": {"name": "image_generate", "description": "Generate an image", "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}}}, implemented=False),
    CatalogTool("music_generate", "media", "Generate music", {"type": "function", "function": {"name": "music_generate", "description": "Generate music", "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}}}, implemented=False),
    CatalogTool("video_generate", "media", "Generate video", {"type": "function", "function": {"name": "video_generate", "description": "Generate video", "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}}}, implemented=False),
    CatalogTool("tts", "media", "Convert text to speech", {"type": "function", "function": {"name": "tts", "description": "Convert text to speech", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}}, implemented=False),
    CatalogTool("gateway_status", "automation", "Report gateway state", {"type": "function", "function": {"name": "gateway_status", "description": "Get gateway status", "parameters": {"type": "object", "properties": {}, "required": []}}}),
    CatalogTool("gateway_restart", "automation", "Request gateway restart", {"type": "function", "function": {"name": "gateway_restart", "description": "Request gateway restart", "parameters": {"type": "object", "properties": {}, "required": []}}}),
    CatalogTool("config_schema_lookup", "automation", "Inspect one config path", {"type": "function", "function": {"name": "config_schema_lookup", "description": "Inspect a config path", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}),
]


GROUP_OVERRIDES = {
    "read_file": "fs",
    "write_file": "fs",
    "create_directory": "fs",
    "list_directory": "fs",
    "search_files": "fs",
    "file_operations": "fs",
    "run_shell_command": "runtime",
    "execute_python": "runtime",
    "manage_processes": "runtime",
    "install_package": "runtime",
    "browser_open": "ui",
    "open_browser": "ui",
    "browser_click": "ui",
    "browser_type": "ui",
    "browser_wait": "ui",
    "browser_snapshot": "ui",
    "browser_close": "ui",
    "manage_browser_tabs": "ui",
    "browser_login": "ui",
    "web_search": "web",
    "web_scrape": "web",
    "download_file": "web",
}


class ToolCatalog:
    def __init__(self):
        self._tools: Dict[str, CatalogTool] = {}
        self._build()

    def _build(self):
        for definition in AdvancedTools.get_agent_definitions():
            fn = definition.get("function", {})
            name = fn.get("name", "")
            if not name:
                continue
            group = GROUP_OVERRIDES.get(name, "runtime")
            self._tools[name] = CatalogTool(
                name=name,
                group=group,
                description=fn.get("description", ""),
                definition=definition,
                implemented=True,
            )
        for tool in STATIC_TOOLS:
            self._tools[tool.name] = tool

    def names(self) -> Set[str]:
        return set(self._tools.keys())

    def group_map(self) -> Dict[str, Set[str]]:
        groups: Dict[str, Set[str]] = {}
        for tool in self._tools.values():
            groups.setdefault(tool.group, set()).add(tool.name)
        return groups

    def get(self, name: str) -> CatalogTool:
        return self._tools[name]

    def list(self) -> List[Dict[str, Any]]:
        rows = []
        for tool in sorted(self._tools.values(), key=lambda item: (item.group, item.name)):
            rows.append(
                {
                    "name": tool.name,
                    "group": tool.group,
                    "implemented": tool.implemented,
                    "description": tool.description,
                }
            )
        return rows

    def definitions(self, names: Set[str]) -> List[Dict[str, Any]]:
        return [self._tools[name].definition for name in sorted(names) if name in self._tools]
