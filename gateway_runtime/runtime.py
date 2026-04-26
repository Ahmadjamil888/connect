from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from ai_assistant import AIModel, AdvancedTools
from gateway_runtime.auth import ClerkAuthManager
from gateway_runtime.catalog import ToolCatalog
from gateway_runtime.canvas_store import CanvasStore
from gateway_runtime.config import GatewayConfig, resolve_allowed_tool_names
from gateway_runtime.memory_store import MemoryStore
from gateway_runtime.messaging import (
    DiscordWebhookConnector,
    SlackBotConnector,
    SlackWebhookConnector,
    TelegramConnector,
    WhatsAppTwilioConnector,
)
from gateway_runtime.node_pairing import NodePairingStore
from gateway_runtime.orchestrator import Orchestrator
from gateway_runtime.scheduler import CronScheduler
from gateway_runtime.sessions import SessionManager
from gateway_runtime.workflow_engine import WorkflowEngine
from gateway_runtime.workspace import WorkspaceLayout


@dataclass
class ToolExecutionResult:
    tool_name: str
    ok: bool
    output: Any


class AgentRuntime:
    def __init__(self, config: GatewayConfig, ai_model: Optional[Any] = None):
        self.config = config
        self.service_state: Dict[str, Dict[str, Any]] = {
            "gateway": {"running": False, "host": config.host, "port": config.port},
            "dashboard": {"running": False, "host": config.dashboard_host, "port": config.dashboard_port},
        }
        self.workspace = WorkspaceLayout(config.workspace_root)
        self.workspace.bootstrap()
        self.auth = ClerkAuthManager(self.workspace.root, config.clerk_publishable_key, config.auth_enabled, config.webhook_bearer_token)
        self.sessions = SessionManager(self.workspace.sessions_dir)
        self.memory = MemoryStore(self.workspace.memory_dir)
        self.catalog = ToolCatalog()
        self.ai = ai_model or AIModel()
        self.cron_path = self.workspace.cron_dir / "jobs.json"
        self.canvas = CanvasStore(self.workspace.canvas_dir / "state.json")
        self.nodes = NodePairingStore(self.workspace.nodes_dir / "nodes.json")
        self.orchestrator = Orchestrator(self.workspace.orchestration_dir / "jobs.json", self._handle_job)
        self.orchestrator.start()
        self.scheduler = CronScheduler(self._load_cron_jobs, self._save_cron_jobs, self.orchestrator.submit)
        self.scheduler.start()
        self.workflows = WorkflowEngine(self.workspace.workflows_dir, self._workflow_tool_executor, self._send_message)
        self.telegram: Optional[TelegramConnector] = None
        self.discord: Optional[DiscordWebhookConnector] = None
        self.slack: Optional[SlackWebhookConnector] = None
        self.slack_bot: Optional[SlackBotConnector] = None
        self.whatsapp: Optional[WhatsAppTwilioConnector] = None
        if self.config.provider_default and hasattr(self.ai, "_select_provider"):
            self.ai._select_provider(preferred=self.config.provider_default)
        if self.config.telegram_bot_token:
            self.telegram = TelegramConnector(self.config.telegram_bot_token, self._handle_connector_message)
            self.telegram.start()
        if self.config.discord_webhooks:
            self.discord = DiscordWebhookConnector(self.config.discord_webhooks)
        if self.config.slack_webhooks:
            self.slack = SlackWebhookConnector(self.config.slack_webhooks)
        if self.config.slack_bot_token and self.config.slack_signing_secret:
            self.slack_bot = SlackBotConnector(self.config.slack_bot_token, self.config.slack_signing_secret, self._handle_connector_message)
        if self.config.whatsapp_account_sid and self.config.whatsapp_auth_token and self.config.whatsapp_from_number:
            self.whatsapp = WhatsAppTwilioConnector(
                self.config.whatsapp_account_sid,
                self.config.whatsapp_auth_token,
                self.config.whatsapp_from_number,
                self._handle_connector_message,
            )

    def ensure_default_session(self) -> str:
        existing = self.sessions.list()
        if existing:
            return existing[0]["id"]
        return self.sessions.create(name="default", profile="coding").id

    def _agent_system_prompt(self) -> str:
        parts: List[str] = []
        for name in ["SOUL.md", "AGENTS.md", "TOOLS.md"]:
            path = self.workspace.root / name
            if path.exists():
                parts.append(path.read_text(encoding="utf-8"))
        return "\n\n".join(parts)

    def allowed_tools_for_session(self, session_id: str) -> set[str]:
        session = self.sessions.require(session_id)
        policy = self.config.agent_policy(session.name)
        return resolve_allowed_tool_names(
            profile=session.profile or policy.profile,
            config_allow=self.config.tools_allow,
            config_deny=self.config.tools_deny,
            policy_allow=policy.allow,
            policy_deny=policy.deny,
            known_names=self.catalog.names(),
            group_map=self.catalog.group_map(),
        )

    def run_turn(self, session_id: str, user_text: str, max_rounds: int = 4) -> Dict[str, Any]:
        session = self.sessions.require(session_id)
        self.sessions.append_message(session.id, "user", user_text)
        self.sessions.set_status(session.id, "running")
        self.memory.remember("user", session.id, user_text, {"role": "user"})
        messages: List[Dict[str, Any]] = [{"role": "system", "content": self._agent_system_prompt()}]
        messages.extend({"role": row["role"], "content": row["content"]} for row in self.sessions.history(session.id, limit=20))
        allowed = self.allowed_tools_for_session(session.id)
        tool_defs = self.catalog.definitions(allowed)

        for _ in range(max_rounds):
            response = self.ai.chat(messages, tools=tool_defs)
            if response.get("error"):
                self.sessions.set_status(session.id, "error")
                return {"ok": False, "error": response["error"], "session_id": session.id}
            message = response.get("choices", [{}])[0].get("message", {})
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                content = str(message.get("content", "")).strip()
                self.sessions.append_message(session.id, "assistant", content)
                self.sessions.set_status(session.id, "idle")
                self.memory.remember("assistant", session.id, content, {"role": "assistant"})
                return {"ok": True, "session_id": session.id, "content": content}

            tool_call = tool_calls[0]
            tool_name = tool_call.get("function", {}).get("name", "")
            if tool_name not in allowed:
                error = f"Tool not allowed for session profile: {tool_name}"
                self.sessions.append_message(session.id, "assistant", error)
                self.sessions.set_status(session.id, "blocked")
                return {"ok": False, "error": error, "session_id": session.id}
            raw_args = tool_call.get("function", {}).get("arguments", "{}")
            try:
                tool_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except Exception:
                tool_args = {}
            result = self.execute_tool(session.id, tool_name, tool_args)
            messages.append({"role": "assistant", "content": message.get("content", "") or f"Calling tool: {tool_name}"})
            messages.append({"role": "tool", "tool_call_id": tool_call.get("id", ""), "name": tool_name, "content": str(result.output)})
            self.memory.remember("tool", session.id, f"{tool_name}: {result.output}", {"tool_name": tool_name, "ok": result.ok})
            if not result.ok:
                self.sessions.set_status(session.id, "error")
                return {"ok": False, "error": str(result.output), "tool_name": tool_name, "session_id": session.id}

        self.sessions.set_status(session.id, "idle")
        return {"ok": False, "error": "Max tool rounds reached", "session_id": session.id}

    def execute_tool(self, session_id: str, tool_name: str, args: Dict[str, Any]) -> ToolExecutionResult:
        try:
            if tool_name == "sessions_list":
                return ToolExecutionResult(tool_name, True, self.sessions.list())
            if tool_name == "sessions_history":
                return ToolExecutionResult(tool_name, True, self.sessions.history(args["session_id"], int(args.get("limit", 30))))
            if tool_name == "sessions_send":
                self.sessions.append_message(args["session_id"], "user", args["content"])
                return ToolExecutionResult(tool_name, True, {"queued": True, "session_id": args["session_id"]})
            if tool_name in {"sessions_spawn", "subagents"}:
                child = self.sessions.spawn(args["parent_id"], args["name"], str(args.get("profile", "coding")))
                return ToolExecutionResult(tool_name, True, {"session_id": child.id, "name": child.name, "profile": child.profile})
            if tool_name == "sessions_yield":
                self.sessions.set_status(args["session_id"], "yielded")
                return ToolExecutionResult(tool_name, True, {"session_id": args["session_id"], "status": "yielded"})
            if tool_name == "session_status":
                return ToolExecutionResult(tool_name, True, self.sessions.status(args["session_id"]))
            if tool_name == "memory_search":
                return ToolExecutionResult(tool_name, True, self.memory.search(args["query"], int(args.get("limit", 8))))
            if tool_name == "memory_get":
                return ToolExecutionResult(tool_name, True, self.memory.get_recent(str(args.get("session_id", "")), int(args.get("limit", 10))))
            if tool_name == "web_fetch":
                response = requests.get(args["url"], timeout=10)
                preview = response.text[:4000] if response.ok else f"http {response.status_code}"
                return ToolExecutionResult(tool_name, response.ok, preview)
            if tool_name == "x_search":
                return ToolExecutionResult(tool_name, False, "X search is not configured in this local build")
            if tool_name == "canvas_present":
                return ToolExecutionResult(tool_name, True, self.canvas.present(args["content"], str(args.get("title", "Canvas Card")), str(args.get("kind", "note"))))
            if tool_name == "canvas_eval":
                return ToolExecutionResult(tool_name, True, self.canvas.evaluate(args["expression"]))
            if tool_name == "canvas_snapshot":
                return ToolExecutionResult(tool_name, True, self.canvas.snapshot())
            if tool_name == "cron_list":
                return ToolExecutionResult(tool_name, True, self._load_cron_jobs())
            if tool_name == "cron_add":
                jobs = self._load_cron_jobs()
                jobs = [job for job in jobs if job.get("name") != args["name"]]
                jobs.append(
                    {
                        "name": args["name"],
                        "schedule": args["schedule"],
                        "prompt": args["prompt"],
                        "session_id": session_id,
                        "created_at": self._now(),
                        "last_run": "",
                        "next_run": "",
                    }
                )
                self._save_cron_jobs(jobs)
                return ToolExecutionResult(tool_name, True, {"saved": True, "name": args["name"]})
            if tool_name == "cron_remove":
                jobs = [job for job in self._load_cron_jobs() if job.get("name") != args["name"]]
                self._save_cron_jobs(jobs)
                return ToolExecutionResult(tool_name, True, {"removed": True, "name": args["name"]})
            if tool_name == "gateway_status":
                return ToolExecutionResult(tool_name, True, self.gateway_status())
            if tool_name == "gateway_restart":
                return ToolExecutionResult(tool_name, True, {"restart_requested": True, "note": "Manual process restart required in local mode"})
            if tool_name == "config_schema_lookup":
                return ToolExecutionResult(tool_name, True, self.config_lookup(args["path"]))
            if tool_name == "workflows_list":
                return ToolExecutionResult(tool_name, True, self.workflows.list_workflows())
            if tool_name == "workflow_run":
                return ToolExecutionResult(tool_name, True, self.workflows.run_named(args["name"], args.get("payload", {}), session_id=session_id))
            if tool_name == "webhook_trigger":
                return ToolExecutionResult(tool_name, True, self.workflows.trigger_webhook(args["name"], args.get("payload", {}), session_id=session_id))
            if tool_name == "nodes_list":
                return ToolExecutionResult(tool_name, True, self.nodes.list_nodes())
            if tool_name == "node_pair":
                return ToolExecutionResult(tool_name, True, self.nodes.create_pairing(str(args.get("label", "mobile"))))
            if tool_name == "node_notify":
                return ToolExecutionResult(tool_name, True, self.nodes.notify(args["node_id"], args["message"]))
            if tool_name == "node_capture_screen":
                return ToolExecutionResult(tool_name, True, {"node_id": args["node_id"], "screen": self.nodes.screen(args["node_id"])})
            if tool_name == "node_capture_camera":
                return ToolExecutionResult(tool_name, True, {"node_id": args["node_id"], "camera": self.nodes.camera(args["node_id"])})
            if tool_name == "node_location":
                return ToolExecutionResult(tool_name, True, self.nodes.location(args["node_id"]))
            if tool_name == "message_send":
                return ToolExecutionResult(tool_name, True, self._send_message(args["target"], args["content"]))
            if tool_name in {"image_analyze", "image_generate", "music_generate", "video_generate", "tts"}:
                return ToolExecutionResult(tool_name, False, f"{tool_name} is scaffolded but not wired to an external integration yet")
            normalized_args = self._normalize_tool_args(tool_name, args)
            return ToolExecutionResult(tool_name, True, AdvancedTools.execute_tracked(tool_name, normalized_args, ai_model=self.ai))
        except Exception as exc:
            return ToolExecutionResult(tool_name, False, str(exc))

    def gateway_status(self) -> Dict[str, Any]:
        recent_memory = self.memory.get_recent(limit=20)
        tool_rows = self.catalog.list()
        stubbed_tools = [row["name"] for row in tool_rows if not row.get("implemented", False)]
        return {
            "workspace_root": str(self.workspace.root),
            "deployment_mode": self.config.deployment_mode,
            "auth_required": self.auth.requires_auth(self.config.deployment_mode),
            "signed_in": self.auth.is_signed_in(),
            "current_user": self.auth.current_user(),
            "session_count": len(self.sessions.list()),
            "provider": getattr(self.ai, "provider", ""),
            "provider_error": getattr(self.ai, "_provider_error", ""),
            "tool_count": len(self.catalog.names()),
            "implemented_tool_count": len([row for row in tool_rows if row.get("implemented", False)]),
            "stubbed_tool_count": len(stubbed_tools),
            "stubbed_tools": stubbed_tools,
            "memory_entries": len(recent_memory),
            "recent_memory_kinds": [row.get("kind", "") for row in recent_memory[-5:]],
            "node_count": len(self.nodes.list_nodes()),
            "canvas_cards": len(self.canvas.snapshot().get("cards", [])),
            "job_count": len(self.orchestrator.jobs()),
            "telegram_enabled": bool(self.telegram),
            "discord_enabled": bool(self.discord),
            "slack_enabled": bool(self.slack),
            "slack_bot_enabled": bool(self.slack_bot),
            "whatsapp_enabled": bool(self.whatsapp),
            "cron_count": len(self._load_cron_jobs()),
            "workflow_count": len(self.workflows.list_workflows()),
            "services": self.service_state,
        }

    def config_lookup(self, path: str) -> Any:
        schema = {
            "gateway.host": self.config.host,
            "gateway.port": self.config.port,
            "gateway.dashboard_port": self.config.dashboard_port,
            "workspace.root": str(self.config.workspace_root),
            "provider.default": self.config.provider_default,
            "tools.allow": self.config.tools_allow,
            "tools.deny": self.config.tools_deny,
            "messaging.telegram_bot_token": bool(self.config.telegram_bot_token),
            "messaging.telegram_default_chat_id": self.config.telegram_default_chat_id,
            "messaging.discord_webhooks": list(self.config.discord_webhooks.keys()),
            "messaging.slack_webhooks": list(self.config.slack_webhooks.keys()),
            "messaging.slack_bot_token": bool(self.config.slack_bot_token),
            "messaging.slack_signing_secret": bool(self.config.slack_signing_secret),
            "messaging.whatsapp_account_sid": bool(self.config.whatsapp_account_sid),
            "messaging.whatsapp_from_number": self.config.whatsapp_from_number,
            "workflows.list": [item["name"] for item in self.workflows.list_workflows()],
            "auth.enabled": self.config.auth_enabled,
            "auth.clerk_publishable_key": bool(self.config.clerk_publishable_key),
            "auth.webhook_bearer_token": bool(self.config.webhook_bearer_token),
        }
        return schema.get(path, None)

    def _load_cron_jobs(self) -> List[Dict[str, Any]]:
        if not self.cron_path.exists():
            return []
        try:
            return json.loads(self.cron_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_cron_jobs(self, jobs: List[Dict[str, Any]]):
        self.cron_path.write_text(json.dumps(jobs, indent=2), encoding="utf-8")

    def _now(self) -> str:
        from datetime import datetime

        return datetime.now().isoformat()

    def _normalize_tool_args(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(args)
        path_keys = {"path", "directory", "source", "destination", "cwd"}
        if tool_name in {
            "read_file",
            "write_file",
            "create_directory",
            "list_directory",
            "search_files",
            "file_operations",
            "observe_environment",
            "run_shell_command",
        }:
            for key in path_keys:
                value = normalized.get(key)
                if isinstance(value, str) and value and not Path(value).is_absolute():
                    normalized[key] = str((self.workspace.root / value).resolve())
        return normalized

    def _send_message(self, target: str, content: str) -> Dict[str, Any]:
        if target.startswith("telegram:"):
            if not self.telegram:
                raise RuntimeError("telegram connector is not configured")
            chat_id = target.split(":", 1)[1]
            return self.telegram.send_message(chat_id, content)
        if target.startswith("discord:"):
            if not self.discord:
                raise RuntimeError("discord connector is not configured")
            webhook_name = target.split(":", 1)[1]
            return self.discord.send_message(webhook_name, content)
        if target.startswith("slack:"):
            channel_or_name = target.split(":", 1)[1]
            if self.slack_bot and (channel_or_name.startswith("C") or channel_or_name.startswith("D")):
                return self.slack_bot.send_message(channel_or_name, content)
            if self.slack:
                return self.slack.send_message(channel_or_name, content)
            raise RuntimeError("slack connector is not configured")
        if target.startswith("whatsapp:"):
            if not self.whatsapp:
                raise RuntimeError("whatsapp connector is not configured")
            number = target.split(":", 1)[1]
            if not number.startswith("whatsapp:"):
                number = f"whatsapp:{number}"
            return self.whatsapp.send_message(number, content)
        if target.startswith("session:"):
            session_id = target.split(":", 1)[1]
            self.sessions.append_message(session_id, "assistant", content)
            return {"delivered": True, "target": target}
        raise RuntimeError(f"unsupported messaging target: {target}")

    def _handle_connector_message(self, payload: Dict[str, Any]):
        connector = payload.get("connector", "connector")
        target_id = payload.get("chat_id") or payload.get("user_id") or "default"
        session_name = f"{connector}_{target_id}"
        session = next((row for row in self.sessions.list() if row["name"] == session_name), None)
        if session:
            session_id = session["id"]
        else:
            session_id = self.sessions.create(name=session_name, profile="messaging", target=f"{connector}:{target_id}").id
        job = self.orchestrator.submit("connector_message", {"session_id": session_id, "text": payload.get("text", ""), "target": f"{connector}:{target_id}"})
        self.memory.remember("connector", session_id, payload.get("text", ""), {"connector": connector, "job_id": job["job_id"]})

    def _handle_job(self, job_type: str, payload: Dict[str, Any]) -> Any:
        if job_type == "connector_message":
            result = self.run_turn(payload["session_id"], payload["text"])
            if result.get("ok") and result.get("content") and payload.get("target"):
                self._send_message(payload["target"], result["content"])
            return result
        if job_type == "run_prompt":
            session_id = payload.get("session_id") or self.ensure_default_session()
            return self.run_turn(session_id, payload["text"])
        if job_type == "workflow_run":
            session_id = payload.get("session_id") or self.ensure_default_session()
            return self.workflows.run_named(payload["name"], payload.get("payload", {}), session_id=session_id)
        raise RuntimeError(f"unknown job type: {job_type}")

    def handle_slack_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.slack_bot:
            raise RuntimeError("slack bot mode is not configured")
        return self.slack_bot.handle_event(payload)

    def handle_whatsapp_inbound(self, form: Dict[str, Any]) -> Dict[str, Any]:
        if not self.whatsapp:
            raise RuntimeError("whatsapp connector is not configured")
        return self.whatsapp.handle_inbound(form)

    def set_service_state(self, name: str, running: bool, host: str = "", port: int = 0):
        row = self.service_state.setdefault(name, {})
        row["running"] = bool(running)
        if host:
            row["host"] = host
        if port:
            row["port"] = int(port)

    def _workflow_tool_executor(self, tool_name: str, args: Dict[str, Any]) -> Any:
        session_id = self.ensure_default_session()
        result = self.execute_tool(session_id, tool_name, args)
        if not result.ok:
            raise RuntimeError(str(result.output))
        return result.output

    def node_manifest(self) -> Dict[str, Any]:
        return {
            "name": "CONNECT Node Contract",
            "version": 1,
            "pairing": {
                "create": "POST /api/node/pair {label}",
                "register": "POST /api/node/register {pair_code,pair_secret,node_name,platform}",
            },
            "updates": {
                "screen": "POST /api/node/screen {node_id,screen}",
                "camera": "POST /api/node/camera {node_id,camera}",
                "location": "POST /api/node/location {node_id,location}",
            },
            "polling": {
                "nodes": "GET /api/nodes",
                "canvas": "GET /api/canvas",
                "status": "GET /api/status",
            },
        }
