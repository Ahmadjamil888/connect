import asyncio
import json
import shutil
import time
import uuid
from pathlib import Path

from gateway_runtime.auth import ClerkAuthManager
from gateway_runtime.config import load_gateway_config, resolve_allowed_tool_names
from gateway_runtime.dashboard import render_dashboard_html
from gateway_runtime.node_client import render_node_client_html
from gateway_runtime.runtime import AgentRuntime
from gateway_runtime.server import GatewayController
from gateway_runtime.workspace import WorkspaceLayout
from gateway_runtime.memory_store import MemoryStore


class FakeAI:
    def __init__(self):
        self.provider = "fake"
        self.model_name = "fake-model"
        self._provider_error = ""
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        return {"choices": [{"message": {"content": "done", "tool_calls": []}}]}

    def stream_chat(self, messages, on_chunk=None):
        content = "done"
        if on_chunk:
            on_chunk(content)
        return content

    def should_use_autonomous_agent(self, user_input, history=None):
        return False

    def get_provider_status(self):
        return [{"name": "fake", "configured": "yes", "ready": "yes", "model": "fake-model", "selected": "yes"}]


def _scratch_dir(name: str) -> Path:
    root = Path.cwd() / ".ai_assistant_runtime" / "test_gateway_runtime" / f"{name}_{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_workspace_bootstrap():
    root = _scratch_dir("workspace_bootstrap") / "workspace"
    layout = WorkspaceLayout(root)
    layout.bootstrap()
    for name in ["AGENTS.md", "SOUL.md", "TOOLS.md", "HEARTBEAT.md"]:
        assert (root / name).exists()
    assert layout.skills_dir.exists()
    assert layout.sessions_dir.exists()
    assert layout.memory_dir.exists()
    shutil.rmtree(root.parent, ignore_errors=True)


def test_tool_permission_resolution():
    scratch = _scratch_dir("permission_resolution")
    config_path = scratch / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "tools": {"allow": ["group:fs"], "deny": ["write_file"]},
                "agents": {"list": [{"name": "default", "tools": {"profile": "coding", "deny": ["run_shell_command"]}}]},
            }
        ),
        encoding="utf-8",
    )
    config = load_gateway_config(config_path)
    known = {"read_file", "write_file", "run_shell_command", "memory_search", "session_status"}
    groups = {"fs": {"read_file", "write_file"}, "runtime": {"run_shell_command"}, "memory": {"memory_search"}, "sessions": {"session_status"}}
    allowed = resolve_allowed_tool_names(
        profile="coding",
        config_allow=config.tools_allow,
        config_deny=config.tools_deny,
        policy_allow=[],
        policy_deny=["run_shell_command"],
        known_names=known,
        group_map=groups,
    )
    assert "read_file" in allowed
    assert "write_file" not in allowed
    assert "run_shell_command" not in allowed
    shutil.rmtree(scratch, ignore_errors=True)


def test_runtime_sessions_and_turn():
    scratch = _scratch_dir("runtime_turn")
    workspace = scratch / "workspace"
    config_path = scratch / "openclaw.json"
    config_path.write_text(json.dumps({"workspace": {"root": str(workspace)}}), encoding="utf-8")
    runtime = AgentRuntime(load_gateway_config(config_path), ai_model=FakeAI())
    session_id = runtime.ensure_default_session()
    result = runtime.run_turn(session_id, "hello")
    assert result["ok"] is True
    assert result["content"] == "done"
    history = runtime.sessions.history(session_id)
    assert history[-1]["role"] == "assistant"
    shutil.rmtree(scratch, ignore_errors=True)


def test_gateway_controller_dispatch():
    scratch = _scratch_dir("gateway_dispatch")
    workspace = scratch / "workspace"
    config_path = scratch / "openclaw.json"
    config_path.write_text(json.dumps({"workspace": {"root": str(workspace)}}), encoding="utf-8")
    runtime = AgentRuntime(load_gateway_config(config_path), ai_model=FakeAI())
    session_id = runtime.ensure_default_session()
    controller = GatewayController(runtime)
    result = asyncio.run(controller.dispatch("agent.ask", {"session_id": session_id, "content": "hello"}))
    assert result["ok"] is True
    sessions = asyncio.run(controller.dispatch("sessions.list", {}))
    assert sessions
    status = asyncio.run(controller.dispatch("sessions.status", {"session_id": session_id}))
    assert status["id"] == session_id
    shutil.rmtree(scratch, ignore_errors=True)


def test_runtime_dashboard_tool_route_uses_real_tool_execution():
    scratch = _scratch_dir("runtime_tool_route")
    workspace = scratch / "workspace"
    config_path = scratch / "openclaw.json"
    config_path.write_text(json.dumps({"workspace": {"root": str(workspace)}}), encoding="utf-8")
    runtime = AgentRuntime(load_gateway_config(config_path), ai_model=FakeAI())
    session_id = runtime.ensure_default_session()
    original_execute_tool = runtime.execute_tool
    runtime.execute_tool = lambda sid, tool_name, args: type("Result", (), {"ok": True, "output": f"{tool_name}:{args['query']}"})()
    result = runtime.run_turn(session_id, "search for python")
    assert result["ok"] is True
    assert result["mode"] == "tool"
    assert "python" in result["content"].lower()
    runtime.execute_tool = original_execute_tool
    shutil.rmtree(scratch, ignore_errors=True)


def test_dashboard_html_contains_core_sections():
    html = render_dashboard_html()
    assert "CONNECT Dashboard" in html
    assert "/api/status" in html
    assert "Live Services" in html
    assert "Real session threads" in html
    assert "/api/ask" in html


def test_node_client_html_contains_pairing_flows():
    html = render_node_client_html()
    assert "CONNECT Node Client" in html
    assert "/api/node/pair" in html
    assert "/api/node/register" in html


def test_canvas_node_and_message_tools():
    scratch = _scratch_dir("canvas_node_message")
    workspace = scratch / "workspace"
    config_path = scratch / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "workspace": {"root": str(workspace)},
                "tools": {"allow": ["group:ui", "group:nodes", "group:messaging", "group:sessions"]},
            }
        ),
        encoding="utf-8",
    )
    runtime = AgentRuntime(load_gateway_config(config_path), ai_model=FakeAI())
    session_id = runtime.ensure_default_session()
    card = runtime.execute_tool(session_id, "canvas_present", {"content": "Ship report", "title": "Ops"})
    assert card.ok is True
    snap = runtime.execute_tool(session_id, "canvas_snapshot", {})
    assert snap.ok is True and snap.output["cards"]
    pair = runtime.execute_tool(session_id, "node_pair", {"label": "phone"})
    assert pair.ok is True
    node = runtime.nodes.register_node(pair.output["pair_code"], pair.output["pair_secret"], "Pixel", "android")
    listed = runtime.execute_tool(session_id, "nodes_list", {})
    assert listed.ok is True and listed.output
    runtime.nodes.update_location(node["node_id"], {"lat": 1.0, "lng": 2.0})
    location = runtime.execute_tool(session_id, "node_location", {"node_id": node["node_id"]})
    assert location.ok is True and location.output["lat"] == 1.0
    delivered = runtime.execute_tool(session_id, "message_send", {"target": f"session:{session_id}", "content": "hello session"})
    assert delivered.ok is True
    assert runtime.sessions.history(session_id)[-1]["content"] == "hello session"
    shutil.rmtree(scratch, ignore_errors=True)


def test_discord_config_lookup():
    scratch = _scratch_dir("discord_lookup")
    config_path = scratch / "openclaw.json"
    config_path.write_text(
        json.dumps({"messaging": {"discord_webhooks": {"ops": "https://discord.com/api/webhooks/example"}}}),
        encoding="utf-8",
    )
    config = load_gateway_config(config_path)
    runtime = AgentRuntime(config, ai_model=FakeAI())
    value = runtime.config_lookup("messaging.discord_webhooks")
    assert value == ["ops"]
    shutil.rmtree(scratch, ignore_errors=True)


def test_save_integration_refreshes_runtime_state():
    scratch = _scratch_dir("integration_refresh")
    config_path = scratch / "openclaw.json"
    config_path.write_text(json.dumps({"messaging": {}}), encoding="utf-8")
    runtime = AgentRuntime(load_gateway_config(config_path), ai_model=FakeAI())
    saved = runtime.save_integration("telegram", {"bot_token": "abc", "default_chat_id": "123"})
    assert saved["ok"] is True
    snapshot = runtime.integration_snapshot()
    assert snapshot["telegram"]["connected"] is True
    assert snapshot["telegram"]["default_chat_id"] == "123"
    assert runtime.telegram is not None
    runtime.telegram.stop()
    shutil.rmtree(scratch, ignore_errors=True)


def test_memory_store_persists_entries_in_sqlite():
    scratch = _scratch_dir("memory_sqlite")
    store = MemoryStore(scratch / "memory")
    store.remember("assistant", "session-1", "remember this line", {"topic": "sql"})
    recent = store.get_recent("session-1", 5)
    matches = store.search("remember this line", 5)
    assert recent and recent[-1]["content"] == "remember this line"
    assert matches and matches[0]["content"] == "remember this line"
    assert (scratch / "memory" / "memory.db").exists()
    shutil.rmtree(scratch, ignore_errors=True)


def test_slack_config_lookup_and_session_delivery():
    scratch = _scratch_dir("slack_lookup")
    config_path = scratch / "openclaw.json"
    config_path.write_text(
        json.dumps({"messaging": {"slack_webhooks": {"alerts": "https://hooks.slack.com/services/example"}}}),
        encoding="utf-8",
    )
    config = load_gateway_config(config_path)
    runtime = AgentRuntime(config, ai_model=FakeAI())
    value = runtime.config_lookup("messaging.slack_webhooks")
    assert value == ["alerts"]
    session_id = runtime.ensure_default_session()
    delivered = runtime.execute_tool(session_id, "message_send", {"target": f"session:{session_id}", "content": "hello session"})
    assert delivered.ok is True
    shutil.rmtree(scratch, ignore_errors=True)


def test_orchestrator_runs_prompt_jobs():
    scratch = _scratch_dir("orchestrator_jobs")
    workspace = scratch / "workspace"
    config_path = scratch / "openclaw.json"
    config_path.write_text(json.dumps({"workspace": {"root": str(workspace)}}), encoding="utf-8")
    runtime = AgentRuntime(load_gateway_config(config_path), ai_model=FakeAI())
    session_id = runtime.ensure_default_session()
    job = runtime.orchestrator.submit("run_prompt", {"session_id": session_id, "text": "create a file"})
    for _ in range(40):
        jobs = runtime.orchestrator.jobs()
        current = next(item for item in jobs if item["job_id"] == job["job_id"])
        if current["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert current["status"] == "completed"
    shutil.rmtree(scratch, ignore_errors=True)


def test_cron_jobs_execute():
    scratch = _scratch_dir("cron_jobs")
    workspace = scratch / "workspace"
    config_path = scratch / "openclaw.json"
    config_path.write_text(json.dumps({"workspace": {"root": str(workspace)}, "tools": {"allow": ["group:automation", "group:sessions"]}}), encoding="utf-8")
    runtime = AgentRuntime(load_gateway_config(config_path), ai_model=FakeAI())
    session_id = runtime.ensure_default_session()
    created = runtime.execute_tool(session_id, "cron_add", {"name": "heartbeat", "schedule": "@every 1s", "prompt": "create a file"})
    assert created.ok is True
    completed = False
    for _ in range(50):
        jobs = runtime.orchestrator.jobs()
        if any(job["status"] == "completed" for job in jobs):
            completed = True
            break
        time.sleep(0.1)
    assert completed is True
    cron_jobs = runtime.execute_tool(session_id, "cron_list", {})
    assert cron_jobs.ok is True and cron_jobs.output
    shutil.rmtree(scratch, ignore_errors=True)


def test_node_manifest_available():
    scratch = _scratch_dir("node_manifest")
    workspace = scratch / "workspace"
    config_path = scratch / "openclaw.json"
    config_path.write_text(json.dumps({"workspace": {"root": str(workspace)}}), encoding="utf-8")
    runtime = AgentRuntime(load_gateway_config(config_path), ai_model=FakeAI())
    manifest = runtime.node_manifest()
    assert manifest["pairing"]["create"].startswith("POST")
    assert "screen" in manifest["updates"]
    shutil.rmtree(scratch, ignore_errors=True)


def test_workflow_run_and_webhook_trigger():
    scratch = _scratch_dir("workflow_run")
    workspace = scratch / "workspace"
    config_path = scratch / "openclaw.json"
    config_path.write_text(
        json.dumps({"workspace": {"root": str(workspace)}, "tools": {"allow": ["group:automation", "group:messaging", "group:sessions"]}}),
        encoding="utf-8",
    )
    runtime = AgentRuntime(load_gateway_config(config_path), ai_model=FakeAI())
    session_id = runtime.ensure_default_session()
    workflow_path = workspace / "workflows" / "notify.yaml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(
        """
name: notify
triggers:
  webhook: inbound_alert
steps:
  - name: local_notice
    type: message
    target: "session:{session_id}"
    content: "Alert: {payload[text]}"
""".strip(),
        encoding="utf-8",
    )
    listed = runtime.workflows.list_workflows()
    assert listed and listed[0]["name"] == "notify"
    result = runtime.workflows.run_named("notify", {"text": "disk high"}, session_id=session_id)
    assert result["ok"] is True
    assert runtime.sessions.history(session_id)[-1]["content"] == "Alert: disk high"
    triggered = runtime.workflows.trigger_webhook("inbound_alert", {"text": "cpu high"}, session_id=session_id)
    assert triggered["ok"] is True
    assert runtime.sessions.history(session_id)[-1]["content"] == "Alert: cpu high"
    shutil.rmtree(scratch, ignore_errors=True)


def test_slack_bot_and_whatsapp_handlers():
    scratch = _scratch_dir("connector_handlers")
    workspace = scratch / "workspace"
    config_path = scratch / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "workspace": {"root": str(workspace)},
                "messaging": {
                    "slack_bot_token": "xoxb-test",
                    "slack_signing_secret": "secret",
                    "whatsapp_account_sid": "AC123",
                    "whatsapp_auth_token": "token",
                    "whatsapp_from_number": "whatsapp:+14155238886",
                },
            }
        ),
        encoding="utf-8",
    )
    runtime = AgentRuntime(load_gateway_config(config_path), ai_model=FakeAI())
    challenge = runtime.handle_slack_event({"type": "url_verification", "challenge": "abc"})
    assert challenge["challenge"] == "abc"
    runtime.handle_slack_event({"event": {"type": "message", "channel": "C123", "user": "U123", "text": "hello slack"}})
    runtime.handle_whatsapp_inbound({"From": "whatsapp:+123456789", "Body": "hello wa"})
    names = [row["name"] for row in runtime.sessions.list()]
    assert any(name.startswith("slack_") for name in names)
    assert any(name.startswith("whatsapp_") for name in names)
    shutil.rmtree(scratch, ignore_errors=True)


def test_config_loads_dashboard_host_and_deployment_mode():
    scratch = _scratch_dir("config_dashboard")
    config_path = scratch / "openclaw.json"
    config_path.write_text(
        json.dumps({"gateway": {"host": "0.0.0.0", "dashboard_host": "127.0.0.1", "deployment_mode": "cloud"}}),
        encoding="utf-8",
    )
    config = load_gateway_config(config_path)
    assert config.host == "0.0.0.0"
    assert config.dashboard_host == "127.0.0.1"
    assert config.deployment_mode == "cloud"
    shutil.rmtree(scratch, ignore_errors=True)


def test_clerk_auth_manager_local_session_validation():
    scratch = _scratch_dir("clerk_auth")
    manager = ClerkAuthManager(scratch, "pk_test_bmVhdC1zcGFuaWVsLTExLmNsZXJrLmFjY291bnRzLmRldiQ", True, "hook-secret")
    manager.verify_clerk_token = lambda token: {"sub": "user_123", "sid": "sess_abc"}  # type: ignore[method-assign]
    state = manager.complete_login("jwt-token", "user@example.com")
    assert state.local_session_id == "sess_abc"
    assert manager.validate_cookie("connect_session=sess_abc") is True
    assert manager.validate_bearer("Bearer hook-secret") is True
    assert manager.request_authenticated({"Cookie": "connect_session=sess_abc"}) is True
    manager.clear_state()
    shutil.rmtree(scratch, ignore_errors=True)


def test_clerk_auth_manager_builds_vercel_cli_signin_url():
    scratch = _scratch_dir("clerk_auth_url")
    manager = ClerkAuthManager(scratch, "pk_test_bmVhdC1zcGFuaWVsLTExLmNsZXJrLmFjY291bnRzLmRldiQ", True)
    url = manager.build_cli_signin_url("http://127.0.0.1:18891/callback")
    assert url.startswith("https://connect-ai-pi.vercel.app/auth/cli?")
    assert "callback=http%3A%2F%2F127.0.0.1%3A18891%2Fcallback" in url
    assert "origin=cli" in url
    shutil.rmtree(scratch, ignore_errors=True)
