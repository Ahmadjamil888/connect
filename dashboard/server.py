from __future__ import annotations

import json
import os
import ast
import shutil
import threading
import time
import webbrowser
import mimetypes
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from core import model_manager
from core.runtime_session import runtime_session
from config.config import load_config, save_config
from imos.hub import delete_connection, list_connection_catalog, list_connections, upsert_connection
from service.status import read_service_status
from setup.autostart import disable_autostart, enable_autostart, safe_autostart_status
from tools.connection_auth import auth_metadata, open_connection_signin
from tools.context_transfer import build_transfer_package
from tools.email_manager import gmail_signin, gmail_status, read_email_detail, read_emails, reply_to_email, search_emails, send_email
from tools.outreach_manager import list_campaigns, run_campaign, save_campaign


@dataclass
class DashboardContext:
    workspace: Path
    state_root: Path
    html_path: Path
    session_manager: Any
    memory_store: Any
    audit_logger: Any
    cost_tracker: Any
    process_manager: Any
    task_manager: Any
    mcp_runtime: Any
    workflow_registry: Any
    skill_registry: Any
    event_bus: Any
    routing_rules: Any
    gateway: Any
    cli_channel: Any
    model_config_getter: Callable[[], dict[str, Any]]
    doctor_reporter: Callable[[], str]
    listener_service: Any | None = None
    contact_book: Any | None = None
    consent_manager: Any | None = None


class DashboardService:
    def __init__(self, context: DashboardContext, host: str = "127.0.0.1", port: int = 8766):
        self.context = context
        self.host = host
        self.port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._browser_opened = False
        self._lock = threading.Lock()
        self._provider_health_cache: list[dict[str, Any]] = []
        self._provider_health_cache_ts = 0.0
        self._doctor_report_cache = ""

    def _session_summary(self) -> dict[str, Any]:
        session = self.context.session_manager.get_active()
        duration_seconds = 0.0
        try:
            from datetime import datetime

            created_at = datetime.fromisoformat(session.created_at)
            duration_seconds = max(0.0, (datetime.utcnow() - created_at).total_seconds())
        except Exception:
            duration_seconds = 0.0
        return {
            "session_id": session.session_id,
            "name": session.name,
            "status": session.status,
            "duration_seconds": duration_seconds,
            "message_count": session.message_count,
            "provider": session.active_provider,
        }

    def _build_handler(self):
        service = self
        context = self.context
        project_root = Path(__file__).resolve().parent.parent
        env_path = project_root / ".env"
        config_dir = project_root / "config"
        routing_path = config_dir / "routing.json"
        skills_path = config_dir / "skills.json"
        workflows_path = config_dir / "workflows.json"
        tools_dir = project_root / "tools"

        def read_env() -> dict[str, str]:
            values: dict[str, str] = {}
            if not env_path.exists():
                return values
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
            return values

        def write_env(updates: dict[str, str]) -> dict[str, str]:
            values = read_env()
            for key, value in updates.items():
                if value is None:
                    values.pop(key, None)
                else:
                    values[key] = str(value)
            env_path.write_text(
                "\n".join(f"{key}={values[key]}" for key in sorted(values)) + "\n",
                encoding="utf-8",
            )
            return values

        def read_json_file(path: Path, default: Any) -> Any:
            try:
                if path.exists():
                    data = json.loads(path.read_text(encoding="utf-8"))
                    return data
            except Exception:
                pass
            return default

        def write_json_file(path: Path, payload: Any) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        def mask_key(value: str) -> str:
            clean = str(value or "").strip()
            if not clean:
                return ""
            if len(clean) <= 8:
                return "*" * len(clean)
            return f"{clean[:4]}{'*' * max(4, len(clean) - 8)}{clean[-4:]}"

        def provider_env_map() -> dict[str, dict[str, str]]:
            return {
                "anthropic": {"key": "ANTHROPIC_API_KEY", "model": "ANTHROPIC_MODEL"},
                "openai": {"key": "OPENAI_API_KEY", "model": "OPENAI_MODEL"},
                "groq": {"key": "GROQ_API_KEY", "model": "GROQ_MODEL"},
                "gemini": {"key": "GOOGLE_GEMINI_API_KEY", "model": "GOOGLE_GEMINI_MODEL"},
                "openrouter": {"key": "OPENROUTER_API_KEY", "model": "OPENROUTER_MODEL"},
                "huggingface": {"key": "HUGGINGFACE_API_KEY", "model": "HUGGINGFACE_MODEL"},
                "deepseek": {"key": "DEEPSEEK_API_KEY", "model": "DEEPSEEK_MODEL"},
                "alibaba": {"key": "ALIBABA_API_KEY", "model": "ALIBABA_MODEL"},
                "nvidia": {"key": "NVIDIA_API_KEY", "model": "NVIDIA_MODEL"},
                "together": {"key": "TOGETHER_API_KEY", "model": "TOGETHER_MODEL"},
                "mistral": {"key": "MISTRAL_API_KEY", "model": "MISTRAL_MODEL"},
                "cohere": {"key": "COHERE_API_KEY", "model": "COHERE_MODEL"},
            }

        def ensure_skills_file() -> dict[str, bool]:
            current = read_json_file(skills_path, {})
            changed = False
            for path in sorted(tools_dir.glob("*.py")):
                if path.name == "__init__.py":
                    continue
                current.setdefault(path.stem, True)
                changed = True
            for directory in sorted((project_root / "skills").glob("*")):
                if directory.is_dir():
                    current.setdefault(directory.name, True)
                    changed = True
            if changed:
                write_json_file(skills_path, current)
            return current

        def read_settings_file() -> dict[str, Any]:
            return read_json_file(config_dir / "settings.json", {})

        def write_settings_file(data: dict[str, Any]) -> dict[str, Any]:
            write_json_file(config_dir / "settings.json", data)
            return data

        def update_runtime_config(**fields: Any) -> dict[str, Any]:
            cfg = load_config()
            listen_cfg = cfg.setdefault("listen", {})
            if "voice_enabled" in fields:
                enabled = bool(fields.get("voice_enabled"))
                listen_cfg["enabled"] = enabled
                listen_cfg["persist"] = enabled
            if "autostart_enabled" in fields:
                cfg["autostart"] = bool(fields.get("autostart_enabled"))
            save_config(cfg)
            return cfg

        def apply_autostart(enabled: bool) -> dict[str, Any]:
            if enabled:
                return enable_autostart(project_root)
            return disable_autostart()

        def read_contacts_file() -> list[dict[str, str]]:
            items = read_json_file(config_dir / "contacts.json", [])
            return items if isinstance(items, list) else []

        def save_contacts_file(items: list[dict[str, str]]) -> list[dict[str, str]]:
            write_json_file(config_dir / "contacts.json", items)
            return items

        def workflow_items() -> list[dict[str, Any]]:
            items = read_json_file(workflows_path, [])
            return items if isinstance(items, list) else []

        def render_dashboard_html() -> str:
            return context.html_path.read_text(encoding="utf-8")

        def provider_health() -> list[dict[str, Any]]:
            now = time.time()
            if service._provider_health_cache and (now - service._provider_health_cache_ts) < 5.0:
                return list(service._provider_health_cache)
            report = context.doctor_reporter()
            service._doctor_report_cache = report
            rows: list[dict[str, Any]] = []
            in_health = False
            for raw_line in report.splitlines():
                line = raw_line.strip()
                if line == "Providers:":
                    in_health = True
                    continue
                if in_health and not line:
                    break
                if in_health:
                    parts = line.split()
                    if len(parts) >= 2:
                        rows.append({"name": parts[0].strip(), "status": parts[1].strip()})
            service._provider_health_cache = rows
            service._provider_health_cache_ts = now
            return list(rows)

        def config_models_payload() -> dict[str, Any]:
            providers = []
            for item in model_manager.load_providers():
                health = model_manager.test_provider(item["id"])
                providers.append(
                    {
                        **item,
                        "provider": item["type"],
                        "api_key_masked": mask_key(item.get("api_key", "")),
                        "status": "healthy" if health.get("ok") else "unhealthy",
                        "latency": health.get("latency", 0),
                        "error": health.get("error", ""),
                    }
                )
            default_provider = model_manager.get_default()
            return {
                "providers": providers,
                "routing": read_json_file(routing_path, {}),
                "default_provider": (default_provider or {}).get("id", ""),
            }

        def config_apikeys_payload() -> dict[str, Any]:
            env_values = read_env()
            key_rows = [
                ("Anthropic", "ANTHROPIC_API_KEY"),
                ("OpenAI", "OPENAI_API_KEY"),
                ("Groq", "GROQ_API_KEY"),
                ("Gemini", "GOOGLE_GEMINI_API_KEY"),
                ("OpenRouter", "OPENROUTER_API_KEY"),
                ("Hugging Face", "HUGGINGFACE_API_KEY"),
                ("DeepSeek", "DEEPSEEK_API_KEY"),
                ("Alibaba Cloud", "ALIBABA_API_KEY"),
                ("NVIDIA", "NVIDIA_API_KEY"),
                ("Together", "TOGETHER_API_KEY"),
                ("Mistral", "MISTRAL_API_KEY"),
                ("Cohere", "COHERE_API_KEY"),
                ("ElevenLabs", "ELEVENLABS_API_KEY"),
                ("Telegram", "IMOS_TELEGRAM_BOT_TOKEN"),
                ("Email SMTP", "EMAIL_PASSWORD"),
                ("Voice API", "VOICE_API_KEY"),
            ]
            items = []
            for service_name, env_key in key_rows:
                value = env_values.get(env_key, "")
                items.append(
                    {
                        "service": service_name,
                        "env_key": env_key,
                        "key_masked": mask_key(value),
                        "status": "configured" if value else "missing",
                    }
                )
            for provider in model_manager.load_providers():
                if provider.get("api_key"):
                    items.append(
                        {
                            "service": f"{provider['name']} Provider",
                            "env_key": f"provider:{provider['id']}",
                            "key_masked": mask_key(provider.get("api_key", "")),
                            "status": "configured",
                        }
                    )
            return {"items": items}

        def skills_payload() -> dict[str, Any]:
            enabled_map = ensure_skills_file()
            items = []
            for path in sorted((project_root / "skills").glob("*")):
                if not path.is_dir():
                    continue
                description = ""
                skill_md = path / "SKILL.md"
                if skill_md.exists():
                    description = skill_md.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
                items.append({"name": path.name, "description": description or f"{path.name} skill", "enabled": bool(enabled_map.get(path.name, True))})
            return {"items": items}

        def workflows_payload() -> dict[str, Any]:
            items = workflow_items()
            if not workflows_path.exists():
                write_json_file(workflows_path, items)
            return {"items": items}

        def integrations_payload() -> dict[str, Any]:
            env_values = read_env()
            runtime = runtime_snapshot()
            catalog = []
            for item in list_connection_catalog():
                merged = dict(item)
                merged.update(auth_metadata(str(item.get("provider", ""))))
                catalog.append(merged)
            return {
                "catalog": catalog,
                "connections": list_connections(),
                "legacy": {
                    "whatsapp": {
                        "status": os.path.exists(str(Path(os.getenv("LOCALAPPDATA", "")) / "WhatsApp" / "WhatsApp.exe")),
                        "description": "WhatsApp Desktop integration",
                    },
                    "email": {
                        "smtp_host": env_values.get("EMAIL_SMTP_SERVER", ""),
                        "smtp_port": env_values.get("EMAIL_SMTP_PORT", "587"),
                        "email_address": env_values.get("EMAIL_FROM", ""),
                        "password": mask_key(env_values.get("EMAIL_PASSWORD", "")),
                    },
                    "telegram": {"bot_token": mask_key(env_values.get("IMOS_TELEGRAM_BOT_TOKEN", ""))},
                    "mcp": {
                        "running": bool(runtime["mcp_server"]["running"]),
                        "endpoint": runtime["mcp_server"]["endpoint"],
                    },
                    "browser": {"status": "ok"},
                },
                "ide_targets": [
                    {"id": "cursor", "label": "Cursor", "available": bool(shutil.which("cursor"))},
                    {"id": "windsurf", "label": "Windsurf", "available": bool(shutil.which("windsurf"))},
                    {"id": "vscode", "label": "VS Code", "available": bool(shutil.which("code"))},
                    {"id": "claude-code", "label": "Claude Code", "available": bool(shutil.which("claude"))},
                    {"id": "codex", "label": "Codex CLI", "available": bool(shutil.which("codex"))},
                    {"id": "aider", "label": "Aider", "available": bool(shutil.which("aider"))},
                ],
                "gmail": gmail_status(),
                "outreach": {"campaigns": list_campaigns()},
            }

        def run_skill(name: str, args: dict[str, Any], *, session_id: str | None = None) -> dict[str, Any]:
            session = context.session_manager.get_active()
            skill = next((item for item in context.skill_registry.load_all() if item.name == name), None)
            if skill is None:
                return {"ok": False, "error": f"Unknown skill: {name}"}
            try:
                return skill.handler(
                    args,
                    workspace=str(context.workspace),
                    memory_store=context.memory_store,
                    session_id=session_id or session.session_id,
                    model_config=context.model_config_getter(),
                    audit_logger=context.audit_logger,
                    process_manager=context.process_manager,
                )
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        def runtime_snapshot() -> dict[str, Any]:
            session = context.session_manager.get_active()
            default_provider = context.model_config_getter()
            health_rows = []
            if default_provider:
                health_rows.append(
                    {
                        "name": default_provider.get("provider", "") or default_provider.get("type", ""),
                        "status": "configured",
                    }
                )
            processes = context.process_manager.list()
            mcp_proc = next(
                (
                    row
                    for row in processes
                    if row.get("name") == "imos-mcp-server" and str(row.get("status")) == "running"
                ),
                None,
            )
            snapshot_path = context.session_manager._snapshot_path(session.session_id)
            memory_snapshot = {}
            if snapshot_path.exists():
                try:
                    memory_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
                except Exception:
                    memory_snapshot = {}
            audit_rows = context.audit_logger.tail(120)
            tool_feed = context.session_manager.recent_tool_calls(session.session_id, limit=20)
            command_starts = [row for row in audit_rows if row.get("kind") == "command_start"]
            command_failures = [
                row
                for row in audit_rows
                if row.get("kind") == "command_end" and int((row.get("metadata") or {}).get("returncode", 0) or 0) != 0
            ]
            file_writes = [
                row
                for row in audit_rows
                if row.get("kind") == "tool_result" and str(row.get("message")) in {"write_file", "imos_write_file"}
            ]
            shell_history = []
            for row in audit_rows:
                kind = str(row.get("kind", ""))
                if kind in {"command_start", "command_end"}:
                    shell_history.append(
                        {
                            "ts": row.get("ts", ""),
                            "kind": kind,
                            "detail": row.get("message", "") or (row.get("metadata") or {}).get("command", ""),
                            "metadata": row.get("metadata") or {},
                        }
                    )
            active_operation = None
            recent_events = context.event_bus.recent(200)
            active_map: dict[str, dict[str, Any]] = {}
            for event in recent_events:
                payload = event.get("payload") or {}
                session_id = payload.get("session_id")
                if event.get("event_type") == "tool_start":
                    active_map[str(session_id)] = {
                        "tool_name": payload.get("name", ""),
                        "input_summary": payload.get("input_summary", ""),
                        "started_at": event.get("ts", ""),
                        "session_id": session_id,
                    }
                if event.get("event_type") == "tool_end":
                    active_map.pop(str(session_id), None)
            active_operation = active_map.get(str(session.session_id))
            runtime_state = runtime_session.runtime_state()
            listener_status = context.listener_service.status() if context.listener_service is not None else {"active": False, "voice_ok": False}
            return {
                "assistant_name": "IMOS",
                "provider": context.model_config_getter().get("provider", "") or context.model_config_getter().get("type", ""),
                "model": context.model_config_getter().get("model", ""),
                "workspace": str(context.workspace),
                "session": service._session_summary(),
                "sessions": [s.__dict__ for s in context.session_manager.list_sessions()],
                "tool_feed": tool_feed,
                "memory": {
                    "short_term": memory_snapshot.get("short_term", context.memory_store.recent_entries(20)),
                    "long_term": memory_snapshot.get("long_term", context.memory_store.recent_entries(40)),
                },
                "provider_health": health_rows,
                "dashboard": service.status(),
                "routing": context.routing_rules.list_rules(),
                "mcp_server": {
                    "running": bool(mcp_proc),
                    "endpoint": str((mcp_proc or {}).get("metadata", {}).get("url", "http://127.0.0.1:8765/mcp")),
                    "connected_clients": 0,
                },
                "processes": processes,
                "tasks": context.task_manager.list(50),
                "token_usage": {
                    "summary": context.cost_tracker.summary(),
                    "per_session": context.session_manager.token_usage(session.session_id),
                },
                "audit": audit_rows,
                "shell_history": shell_history[-50:],
                "metrics": {
                    "commands_run": len(command_starts),
                    "command_failures": len(command_failures),
                    "files_modified": len(file_writes),
                    "providers_healthy": len([row for row in health_rows if row.get("status") in {"ok", "healthy"}]),
                    "providers_total": len(health_rows),
                },
                "event_bus": context.event_bus.status(),
                "listener": listener_status,
                "voice": getattr(getattr(context.gateway, "voice_manager", None), "status", lambda: {"provider": "pyttsx3", "muted": False})(),
                "service": read_service_status(context.state_root),
                "autostart": safe_autostart_status(Path.cwd()),
                "contacts": {
                    "count": context.contact_book.count() if context.contact_book is not None else 0,
                },
                "consent": context.consent_manager.status() if context.consent_manager is not None else {"granted": False},
                "active_operation": active_operation,
                "runtime_state": runtime_state,
                "operations": runtime_state.get("operations", []),
                "voice_mode": listener_status.get("mode", "always-on"),
            }

        class Handler(BaseHTTPRequestHandler):
            def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
                raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_html(self, html: str, status: int = 200) -> None:
                raw = html.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_sse_headers(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()

            def _send_sse(self, payload: dict[str, Any]) -> None:
                raw = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
                self.wfile.write(raw)
                self.wfile.flush()

            def _read_json(self) -> dict[str, Any]:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                except Exception:
                    return {}

            def do_GET(self):
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)
                if parsed.path == "/api/status":
                    snapshot = runtime_snapshot()
                    snapshot["local_ide"] = "none found"
                    self._send_json(snapshot)
                    return
                if parsed.path == "/api/events" or parsed.path == "/events":
                    self._send_sse_headers()
                    last_event_id = 0
                    try:
                        while True:
                            payload = runtime_snapshot()
                            payload["events"] = context.event_bus.since(last_event_id)
                            events = payload["events"]
                            if events:
                                last_event_id = int(events[-1]["event_id"])
                            self._send_sse(payload)
                            time.sleep(3.0)
                    except (BrokenPipeError, ConnectionResetError):
                        return
                if parsed.path == "/api/runtime_state":
                    self._send_json(runtime_session.runtime_state())
                    return
                if parsed.path == "/api/runtime":
                    self._send_json(runtime_snapshot())
                    return
                if parsed.path == "/api/sessions":
                    self._send_json({"items": [s.__dict__ for s in context.session_manager.list_sessions()]})
                    return
                if parsed.path.startswith("/api/sessions/") and parsed.path.endswith("/export"):
                    requested = parsed.path.split("/")[-2]
                    target = context.session_manager.get(requested) or context.session_manager.get_by_id(requested)
                    if target is None:
                        self._send_json({"ok": False, "error": "Session not found"}, status=404)
                        return
                    payload = context.session_manager.export_session(target.name)
                    export_path = Path(payload.get("export_path", ""))
                    if not export_path.exists():
                        self._send_json({"ok": False, "error": "Export failed"}, status=500)
                        return
                    raw = export_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Disposition", f"attachment; filename={export_path.name}")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                if parsed.path.startswith("/api/sessions/") and parsed.path.endswith("/transfer"):
                    requested = parsed.path.split("/")[-2]
                    provider = str((params.get("provider") or ["generic"])[0]).strip() or "generic"
                    target = context.session_manager.get(requested) or context.session_manager.get_by_id(requested)
                    if target is None:
                        self._send_json({"ok": False, "error": "Session not found"}, status=404)
                        return
                    try:
                        payload = build_transfer_package(context.session_manager, target.name, target=provider)
                    except KeyError:
                        self._send_json({"ok": False, "error": "Session not found"}, status=404)
                        return
                    self._send_json(payload)
                    return
                if parsed.path.startswith("/api/sessions/"):
                    requested = parsed.path.rsplit("/", 1)[-1]
                    self._send_json({"items": context.session_manager.history_by_id(requested, limit=200)})
                    return
                if parsed.path == "/api/gmail":
                    action = str((params.get("action") or ["status"])[0]).strip().lower()
                    if action == "status":
                        self._send_json(gmail_status())
                        return
                    if action == "signin":
                        self._send_json(gmail_signin())
                        return
                    if action == "inbox":
                        count = int(str((params.get("count") or ["10"])[0]).strip() or "10")
                        self._send_json({"ok": True, "items": read_emails(count=count)})
                        return
                    if action == "search":
                        query = str((params.get("query") or [""])[0]).strip()
                        self._send_json({"ok": True, "items": search_emails(query)})
                        return
                    if action == "read":
                        email_id = str((params.get("id") or [""])[0]).strip()
                        self._send_json({"ok": True, "item": read_email_detail(email_id)})
                        return
                if parsed.path == "/api/outreach":
                    self._send_json({"ok": True, "items": list_campaigns()})
                    return
                if parsed.path == "/api/memory":
                    snapshot = runtime_snapshot()["memory"]
                    self._send_json(
                        {
                            "short_term": snapshot.get("short_term", []),
                            "long_term": snapshot.get("long_term", []),
                            "items": context.memory_store.recent_entries(40),
                        }
                    )
                    return
                if parsed.path == "/api/cost":
                    self._send_json(
                        {
                            **context.cost_tracker.summary(),
                            "per_session": context.session_manager.token_usage(session.session_id),
                        }
                    )
                    return
                if parsed.path == "/api/processes":
                    items = context.process_manager.list()
                    for item in items:
                        item["log_tail"] = context.process_manager.tail_log(item["process_id"], 1200)
                    self._send_json({"items": items})
                    return
                if parsed.path == "/api/tasks":
                    self._send_json({"items": context.task_manager.list(50)})
                    return
                if parsed.path == "/api/audit":
                    snapshot = runtime_snapshot()
                    self._send_json({"items": snapshot["audit"], "tool_calls": snapshot["tool_feed"]})
                    return
                if parsed.path == "/api/mcp":
                    self._send_json({"servers": context.mcp_runtime.list_servers(), "tools": context.mcp_runtime.list_tools(), "connected_clients": 0})
                    return
                if parsed.path == "/api/doctor":
                    report = service._doctor_report_cache or context.doctor_reporter()
                    service._doctor_report_cache = report
                    self._send_json({"report": report})
                    return
                if parsed.path == "/api/config/models":
                    self._send_json(config_models_payload())
                    return
                if parsed.path == "/api/models":
                    self._send_json(config_models_payload())
                    return
                if parsed.path == "/api/models/list":
                    provider_id = str((params.get("id") or [""])[0]).strip()
                    if not provider_id:
                        self._send_json({"ok": False, "error": "Missing id"}, status=400)
                        return
                    try:
                        self._send_json({"ok": True, "models": model_manager.list_models(provider_id)})
                    except Exception as exc:
                        self._send_json({"ok": False, "error": str(exc)}, status=500)
                    return
                if parsed.path == "/api/config/apikeys":
                    self._send_json(config_apikeys_payload())
                    return
                if parsed.path == "/api/apikeys":
                    self._send_json(config_apikeys_payload())
                    return
                if parsed.path == "/api/skills":
                    self._send_json(skills_payload())
                    return
                if parsed.path == "/api/integrations":
                    self._send_json(integrations_payload())
                    return
                if parsed.path == "/api/workflows":
                    self._send_json(workflows_payload())
                    return
                if parsed.path == "/api/settings":
                    env_values = read_env()
                    autostart = safe_autostart_status(project_root)
                    listener = context.listener_service.status() if context.listener_service is not None else {"active": False, "mode": "always-on"}
                    self._send_json(
                        {
                            **read_settings_file(),
                            "assistant_name": "IMOS",
                            "wake_word": "IMOS",
                            "voice_mode": listener.get("mode", "always-on"),
                            "voice_enabled": str(env_values.get("IMOS_VOICE_ENABLED", "true")).lower() == "true",
                            "dashboard_port": int(env_values.get("DASHBOARD_PORT", self.server.server_address[1])),
                            "autostart": autostart,
                            "active_session": context.session_manager.get_active().__dict__,
                            "help_commands": [
                                "/gmail status",
                                "/gmail inbox 10",
                                "/outreach list",
                                "/outreach create <name>|<subject>|<body>|<leads>",
                                "/session transfer claude",
                                "/publish vercel",
                            ],
                        }
                    )
                    return
                if parsed.path == "/api/routing":
                    self._send_json({"items": context.routing_rules.list_rules()})
                    return
                if parsed.path == "/api/contacts":
                    if context.contact_book is not None:
                        self._send_json({"items": [{"name": name, "number": number} for name, number in sorted(context.contact_book.list().items())]})
                    else:
                        self._send_json({"items": read_contacts_file()})
                    return
                if parsed.path == "/api/voice/status":
                    listener = context.listener_service.status() if context.listener_service is not None else {"active": False, "mode": "always-on"}
                    voice = getattr(getattr(context.gateway, "voice_manager", None), "status", lambda: {"provider": "pyttsx3", "voice_id": ""})()
                    self._send_json(
                        {
                            "assistant_name": "IMOS",
                            "listener_status": "active" if listener.get("active") else "inactive",
                            "active": bool(listener.get("active")),
                            "wake_word": "IMOS",
                            "mode": listener.get("mode", "always-on"),
                            "model": listener.get("command_model", "base"),
                            "model_error": listener.get("model_error", ""),
                            "voice_provider": voice.get("provider", "pyttsx3"),
                            "voice_name": voice.get("voice_id", ""),
                        }
                    )
                    return
                if parsed.path == "/api/weather":
                    self._send_json(run_skill("weather", {}))
                    return
                if parsed.path == "/api/news":
                    self._send_json(run_skill("news", {"limit": 4}))
                    return
                if parsed.path == "/api/chat":
                    self._send_json({"ok": False, "error": "POST required"}, status=405)
                    return
                self._send_html(render_dashboard_html())

            def do_POST(self):
                parsed = urlparse(self.path)
                method = self.command.upper()
                if parsed.path == "/api/chat":
                    payload = self._read_json()
                    text = str(payload.get("text", "")).strip()
                    if not text:
                        self._send_json({"ok": False, "error": "Missing text"}, status=400)
                        return
                    session_hint = context.session_manager.get_active().name
                    envelope = context.cli_channel.normalize(
                        user_id="dashboard-user",
                        text=text,
                        session_hint=session_hint,
                        source="dashboard",
                    )
                    result = context.gateway.handle(envelope, str(context.workspace), context.model_config_getter())
                    self._send_json({"ok": True, "response": result.output, "session_id": context.session_manager.get_active().session_id})
                    return
                if parsed.path == "/api/prompt":
                    payload = self._read_json()
                    text = str(payload.get("prompt", "")).strip()
                    if not text:
                        self.send_response(400)
                        self.end_headers()
                        return
                    envelope = context.cli_channel.normalize(
                        user_id="dashboard-user",
                        text=text,
                        session_hint=context.session_manager.get_active().name,
                        source="dashboard",
                    )
                    self._send_sse_headers()

                    def emit_token(token: str) -> None:
                        self._send_sse({"type": "token", "text": token})

                    try:
                        result = context.gateway.handle_with_meta(
                            envelope,
                            str(context.workspace),
                            context.model_config_getter(),
                            on_text_delta=emit_token,
                        )
                        self._send_sse({
                            "type": "done",
                            "response": result.get("output", ""),
                            "session_id": context.session_manager.get_active().session_id,
                            "usage": result.get("usage", {}),
                        })
                    except Exception as exc:
                        self._send_sse({"type": "error", "error": str(exc)})
                    return
                if parsed.path == "/api/config/models":
                    payload = self._read_json()
                    provider = str(payload.get("provider", "")).strip().lower()
                    if provider not in provider_env_map():
                        self._send_json({"ok": False, "error": "Unknown provider"}, status=400)
                        return
                    mapping = provider_env_map()[provider]
                    updates = {"AI_PROVIDER": provider}
                    if "api_key" in payload:
                        updates[mapping["key"]] = str(payload.get("api_key", "")).strip()
                    if payload.get("model"):
                        updates[mapping["model"]] = str(payload.get("model", "")).strip()
                    write_env(updates)
                    self._send_json({"ok": True, **config_models_payload()})
                    return
                if parsed.path == "/api/models" and method == "POST":
                    payload = self._read_json()
                    provider = model_manager.add_provider(payload)
                    self._send_json({"ok": True, "provider": provider, **config_models_payload()})
                    return
                if parsed.path.startswith("/api/models/") and parsed.path.endswith("/default") and method == "POST":
                    provider_id = parsed.path.split("/")[-2]
                    try:
                        provider = model_manager.set_default(provider_id)
                    except KeyError:
                        self._send_json({"ok": False, "error": "Provider not found"}, status=404)
                        return
                    self._send_json({"ok": True, "provider": provider, **config_models_payload()})
                    return
                if parsed.path == "/api/models/test" and method == "POST":
                    payload = self._read_json()
                    provider_id = str(payload.get("id", "")).strip()
                    if not provider_id and isinstance(payload.get("provider"), dict):
                        temp = payload["provider"]
                        temp.setdefault("id", f"test-{int(time.time())}")
                        provider = model_manager._normalize_provider(temp)
                        result = model_manager.test_provider(model_manager.add_provider(provider)["id"])
                        model_manager.remove_provider(provider["id"])
                    elif provider_id:
                        result = model_manager.test_provider(provider_id)
                    else:
                        self._send_json({"ok": False, "error": "Missing id"}, status=400)
                        return
                    self._send_json(result)
                    return
                if parsed.path == "/api/config/apikeys":
                    payload = self._read_json()
                    env_key = str(payload.get("env_key", "")).strip()
                    value = str(payload.get("value", "")).strip()
                    if not env_key:
                        self._send_json({"ok": False, "error": "Missing env_key"}, status=400)
                        return
                    write_env({env_key: value})
                    self._send_json({"ok": True, **config_apikeys_payload()})
                    return
                if parsed.path == "/api/apikeys" and method == "POST":
                    payload = self._read_json()
                    service = str(payload.get("service", "")).strip()
                    env_key = str(payload.get("env_key", "")).strip()
                    value = str(payload.get("value", "")).strip()
                    if env_key.startswith("provider:"):
                        provider_id = env_key.split(":", 1)[1]
                        model_manager.update_provider(provider_id, {"api_key": value})
                        self._send_json({"ok": True, **config_apikeys_payload()})
                        return
                    if not env_key:
                        env_key = service.upper().replace(" ", "_")
                    write_env({env_key: value})
                    self._send_json({"ok": True, **config_apikeys_payload()})
                    return
                if parsed.path == "/api/apikeys/test" and method == "POST":
                    payload = self._read_json()
                    env_key = str(payload.get("env_key", "")).strip()
                    value = str(payload.get("value", "")).strip()
                    ok = bool(value or read_env().get(env_key, ""))
                    self._send_json({"ok": ok, "status": "healthy" if ok else "missing"})
                    return
                if parsed.path == "/api/config/skills":
                    payload = self._read_json()
                    name = str(payload.get("name", "")).strip()
                    enabled = bool(payload.get("enabled", False))
                    current = read_json_file(skills_path, {})
                    current[name] = enabled
                    write_json_file(skills_path, current)
                    self._send_json({"ok": True, **skills_payload()})
                    return
                if parsed.path.startswith("/api/skills/") and parsed.path.endswith("/toggle") and method == "POST":
                    payload = self._read_json()
                    name = parsed.path.split("/")[-2]
                    current = ensure_skills_file()
                    current[name] = bool(payload.get("enabled", not current.get(name, True)))
                    write_json_file(skills_path, current)
                    self._send_json({"ok": True, **skills_payload()})
                    return
                if parsed.path == "/api/skills/refresh" and method == "POST":
                    ensure_skills_file()
                    self._send_json({"ok": True, **skills_payload()})
                    return
                if parsed.path == "/api/workflows":
                    payload = self._read_json()
                    name = str(payload.get("name", "")).strip()
                    if not name:
                        self._send_json({"ok": False, "error": "Missing workflow name"}, status=400)
                        return
                    current = read_json_file(workflows_path, [])
                    filtered = [row for row in current if str(row.get("name", "")).strip() != name]
                    filtered.append(
                        {
                            "name": name,
                            "trigger": str(payload.get("trigger", "manual")).strip() or "manual",
                            "prompt": str(payload.get("prompt", "")).strip(),
                            "last_run": str(payload.get("last_run", "never")).strip() or "never",
                        }
                    )
                    write_json_file(workflows_path, filtered)
                    self._send_json({"ok": True, **workflows_payload()})
                    return
                if parsed.path.startswith("/api/workflows/") and parsed.path.endswith("/run") and method == "POST":
                    workflow_id = parsed.path.split("/")[-2]
                    items = workflow_items()
                    row = next((item for item in items if str(item.get("id", item.get("name", ""))) == workflow_id), None)
                    if row is None:
                        self._send_json({"ok": False, "error": "Workflow not found"}, status=404)
                        return
                    envelope = context.cli_channel.normalize(
                        user_id="dashboard-user",
                        text=str(row.get("trigger") or row.get("prompt") or row.get("name")),
                        session_hint=context.session_manager.get_active().name,
                        source="dashboard",
                    )
                    result = context.gateway.handle(envelope, str(context.workspace), context.model_config_getter())
                    row["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    row["status"] = "completed"
                    write_json_file(workflows_path, items)
                    self._send_json({"ok": True, "output": result.output, **workflows_payload()})
                    return
                if parsed.path == "/api/config/integrations":
                    payload = self._read_json()
                    updates = {
                        "IMOS_TELEGRAM_BOT_TOKEN": str(payload.get("telegram_token", "")).strip(),
                        "EMAIL_SMTP_SERVER": str(payload.get("smtp_host", "")).strip(),
                        "EMAIL_SMTP_PORT": str(payload.get("smtp_port", "")).strip(),
                        "EMAIL_FROM": str(payload.get("smtp_user", "")).strip(),
                        "EMAIL_PASSWORD": str(payload.get("smtp_password", "")).strip(),
                        "MCP_ENDPOINT": str(payload.get("mcp_endpoint", "")).strip(),
                        "MCP_ENABLED": "true" if bool(payload.get("mcp_enabled", False)) else "false",
                    }
                    write_env(updates)
                    self._send_json({"ok": True, "saved": True})
                    return
                if parsed.path == "/api/integrations/connections":
                    payload = self._read_json()
                    try:
                        connection = upsert_connection(payload)
                    except Exception as exc:
                        self._send_json({"ok": False, "error": str(exc)}, status=400)
                        return
                    self._send_json({"ok": True, "connection": connection, **integrations_payload()})
                    return
                if parsed.path == "/api/integrations/auth":
                    payload = self._read_json()
                    provider = str(payload.get("provider", "")).strip()
                    open_console = bool(payload.get("open_console", False))
                    self._send_json(open_connection_signin(provider, open_console=open_console))
                    return
                if parsed.path.startswith("/api/integrations/") and method == "POST":
                    name = parsed.path.split("/")[-1]
                    payload = self._read_json()
                    if name == "email":
                        write_env(
                            {
                                "EMAIL_SMTP_SERVER": str(payload.get("smtp_host", "")).strip(),
                                "EMAIL_SMTP_PORT": str(payload.get("smtp_port", "")).strip(),
                                "EMAIL_FROM": str(payload.get("email_address", "")).strip(),
                                "EMAIL_PASSWORD": str(payload.get("password", "")).strip(),
                            }
                        )
                    elif name == "telegram":
                        write_env({"IMOS_TELEGRAM_BOT_TOKEN": str(payload.get("bot_token", "")).strip()})
                    elif name == "mcp":
                        write_env({"MCP_ENDPOINT": str(payload.get("endpoint", "")).strip(), "MCP_ENABLED": str(payload.get("running", False)).lower()})
                    self._send_json({"ok": True})
                    return
                if parsed.path == "/api/gmail" and method == "POST":
                    payload = self._read_json()
                    action = str(payload.get("action", "status")).strip().lower()
                    if action == "signin":
                        self._send_json(gmail_signin())
                        return
                    if action == "send":
                        self._send_json({"ok": True, "result": send_email(str(payload.get("to", "")).strip(), str(payload.get("subject", "")).strip(), str(payload.get("body", "")).strip())})
                        return
                    if action == "reply":
                        self._send_json({"ok": True, "result": reply_to_email(str(payload.get("id", "")).strip(), str(payload.get("body", "")).strip())})
                        return
                    self._send_json(gmail_status())
                    return
                if parsed.path == "/api/outreach" and method == "POST":
                    payload = self._read_json()
                    action = str(payload.get("action", "save")).strip().lower()
                    if action == "save":
                        campaign = save_campaign(payload)
                        self._send_json({"ok": True, "campaign": campaign, "items": list_campaigns()})
                        return
                    if action in {"run", "preview"}:
                        campaign_id = str(payload.get("id", "")).strip()
                        result = run_campaign(campaign_id, dry_run=action == "preview")
                        self._send_json(result)
                        return
                    self._send_json({"ok": False, "error": f"Unknown outreach action: {action}"}, status=400)
                    return
                if parsed.path == "/api/vibe/publish" and method == "POST":
                    payload = self._read_json()
                    result = run_skill("vibe_coder", {"action": "publish", "tool": str(payload.get("target", "")).strip().lower()})
                    self._send_json(result, status=200 if result.get("ok", True) else 400)
                    return
                if parsed.path == "/api/ide/automation":
                    payload = self._read_json()
                    result = run_skill(
                        "ide_orchestrator",
                        {
                            "action": str(payload.get("action", "start")).strip() or "start",
                            "target": str(payload.get("target", "cursor")).strip() or "cursor",
                            "prompt": str(payload.get("prompt", "")).strip(),
                            "project_name": str(payload.get("project_name", "")).strip(),
                            "project_path": str(payload.get("project_path", "")).strip(),
                            "wait_for_response": bool(payload.get("wait_for_response", True)),
                        },
                    )
                    self._send_json(result, status=200 if result.get("ok", True) else 400)
                    return
                if parsed.path.startswith("/api/integrations/") and parsed.path.endswith("/test") and method == "POST":
                    name = parsed.path.split("/")[-2]
                    if name == "whatsapp":
                        self._send_json({"ok": True, "status": "open requested"})
                        return
                    if name == "email":
                        self._send_json({"ok": True, "status": "configured" if read_env().get("EMAIL_SMTP_SERVER") else "missing"})
                        return
                    if name == "telegram":
                        self._send_json({"ok": bool(read_env().get("IMOS_TELEGRAM_BOT_TOKEN")), "status": "configured" if read_env().get("IMOS_TELEGRAM_BOT_TOKEN") else "missing"})
                        return
                    self._send_json({"ok": True})
                    return
                if parsed.path == "/api/config/settings":
                    payload = self._read_json()
                    cfg = read_json_file(config_dir / "dashboard.json", {})
                    cfg["port"] = int(payload.get("dashboard_port", 8766) or 8766)
                    write_json_file(config_dir / "dashboard.json", cfg)
                    autostart_enabled = bool(payload.get("autostart", False))
                    voice_enabled = bool(payload.get("voice_enabled", True))
                    update_runtime_config(autostart_enabled=autostart_enabled, voice_enabled=voice_enabled)
                    apply_autostart(autostart_enabled)
                    write_env(
                        {
                            "WAKE_WORD": "IMOS",
                            "IMOS_AUTOSTART": "true" if autostart_enabled else "false",
                            "IMOS_VOICE_ENABLED": "true" if voice_enabled else "false",
                            "DASHBOARD_PORT": str(cfg["port"]),
                        }
                    )
                    self._send_json({"ok": True, "saved": True})
                    return
                if parsed.path == "/api/settings" and method == "POST":
                    payload = self._read_json()
                    settings = read_settings_file()
                    settings.update(payload)
                    write_settings_file(settings)
                    env_updates = {}
                    env_updates["WAKE_WORD"] = "IMOS"
                    if "dashboard_port" in payload:
                        env_updates["DASHBOARD_PORT"] = str(payload.get("dashboard_port", self.server.server_address[1]))
                    if "voice_enabled" in payload:
                        env_updates["IMOS_VOICE_ENABLED"] = "true" if bool(payload.get("voice_enabled")) else "false"
                    autostart_payload = payload.get("autostart")
                    if isinstance(autostart_payload, dict) and "enabled" in autostart_payload:
                        enabled = bool(autostart_payload.get("enabled"))
                        env_updates["IMOS_AUTOSTART"] = "true" if enabled else "false"
                        apply_autostart(enabled)
                        update_runtime_config(autostart_enabled=enabled)
                    if "voice_enabled" in payload:
                        update_runtime_config(voice_enabled=bool(payload.get("voice_enabled")))
                    if env_updates:
                        write_env(env_updates)
                    self._send_json({"ok": True, **settings})
                    return
                if parsed.path == "/api/sessions" and method == "POST":
                    payload = self._read_json()
                    name = str(payload.get("name", "")).strip() or f"session-{int(time.time())}"
                    session = context.session_manager.create(name, channel="dashboard", user_id="dashboard-user")
                    self._send_json({"ok": True, "session": session.__dict__})
                    return
                if parsed.path.startswith("/api/sessions/") and parsed.path.endswith("/resume") and method == "POST":
                    session_id = parsed.path.split("/")[-2]
                    session = context.session_manager.get_by_id(session_id) or context.session_manager.get(session_id)
                    if session is None:
                        self._send_json({"ok": False, "error": "Session not found"}, status=404)
                        return
                    context.session_manager.set_active(session.name)
                    self._send_json({"ok": True, "session": context.session_manager.get_active().__dict__})
                    return
                if parsed.path == "/api/routing" and method == "POST":
                    payload = self._read_json()
                    task_type = str(payload.get("task_type", "")).strip()
                    provider = str(payload.get("provider", "")).strip()
                    context.routing_rules.set_rule(task_type, provider)
                    self._send_json({"ok": True, "items": context.routing_rules.list_rules()})
                    return
                if parsed.path == "/api/contacts" and method == "POST":
                    payload = self._read_json()
                    name = str(payload.get("name", "")).strip()
                    number = str(payload.get("number", "")).strip()
                    if context.contact_book is not None:
                        result = context.contact_book.add(name, number)
                        self._send_json({"ok": True, "item": result})
                    else:
                        items = [item for item in read_contacts_file() if item.get("name") != name]
                        items.append({"name": name, "number": number})
                        save_contacts_file(items)
                        self._send_json({"ok": True, "items": items})
                    return
                if parsed.path == "/api/voice/start" and method == "POST":
                    if context.listener_service is None:
                        self._send_json({"ok": False, "error": "Listener unavailable"}, status=500)
                        return
                    update_runtime_config(voice_enabled=True)
                    write_env({"IMOS_VOICE_ENABLED": "true"})
                    self._send_json({"ok": True, **context.listener_service.start(persist=True, daemon=True)})
                    return
                if parsed.path == "/api/voice/stop" and method == "POST":
                    if context.listener_service is None:
                        self._send_json({"ok": False, "error": "Listener unavailable"}, status=500)
                        return
                    update_runtime_config(voice_enabled=False)
                    write_env({"IMOS_VOICE_ENABLED": "false"})
                    self._send_json({"ok": True, **context.listener_service.stop()})
                    return
                if parsed.path == "/api/voice/test" and method == "POST":
                    result = getattr(getattr(context.gateway, "voice_manager", None), "speak", lambda text: {"ok": False})(getattr(getattr(context.gateway, "voice_manager", None), "test_phrase", lambda: "IMOS is ready")())
                    self._send_json(result)
                    return
                if parsed.path == "/api/voice/config" and method == "POST":
                    payload = self._read_json()
                    voice_manager = getattr(context.gateway, "voice_manager", None)
                    if voice_manager is not None and "voice_name" in payload:
                        voice_manager.set_voice(str(payload.get("voice_name", "")))
                    write_env({"WAKE_WORD": "IMOS"})
                    self._send_json({"ok": True})
                    return
                if parsed.path == "/api/chat/stream":
                    payload = self._read_json()
                    text = str(payload.get("text", "")).strip()
                    if not text:
                        self.send_response(400)
                        self.end_headers()
                        return
                    envelope = context.cli_channel.normalize(
                        user_id="dashboard-user",
                        text=text,
                        session_hint=context.session_manager.get_active().name,
                        source="dashboard",
                    )
                    self._send_sse_headers()

                    def emit_token(token: str) -> None:
                        self._send_sse({"type": "token", "text": token})

                    try:
                        result = context.gateway.handle_with_meta(envelope, str(context.workspace), context.model_config_getter(), on_text_delta=emit_token)
                        self._send_sse({"type": "done", "response": result.get("output", ""), "session_id": context.session_manager.get_active().session_id, "usage": result.get("usage", {})})
                    except Exception as exc:
                        self._send_sse({"type": "error", "error": str(exc)})
                    return
                self._send_json({"ok": False, "error": "Not found"}, status=404)

            def do_PUT(self):
                parsed = urlparse(self.path)
                payload = self._read_json()
                if parsed.path.startswith("/api/models/"):
                    provider_id = parsed.path.rsplit("/", 1)[-1]
                    try:
                        provider = model_manager.update_provider(provider_id, payload)
                    except KeyError:
                        self._send_json({"ok": False, "error": "Provider not found"}, status=404)
                        return
                    self._send_json({"ok": True, "provider": provider, **config_models_payload()})
                    return
                if parsed.path.startswith("/api/workflows/"):
                    workflow_id = parsed.path.rsplit("/", 1)[-1]
                    items = workflow_items()
                    for row in items:
                        if str(row.get("id", row.get("name", ""))) == workflow_id:
                            row.update(payload)
                            write_json_file(workflows_path, items)
                            self._send_json({"ok": True, "items": items})
                            return
                    self._send_json({"ok": False, "error": "Workflow not found"}, status=404)
                    return
                if parsed.path.startswith("/api/contacts/"):
                    name = parsed.path.rsplit("/", 1)[-1]
                    number = str(payload.get("number", "")).strip()
                    if context.contact_book is not None:
                        context.contact_book.add(name, number)
                        self._send_json({"ok": True})
                    else:
                        items = [item for item in read_contacts_file() if item.get("name") != name]
                        items.append({"name": name, "number": number})
                        save_contacts_file(items)
                        self._send_json({"ok": True, "items": items})
                    return
                self._send_json({"ok": False, "error": "Not found"}, status=404)

            def do_DELETE(self):
                parsed = urlparse(self.path)
                if parsed.path.startswith("/api/models/"):
                    provider_id = parsed.path.rsplit("/", 1)[-1]
                    removed = model_manager.remove_provider(provider_id)
                    self._send_json({"ok": removed, **config_models_payload()})
                    return
                if parsed.path.startswith("/api/integrations/connections/"):
                    connection_id = parsed.path.rsplit("/", 1)[-1]
                    delete_connection(connection_id)
                    self._send_json({"ok": True, **integrations_payload()})
                    return
                if parsed.path.startswith("/api/apikeys/"):
                    service = parsed.path.rsplit("/", 1)[-1]
                    if service.startswith("provider%3A"):
                        service = service.replace("provider%3A", "provider:")
                    if service.startswith("provider:"):
                        provider_id = service.split(":", 1)[1]
                        try:
                            model_manager.update_provider(provider_id, {"api_key": ""})
                        except KeyError:
                            pass
                    else:
                        write_env({service: ""})
                    self._send_json({"ok": True, **config_apikeys_payload()})
                    return
                if parsed.path.startswith("/api/workflows/"):
                    workflow_id = parsed.path.rsplit("/", 1)[-1]
                    items = [item for item in workflow_items() if str(item.get("id", item.get("name", ""))) != workflow_id]
                    write_json_file(workflows_path, items)
                    self._send_json({"ok": True, "items": items})
                    return
                if parsed.path.startswith("/api/sessions/"):
                    session_id = parsed.path.rsplit("/", 1)[-1]
                    session = context.session_manager.get_by_id(session_id) or context.session_manager.get(session_id)
                    if session is None:
                        self._send_json({"ok": False, "error": "Session not found"}, status=404)
                        return
                    data = context.session_manager._load_index()
                    data.pop(session.name, None)
                    context.session_manager._save_index(data)
                    self._send_json({"ok": True})
                    return
                if parsed.path.startswith("/api/routing/"):
                    task_type = parsed.path.rsplit("/", 1)[-1]
                    context.routing_rules.set_rule(task_type, "")
                    self._send_json({"ok": True, "items": context.routing_rules.list_rules()})
                    return
                if parsed.path.startswith("/api/contacts/"):
                    name = parsed.path.rsplit("/", 1)[-1]
                    if context.contact_book is not None:
                        context.contact_book.remove(name)
                        self._send_json({"ok": True})
                    else:
                        items = [item for item in read_contacts_file() if item.get("name") != name]
                        save_contacts_file(items)
                        self._send_json({"ok": True, "items": items})
                    return
                self._send_json({"ok": False, "error": "Not found"}, status=404)

            def log_message(self, format, *args):
                return

        return Handler

    def start(self, open_browser: bool = False) -> str:
        with self._lock:
            if self._server is None:
                self._server = ThreadingHTTPServer((self.host, self.port), self._build_handler())
                self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
                self._thread.start()
            url = f"http://{self.host}:{self._server.server_address[1]}"
            if open_browser:
                webbrowser.open(url + "/")
                self._browser_opened = True
            return url

    def stop(self) -> None:
        with self._lock:
            if self._server is None:
                return
            server = self._server
            self._server = None
            thread = self._thread
            self._thread = None
        server.shutdown()
        server.server_close()
        if thread is not None:
            thread.join(timeout=3)

    def status(self) -> dict[str, Any]:
        with self._lock:
            server = self._server
            thread = self._thread
            if server is None:
                return {"running": False, "url": f"http://{self.host}:{self.port}", "browser_opened": False}
            return {
                "running": bool(thread and thread.is_alive()),
                "url": f"http://{self.host}:{server.server_address[1]}",
                "browser_opened": self._browser_opened,
            }
