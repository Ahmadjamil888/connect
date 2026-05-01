"""
IMOS — Intelligent Machine Operating System
Main Flask server + dashboard + SSE streaming.

Run: python imos_server.py
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

from config.config import get_model_config, load_config
from connectai.memory import ConnectMemoryStore
from connectai.ops import (
    ApprovalPolicy,
    AuditLogger,
    CostTracker,
    ProcessRegistry,
    ShellRunner,
    TaskManager,
    TerminalSessionManager,
)
from connectai.sessions import ConnectSessionManager
from connectai.skills import SkillRegistry
from imos.hub import (
    get_voice_settings,
    list_connection_catalog,
    list_connections,
    list_model_catalog,
    list_workflows,
    save_voice_settings,
    upsert_connection,
    upsert_workflow,
    delete_connection,
)
from imos.runtime import IMOSRuntime
from imos.ui import get_ui_config, save_ui_config, setup_terminal_io
from imos.voice_loop import configure_tts, get_voice_status, speak, start_voice_loop

setup_terminal_io()

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------

WORKSPACE = Path(load_config().get("workspace", str(Path.home() / "imos_workspace")))
WORKSPACE.mkdir(parents=True, exist_ok=True)

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

STATIC_DIR = PROJECT_ROOT / "static"
STATIC_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Core services
# ---------------------------------------------------------------------------

_audit = AuditLogger(LOGS_DIR)
_approval = ApprovalPolicy(load_config, _audit)
_shell = ShellRunner(LOGS_DIR / "shell", _audit, _approval)
_processes = ProcessRegistry(LOGS_DIR / "processes", _audit)
_tasks = TaskManager(LOGS_DIR / "tasks", _audit)
_cost = CostTracker(LOGS_DIR / "cost")
_sessions = ConnectSessionManager(WORKSPACE / "sessions")
_memory = ConnectMemoryStore(WORKSPACE / "memory")
_terminals = TerminalSessionManager(LOGS_DIR / "terminals", _audit)
_skill_registry = SkillRegistry(workspace_root=WORKSPACE, bundled_root=PROJECT_ROOT / "skills")

_runtime = IMOSRuntime(
    skill_registry=_skill_registry,
    memory_store=_memory,
    shell_runner=_shell,
    process_manager=_processes,
    audit_logger=_audit,
    task_manager=_tasks,
    cost_tracker=_cost,
)

# ---------------------------------------------------------------------------
# SSE event queue
# ---------------------------------------------------------------------------

_sse_clients: List[queue.Queue] = []
_sse_lock = threading.Lock()


def _broadcast_sse(event_type: str, data: Any):
    payload = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(payload)
            except Exception:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder=str(STATIC_DIR))
CORS(app)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    dashboard_path = PROJECT_ROOT / "static" / "dashboard.html"
    if dashboard_path.exists():
        return send_from_directory(str(STATIC_DIR), "dashboard.html")
    return "<h1>IMOS Dashboard</h1><p>dashboard.html not found in static/</p>", 404


# ---------------------------------------------------------------------------
# API — auth status (for dashboard)
# ---------------------------------------------------------------------------

@app.route("/api/auth/status")
def api_auth_status():
    try:
        from imos.auth import current_user, is_authenticated
        user = current_user()
        return jsonify({
            "ok": True,
            "authenticated": is_authenticated(),
            "signed_in": user.get("signed_in", False),
            "email": user.get("email", ""),
            "user_id": user.get("user_id", ""),
        })
    except Exception as exc:
        return jsonify({"ok": False, "authenticated": False, "error": str(exc)})


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    try:
        from imos.auth import cmd_logout
        cmd_logout()
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# API — status
# ---------------------------------------------------------------------------

@app.route("/api/status")
def api_status():
    model_config = get_model_config()
    cfg = load_config()
    # Get auth state
    auth_info = {"signed_in": False, "email": "", "user_id": ""}
    try:
        from imos.auth import current_user
        auth_info = current_user()
    except Exception:
        pass
    return jsonify({
        "name": "IMOS",
        "version": "1.0.0",
        "provider": model_config.get("provider", "not configured"),
        "model": model_config.get("model", "not configured"),
        "workspace": str(WORKSPACE),
        "providers": list(cfg.get("providers", {}).keys()),
        "uptime_seconds": int(time.time() - _start_time),
        "auth": auth_info,
    })


# ---------------------------------------------------------------------------
# API — system stats
# ---------------------------------------------------------------------------

@app.route("/api/stats")
def api_stats():
    try:
        import psutil
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\" if os.name == "nt" else "/")
        net = psutil.net_io_counters()
        return jsonify({
            "ok": True,
            "cpu_percent": psutil.cpu_percent(interval=0.3),
            "cpu_count": psutil.cpu_count(),
            "ram_total_gb": round(vm.total / (1024 ** 3), 2),
            "ram_used_gb": round(vm.used / (1024 ** 3), 2),
            "ram_percent": vm.percent,
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "disk_used_gb": round(disk.used / (1024 ** 3), 2),
            "disk_percent": disk.percent,
            "net_sent_mb": round(net.bytes_sent / (1024 ** 2), 2),
            "net_recv_mb": round(net.bytes_recv / (1024 ** 2), 2),
            "uptime_seconds": int(time.time() - _start_time),
            "process_count": len(psutil.pids()),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# API — weather
# ---------------------------------------------------------------------------

@app.route("/api/weather")
def api_weather():
    city = request.args.get("city", "")
    try:
        from skills.weather.handler import run as weather_run
        result = weather_run({"city": city, "provider": "auto"})
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# API — news
# ---------------------------------------------------------------------------

@app.route("/api/news")
def api_news():
    topic = request.args.get("topic", "")
    count = int(request.args.get("count", 5))
    try:
        from skills.news.handler import run as news_run
        result = news_run({"category": topic or "general", "limit": count})
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# API — world health
# ---------------------------------------------------------------------------

@app.route("/api/health")
def api_health():
    metric = request.args.get("metric", "covid")
    try:
        from skills.world_health.handler import run as health_run
        result = health_run({"metric": metric})
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# API — processes
# ---------------------------------------------------------------------------

@app.route("/api/processes")
def api_processes():
    try:
        import psutil
        procs = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
            try:
                info = proc.info
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu_percent": round(info.get("cpu_percent") or 0, 1),
                    "memory_percent": round(info.get("memory_percent") or 0, 2),
                    "status": info.get("status", "unknown"),
                })
            except Exception:
                continue
        # Sort by CPU usage
        procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
        return jsonify({"ok": True, "items": procs[:50]})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "items": []})


# ---------------------------------------------------------------------------
# API — audit log
# ---------------------------------------------------------------------------

@app.route("/api/audit")
def api_audit():
    limit = int(request.args.get("limit", 50))
    entries = _audit.tail(limit)
    return jsonify({"ok": True, "items": entries})


# ---------------------------------------------------------------------------
# API — tasks
# ---------------------------------------------------------------------------

@app.route("/api/tasks")
def api_tasks():
    items = _tasks.list(limit=100)
    return jsonify({"ok": True, "items": items})


@app.route("/api/workflows", methods=["GET"])
def api_workflows():
    return jsonify({"ok": True, "items": list_workflows()})


@app.route("/api/workflows", methods=["POST"])
def api_workflows_upsert():
    body = request.get_json(force=True, silent=True) or {}
    try:
        item = upsert_workflow(body)
        return jsonify({"ok": True, "item": item})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# API — cost
# ---------------------------------------------------------------------------

@app.route("/api/cost")
def api_cost():
    return jsonify(_cost.summary())


# ---------------------------------------------------------------------------
# API — skills
# ---------------------------------------------------------------------------

@app.route("/api/skills")
def api_skills():
    skills = _skill_registry.load_all()
    return jsonify({
        "ok": True,
        "items": [
            {"name": s.name, "description": s.description, "source": s.source}
            for s in skills
        ],
    })


@app.route("/api/catalog/models")
def api_catalog_models():
    return jsonify({"ok": True, "items": list_model_catalog()})


@app.route("/api/catalog/connections")
def api_catalog_connections():
    return jsonify({"ok": True, "items": list_connection_catalog()})


@app.route("/api/connections", methods=["GET"])
def api_connections():
    return jsonify({"ok": True, "items": list_connections()})


@app.route("/api/connections", methods=["POST"])
def api_connections_upsert():
    body = request.get_json(force=True, silent=True) or {}
    try:
        item = upsert_connection(body)
        return jsonify({"ok": True, "item": item})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


@app.route("/api/connections/<connection_id>", methods=["DELETE"])
def api_connections_delete(connection_id: str):
    try:
        delete_connection(connection_id)
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# API — sessions
# ---------------------------------------------------------------------------

@app.route("/api/sessions")
def api_sessions():
    try:
        sessions = _sessions.list_sessions()
        return jsonify({
            "ok": True,
            "items": [
                {
                    "session_id": s.session_id,
                    "session_key": s.session_key,
                    "title": s.title,
                    "channel": s.channel,
                    "message_count": s.message_count,
                    "updated_at": s.updated_at,
                }
                for s in sessions
            ],
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "items": []})


@app.route("/api/sessions/<session_id>")
def api_session_transcript(session_id: str):
    try:
        if session_id == "default":
            return jsonify({"ok": True, "items": []})
        messages = _sessions.history_by_id(session_id, limit=50)
        return jsonify({"ok": True, "items": messages})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "items": []})


# ---------------------------------------------------------------------------
# API — chat (POST, streaming SSE)
# ---------------------------------------------------------------------------

@app.route("/api/chat", methods=["POST"])
def api_chat():
    body = request.get_json(force=True, silent=True) or {}
    user_text = str(body.get("text", "")).strip()
    session_key = str(body.get("session_id", "")).strip() or "imos-default"

    if not user_text:
        return jsonify({"ok": False, "error": "text is required"})

    model_config = get_model_config()

    # Get or create session
    session = _sessions.get_or_create(
        session_key=session_key,
        channel="dashboard",
        user_id="operator",
        title="IMOS Chat",
    )
    session_id = session.session_id

    # Load session history
    try:
        history = _sessions.history(session, limit=20)
    except Exception:
        history = []

    # Run IMOS runtime
    try:
        result = _runtime.run(
            user_text=user_text,
            session_history=history,
            session_id=session_id,
            workspace=str(WORKSPACE),
            model_config=model_config,
            return_meta=True,
        )
        if isinstance(result, dict):
            response_text = result.get("text", "")
            usage = result.get("usage", {})
        else:
            response_text = str(result)
            usage = {}
    except Exception as exc:
        response_text = f"IMOS error: {exc}"
        usage = {}

    # Save to session
    try:
        _sessions.append_message(session, "user", user_text)
        _sessions.append_message(session, "assistant", response_text)
    except Exception:
        pass

    # Broadcast to SSE
    _broadcast_sse("chat", {"role": "assistant", "content": response_text, "session_id": session_id})

    return jsonify({
        "ok": True,
        "response": response_text,
        "session_id": session_key,
        "usage": usage,
    })


# ---------------------------------------------------------------------------
# API — chat streaming (SSE token-by-token)
# ---------------------------------------------------------------------------

@app.route("/api/chat/stream", methods=["POST"])
def api_chat_stream():
    body = request.get_json(force=True, silent=True) or {}
    user_text = str(body.get("text", "")).strip()
    session_key = str(body.get("session_id", "")).strip() or "imos-default"

    if not user_text:
        return jsonify({"ok": False, "error": "text is required"})

    model_config = get_model_config()
    session = _sessions.get_or_create(
        session_key=session_key, channel="dashboard", user_id="operator", title="IMOS Chat"
    )
    try:
        history = _sessions.history(session, limit=20)
    except Exception:
        history = []

    token_buffer = []

    def generate():
        def on_delta(token: str):
            token_buffer.append(token)
            payload = json.dumps({"type": "token", "token": token}, ensure_ascii=False)
            # We can't yield from callback directly; push to queue
            delta_q.put(payload)

        delta_q: queue.Queue = queue.Queue()
        result_holder = {}

        def run_in_thread():
            try:
                result = _runtime.run(
                    user_text=user_text,
                    session_history=history,
                    session_id=session.session_id,
                    workspace=str(WORKSPACE),
                    model_config=model_config,
                    on_text_delta=on_delta,
                    return_meta=True,
                )
                result_holder["result"] = result
            except Exception as exc:
                result_holder["error"] = str(exc)
            finally:
                delta_q.put(None)  # sentinel

        t = threading.Thread(target=run_in_thread, daemon=True)
        t.start()

        full_text = []
        while True:
            item = delta_q.get()
            if item is None:
                break
            full_text.append(json.loads(item)["token"])
            yield f"data: {item}\n\n"

        # Final message
        result = result_holder.get("result", {})
        error = result_holder.get("error")
        if error:
            final_text = f"IMOS error: {error}"
        elif isinstance(result, dict):
            final_text = result.get("text", "".join(full_text))
            usage = result.get("usage", {})
        else:
            final_text = str(result) if result else "".join(full_text)
            usage = {}

        # Save session
        try:
            _sessions.append_message(session, "user", user_text)
            _sessions.append_message(session, "assistant", final_text)
        except Exception:
            pass

        done_payload = json.dumps({
            "type": "done",
            "text": final_text,
            "session_id": session_key,
            "usage": usage if isinstance(usage, dict) else {},
        }, ensure_ascii=False)
        yield f"data: {done_payload}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# API — shell execute (direct, no LLM)
# ---------------------------------------------------------------------------

@app.route("/api/shell", methods=["POST"])
def api_shell():
    body = request.get_json(force=True, silent=True) or {}
    cmd = str(body.get("command", "")).strip()
    cwd = str(body.get("cwd", str(WORKSPACE))).strip() or str(WORKSPACE)
    timeout = int(body.get("timeout", 60))
    if not cmd:
        return jsonify({"ok": False, "error": "command is required"})
    result = _shell.run(cmd, cwd=cwd, timeout=timeout)
    return jsonify({
        "ok": result.ok,
        "command": result.command,
        "cwd": result.cwd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_seconds": result.duration_seconds,
    })


# ---------------------------------------------------------------------------
# API — config / model settings
# ---------------------------------------------------------------------------

@app.route("/api/config/model", methods=["GET"])
def api_config_model_get():
    return jsonify(get_model_config())


@app.route("/api/config/ui", methods=["GET"])
def api_config_ui_get():
    return jsonify({"ok": True, **get_ui_config()})


@app.route("/api/config/ui", methods=["POST"])
def api_config_ui_set():
    body = request.get_json(force=True, silent=True) or {}
    dashboard_palette = str(body.get("dashboard_palette", "")).strip().lower() or None
    shell_palette = str(body.get("shell_palette", "")).strip().lower() or None
    try:
        data = save_ui_config(
            dashboard_palette=dashboard_palette,
            shell_palette=shell_palette,
        )
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


@app.route("/api/config/model", methods=["POST"])
def api_config_model_set():
    from config.config import save_model_config
    body = request.get_json(force=True, silent=True) or {}
    provider = str(body.get("provider", "")).strip()
    model = str(body.get("model", "")).strip()
    api_key = str(body.get("api_key", "")).strip()
    extra = body.get("extra", {}) or {}
    if not provider or not model:
        return jsonify({"ok": False, "error": "provider and model are required"})
    try:
        model_cfg = {"provider": provider, "model": model}
        if api_key:
            model_cfg["api_key"] = api_key
        model_cfg.update({k: v for k, v in extra.items() if v})
        save_model_config(model_cfg)
        # Also reload env so it takes effect immediately
        load_dotenv(PROJECT_ROOT / ".env", override=True)
        return jsonify({"ok": True, "provider": provider, "model": model})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


@app.route("/api/config/env", methods=["POST"])
def api_config_env_set():
    """Write a key=value to .env file."""
    body = request.get_json(force=True, silent=True) or {}
    key = str(body.get("key", "")).strip()
    value = str(body.get("value", "")).strip()
    if not key:
        return jsonify({"ok": False, "error": "key is required"})
    env_path = PROJECT_ROOT / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
        updated = False
        new_lines = []
        for line in lines:
            if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
                new_lines.append(f"{key}={value}")
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            new_lines.append(f"{key}={value}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        os.environ[key] = value
        return jsonify({"ok": True, "key": key})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


@app.route("/api/config/env", methods=["GET"])
def api_config_env_get():
    """Return non-secret env keys (masked values)."""
    env_path = PROJECT_ROOT / ".env"
    keys = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            # Mask secrets
            if any(word in k.upper() for word in ["KEY", "SECRET", "TOKEN", "PASSWORD"]):
                keys[k] = "***" + v[-4:] if len(v) > 4 else ("***" if v else "")
            else:
                keys[k] = v
    return jsonify({"ok": True, "keys": keys})


# ---------------------------------------------------------------------------
# API — speak (TTS)
# ---------------------------------------------------------------------------

@app.route("/api/voice/status", methods=["GET"])
def api_voice_status():
    settings = get_voice_settings()
    status = get_voice_status()
    return jsonify({"ok": True, "settings": settings, "status": status})


@app.route("/api/voice/config", methods=["POST"])
def api_voice_config():
    body = request.get_json(force=True, silent=True) or {}
    enabled = bool(body.get("enabled", True))
    voice = str(body.get("voice", "jarvis")).strip() or "jarvis"
    rate = int(body.get("rate", 175) or 175)
    wake_words = body.get("wake_words") or ["imos", "hey imos"]
    settings = save_voice_settings(enabled=enabled, voice=voice, rate=rate, wake_words=wake_words)
    configure_tts(voice=voice, rate=rate)
    return jsonify({"ok": True, "settings": settings, "status": get_voice_status()})


@app.route("/api/voice/listen", methods=["POST"])
def api_voice_listen():
    body = request.get_json(force=True, silent=True) or {}
    timeout = int(body.get("timeout", 5) or 5)
    phrase_time_limit = int(body.get("phrase_time_limit", 10) or 10)
    try:
        from connectai.voice import SpeechEngine
        result = SpeechEngine().listen(timeout=timeout, phrase_time_limit=phrase_time_limit)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


@app.route("/api/voice/speak", methods=["POST"])
@app.route("/api/speak", methods=["POST"])
def api_speak():
    body = request.get_json(force=True, silent=True) or {}
    text = str(body.get("text", "")).strip()
    if not text:
        return jsonify({"ok": False, "error": "text is required"})
    settings = get_voice_settings()
    configure_tts(voice=settings["voice"], rate=settings["rate"])
    speak(text)
    return jsonify({"ok": True, "spoken": text, "voice": settings["voice"], "rate": settings["rate"]})


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------

@app.route("/stream")
def sse_stream():
    def generate() -> Generator[str, None, None]:
        q: queue.Queue = queue.Queue(maxsize=100)
        with _sse_lock:
            _sse_clients.append(q)
        try:
            yield "data: {\"type\": \"connected\"}\n\n"
            while True:
                try:
                    payload = q.get(timeout=30)
                    yield payload
                except queue.Empty:
                    yield ": heartbeat\n\n"
        finally:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# API — terminal sessions
# ---------------------------------------------------------------------------

@app.route("/api/terminal/open", methods=["POST"])
def api_terminal_open():
    body = request.get_json(force=True, silent=True) or {}
    cwd = str(body.get("cwd", str(WORKSPACE)))
    result = _terminals.open(cwd)
    return jsonify(result)


@app.route("/api/terminal/<session_id>/write", methods=["POST"])
def api_terminal_write(session_id: str):
    body = request.get_json(force=True, silent=True) or {}
    data = str(body.get("data", ""))
    return jsonify(_terminals.write(session_id, data))


@app.route("/api/terminal/<session_id>/read")
def api_terminal_read(session_id: str):
    return jsonify(_terminals.read(session_id))


@app.route("/api/terminal/<session_id>/close", methods=["POST"])
def api_terminal_close(session_id: str):
    return jsonify(_terminals.close(session_id))


@app.route("/api/terminals")
def api_terminals():
    return jsonify({"ok": True, "items": _terminals.list()})


# ---------------------------------------------------------------------------
# API — memory
# ---------------------------------------------------------------------------

@app.route("/api/memory")
def api_memory():
    query = request.args.get("query", "")
    try:
        blocks = _memory.context_blocks(session_id="", query=query)
        return jsonify({"ok": True, "items": blocks})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "items": []})


# ---------------------------------------------------------------------------
# Startup sequence
# ---------------------------------------------------------------------------

IMOS_ASCII = r"""
  ██╗███╗   ███╗ ██████╗ ███████╗
  ██║████╗ ████║██╔═══██╗██╔════╝
  ██║██╔████╔██║██║   ██║███████╗
  ██║██║╚██╔╝██║██║   ██║╚════██║
  ██║██║ ╚═╝ ██║╚██████╔╝███████║
  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚══════╝
  Intelligent Machine Operating System v1.0
"""

_start_time = time.time()


def _test_apis():
    """Test all API connections at startup."""
    print("\n[IMOS] Testing API connections...")

    tests = [
        ("Weather API", lambda: __import__("skills.weather.handler", fromlist=["run"]).run({"city": "London"})),
        ("News API", lambda: __import__("skills.news.handler", fromlist=["run"]).run({"limit": 3})),
        ("World Health API", lambda: __import__("skills.world_health.handler", fromlist=["run"]).run({"metric": "covid"})),
        ("Wikipedia", lambda: __import__("skills.wikipedia.handler", fromlist=["run"]).run({"query": "artificial intelligence", "sentences": 2})),
        ("Joke API", lambda: __import__("skills.jokes.handler", fromlist=["run"]).run({})),
    ]

    for name, fn in tests:
        try:
            result = fn()
            if isinstance(result, dict) and result.get("ok") is False:
                print(f"  ✗ {name} — FAILED: {result.get('error', 'unknown')}")
            else:
                print(f"  ✓ {name} — OK")
        except Exception as exc:
            print(f"  ✗ {name} — FAILED: {exc}")


def _voice_command_handler(text: str) -> str:
    """Handle voice commands from the voice loop."""
    model_config = get_model_config()
    session_key = "voice-session"
    session = _sessions.get_or_create(
        session_key=session_key,
        channel="voice",
        user_id="operator",
        title="IMOS Voice",
    )
    try:
        history = _sessions.history(session, limit=10)
    except Exception:
        history = []
    try:
        result = _runtime.run(
            user_text=text,
            session_history=history,
            session_id=session.session_id,
            workspace=str(WORKSPACE),
            model_config=model_config,
            return_meta=True,
        )
        response = result.get("text", "") if isinstance(result, dict) else str(result)
    except Exception as exc:
        response = f"Error: {exc}"
    try:
        _sessions.append_message(session, "user", text)
        _sessions.append_message(session, "assistant", response)
    except Exception:
        pass
    _broadcast_sse("voice_command", {"command": text, "response": response})
    return response


def _get_greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"


def startup(open_browser: bool = True, port: int = 5000):
    print(IMOS_ASCII)
    print(f"[IMOS] Starting up — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[IMOS] Workspace: {WORKSPACE}")
    voice_settings = get_voice_settings()
    configure_tts(voice=voice_settings["voice"], rate=voice_settings["rate"])

    skills = _skill_registry.load_all()
    print(f"[IMOS] Loaded {len(skills)} skills: {', '.join(s.name for s in skills)}")

    _test_apis()

    try:
        from imos.voice_loop import get_tts
        tts = get_tts()
        time.sleep(0.5)
        if tts.available:
            print("[IMOS] Voice engine: OK (pyttsx3)")
        else:
            print("[IMOS] Voice engine: unavailable")
    except Exception as exc:
        print(f"[IMOS] Voice engine: FAILED — {exc}")

    try:
        if voice_settings.get("enabled", True):
            start_voice_loop(_voice_command_handler)
            print("[IMOS] Voice loop: started (listening for 'IMOS' or 'Hey IMOS')")
        else:
            print("[IMOS] Voice loop: disabled in settings")
    except Exception as exc:
        print(f"[IMOS] Voice loop: FAILED — {exc}")

    print(f"\n[IMOS] Starting Flask server on http://localhost:{port}")
    print(f"[IMOS] Dashboard: http://localhost:{port}\n")

    def _speak_startup():
        time.sleep(2)
        greeting = _get_greeting()
        speak(f"IMOS online. All systems operational. {greeting}, sir.")

    if voice_settings.get("enabled", True):
        threading.Thread(target=_speak_startup, daemon=True).start()

    if open_browser:
        def _open_browser():
            time.sleep(1.5)
            webbrowser.open(f"http://localhost:{port}")
        threading.Thread(target=_open_browser, daemon=True).start()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    no_browser = "--no-browser" in sys.argv
    port = int(load_config().get("dashboard", {}).get("port", 5000))
    startup(open_browser=not no_browser, port=port)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
