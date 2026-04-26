#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for AI Assistant
Verifies that the assistant is working correctly
"""

import json
import sys
import io
import os
import builtins
from contextlib import redirect_stdout
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ai_assistant import Config, AdvancedTools, UserDataStore

def test_config():
    """Test configuration loading."""
    print("\n=== Testing Configuration ===")
    print(f"GROQ_API_KEY set: {bool(Config.GROQ_API_KEY)}")
    print(f"Key length: {len(Config.GROQ_API_KEY) if Config.GROQ_API_KEY else 0}")
    print(f"USE_GROQ: {Config.USE_GROQ}")
    print(f"DATA_DIR: {Config.DATA_DIR}")
    return bool(Config.GROQ_API_KEY)

def test_data_store():
    """Test data storage."""
    print("\n=== Testing Data Store ===")
    store = UserDataStore()
    print(f"User profile loaded: {store.user_profile.name}")
    print(f"History entries: {len(store.history)}")
    print(f"Projects: {len(store.projects)}")
    store.save_profile()
    print("Save profile: OK")
    return True

def test_tools():
    """Test tool execution."""
    print("\n=== Testing Tools ===")

    # Test system info
    print("\n1. System Info:")
    result = AdvancedTools._get_system_info("os")
    print(f"   {result[:100]}...")

    # Test file operations
    print("\n2. File Operations:")
    result = AdvancedTools._list_directory(str(Path.home()))
    print(f"   Home dir: {result[:100]}...")

    # Test disk usage
    print("\n3. Disk Usage:")
    result = AdvancedTools._get_disk_usage("C:\\")
    print(f"   {result}")

    # Test search
    print("\n4. File Search:")
    result = AdvancedTools._search_files("*.txt", str(Path.home()))
    print(f"   {result[:200]}...")

    return True

def test_agent_tool_surface():
    """Test that the autonomous agent only sees primitive actions."""
    print("\n=== Testing Agent Tool Surface ===")
    defs = AdvancedTools.get_agent_definitions()
    names = {tool["function"]["name"] for tool in defs}
    print(f"   Agent tools: {sorted(names)}")

    assert "write_file" in names
    assert "run_shell_command" in names
    assert "observe_environment" in names
    assert "browser_open" in names
    assert "browser_snapshot" in names
    assert "synthesize_helper" in names
    assert "run_helper" in names
    assert "generate_workflow" in names
    assert "create_website" not in names
    assert "generate_content" not in names
    assert "deploy_website" not in names
    print("   Primitive action surface: OK")
    return True

def test_observe_environment():
    """Test environment snapshot tool."""
    print("\n=== Testing Environment Observation ===")
    result = AdvancedTools._observe_environment(".", 1)
    print(f"   Snapshot excerpt: {result[:200]}...")
    assert "cwd:" in result
    assert "tree:" in result
    print("   Environment observation: OK")
    return True

def test_agent_event_formatter():
    """Test that the CLI event formatter is callable."""
    print("\n=== Testing Agent Event Formatter ===")
    from ai_assistant import AdvancedAIPlatform

    formatter = AdvancedAIPlatform.__dict__["_emit_agent_event"]
    assert callable(formatter)
    print("   Agent event formatter: OK")
    return True

def test_agent_trace_formatting():
    """Test structured trace output for action and patch events."""
    print("\n=== Testing Agent Trace Formatting ===")
    from ai_assistant import AdvancedAIPlatform

    formatter = AdvancedAIPlatform.__dict__["_emit_agent_event"]
    obj = AdvancedAIPlatform.__new__(AdvancedAIPlatform)
    buf = io.StringIO()
    with redirect_stdout(buf):
        formatter(
            obj,
            "action",
            {"intent": "build_ui", "action": 'write_file({"path":"project_site/index.html"})'},
        )
        formatter(
            obj,
            "patch",
            {
                "intent": "build_ui",
                "target": "project_site/index.html",
                "changes": ["+ Added navigation structure", "+ Added hero section"],
            },
        )
    out = buf.getvalue()
    print(out.strip())
    assert "[ACTION]" in out
    assert "Intent: build_ui" in out
    assert "[PATCH]" in out
    assert "+ Added navigation structure" in out
    print("   Agent trace formatting: OK")
    return True

def test_streaming_api_exists():
    """Test that AIModel exposes streaming output."""
    print("\n=== Testing Streaming API ===")
    from ai_assistant import AIModel
    assert callable(getattr(AIModel, "stream_chat", None))
    assert callable(getattr(AIModel, "switch_provider", None))
    print("   Streaming API: OK")
    return True

def test_provider_command_aliases():
    """Test provider command aliases and dispatch."""
    print("\n=== Testing Provider Command Aliases ===")
    from ai_assistant import AdvancedAIPlatform

    class StubAI:
        def __init__(self):
            self.calls = []

        def get_provider_status(self):
            return [{"name": "groq", "ready": "yes", "configured": "yes", "model": "compound-beta", "selected": "yes"}]

        def switch_provider(self, name):
            self.calls.append(name)
            return True, f"Switched provider to {name}:demo-model"

    obj = AdvancedAIPlatform.__new__(AdvancedAIPlatform)
    obj.ai = StubAI()

    report = obj.process_command("/provider")
    switched = obj.process_command("/llm openai")
    print(report)
    print(switched)
    assert "Providers:" in report
    assert "openai" in switched
    assert obj.ai.calls == ["openai"]
    print("   Provider command aliases: OK")
    return True

def test_main_login_alias_dispatches_directly():
    """Test top-level `connect login` dispatches Clerk login directly."""
    print("\n=== Testing Login Alias Dispatch ===")
    import io
    from contextlib import redirect_stdout
    import ai_assistant

    original_argv = sys.argv
    original_platform = ai_assistant.AdvancedAIPlatform

    class StubPlatform:
        def __init__(self):
            self.called = []

        def run_clerk_login(self):
            self.called.append("login")
            return "Signed in successfully"

    stub = StubPlatform()
    ai_assistant.AdvancedAIPlatform = lambda: stub
    sys.argv = ["ai_assistant.py", "login"]
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            ai_assistant.main()
        out = buf.getvalue()
        assert "Signed in successfully" in out
        assert stub.called == ["login"]
        print("   Login alias dispatch: OK")
        return True
    finally:
        sys.argv = original_argv
        ai_assistant.AdvancedAIPlatform = original_platform

def test_launch_profile_defaults():
    """Test startup launch profile defaults."""
    print("\n=== Testing Launch Profile Defaults ===")
    from ai_assistant import AdvancedAIPlatform, UserProfile

    obj = AdvancedAIPlatform.__new__(AdvancedAIPlatform)

    class Store:
        def __init__(self):
            self.user_profile = UserProfile()

    obj.data_store = Store()
    profile = AdvancedAIPlatform._load_launch_profile(obj)
    assert profile["initialized"] is False
    assert profile["default_mode"] == "shell"
    assert profile["prompt_gateway_each_launch"] is True
    print("   Launch profile defaults: OK")
    return True

def test_choose_start_mode_updates_profile():
    """Test launch mode chooser persists selected mode."""
    print("\n=== Testing Launch Mode Selection ===")
    from ai_assistant import AdvancedAIPlatform

    obj = AdvancedAIPlatform.__new__(AdvancedAIPlatform)
    obj.launch_profile = {"default_mode": "shell", "prompt_gateway_each_launch": True}
    obj._save_launch_profile = lambda: None
    obj._ask_choice = lambda prompt, options, default="": "gateway"
    original_stdin = sys.stdin

    class FakeStdin:
        def isatty(self):
            return True

    sys.stdin = FakeStdin()
    try:
        mode = AdvancedAIPlatform.choose_start_mode(obj)
        assert mode == "gateway"
        assert obj.launch_profile["default_mode"] == "gateway"
        print("   Launch mode selection: OK")
        return True
    finally:
        sys.stdin = original_stdin

def test_choose_start_mode_respects_saved_default():
    """Test launch mode chooser uses saved default when prompting is disabled."""
    print("\n=== Testing Launch Mode Default ===")
    from ai_assistant import AdvancedAIPlatform

    obj = AdvancedAIPlatform.__new__(AdvancedAIPlatform)
    obj.launch_profile = {"default_mode": "dashboard", "prompt_gateway_each_launch": False}
    mode = AdvancedAIPlatform.choose_start_mode(obj)
    assert mode == "dashboard"
    print("   Launch mode default: OK")
    return True

def test_messaging_setup_writes_gateway_config():
    """Test CLI messaging setup writes Telegram settings to gateway config."""
    print("\n=== Testing Messaging Setup ===")
    import builtins
    from ai_assistant import AdvancedAIPlatform

    obj = AdvancedAIPlatform.__new__(AdvancedAIPlatform)
    temp_config = Path(__file__).parent / ".tmp_openclaw_test.json"
    if temp_config.exists():
        temp_config.unlink()
    answers = iter(["bot-token-123", "chat-456"])
    original_input = builtins.input
    original_stdin = sys.stdin

    class FakeStdin:
        def isatty(self):
            return True

    builtins.input = lambda prompt="": next(answers)
    sys.stdin = FakeStdin()
    obj._gateway_config_path = lambda: temp_config
    obj._muted = lambda text: text
    obj._section_header = lambda label: f"[{label}]"
    obj._ask_choice = lambda prompt, options, default="": "telegram"
    try:
        message = AdvancedAIPlatform.run_messaging_setup(obj)
        payload = json.loads(temp_config.read_text(encoding="utf-8"))
        assert payload["messaging"]["telegram_bot_token"] == "bot-token-123"
        assert payload["messaging"]["telegram_default_chat_id"] == "chat-456"
        assert "Saved Telegram" in message
        print("   Messaging setup: OK")
        return True
    finally:
        builtins.input = original_input
        sys.stdin = original_stdin
        if temp_config.exists():
            temp_config.unlink()

def test_has_messaging_config_detects_telegram():
    """Test messaging config detection sees a configured Telegram connector."""
    print("\n=== Testing Messaging Config Detection ===")
    from ai_assistant import AdvancedAIPlatform

    obj = AdvancedAIPlatform.__new__(AdvancedAIPlatform)
    obj._load_gateway_json = lambda: {
        "messaging": {
            "telegram_bot_token": "bot-token-123",
            "telegram_default_chat_id": "chat-456",
        }
    }
    obj._ensure_gateway_sections = AdvancedAIPlatform._ensure_gateway_sections.__get__(obj, AdvancedAIPlatform)
    assert AdvancedAIPlatform._has_messaging_config(obj) is True
    print("   Messaging config detection: OK")
    return True


def test_gateway_sections_include_deployment_defaults():
    """Test gateway config sections include deployment defaults."""
    print("\n=== Testing Gateway Deployment Defaults ===")
    from ai_assistant import AdvancedAIPlatform

    obj = AdvancedAIPlatform.__new__(AdvancedAIPlatform)
    data = AdvancedAIPlatform._ensure_gateway_sections(obj, {})
    assert data["gateway"]["deployment_mode"] == "local"
    assert data["gateway"]["dashboard_host"] == "127.0.0.1"
    print("   Gateway deployment defaults: OK")
    return True


def test_messaging_setup_writes_slack_config():
    """Test CLI messaging setup writes Slack webhook settings to gateway config."""
    print("\n=== Testing Slack Messaging Setup ===")
    from ai_assistant import AdvancedAIPlatform

    obj = AdvancedAIPlatform.__new__(AdvancedAIPlatform)
    temp_config = Path(__file__).parent / ".tmp_openclaw_slack_test.json"
    if temp_config.exists():
        temp_config.unlink()
    answers = iter(["alerts", "https://hooks.slack.com/services/example"])
    original_input = builtins.input
    original_stdin = sys.stdin

    class FakeStdin:
        def isatty(self):
            return True

    builtins.input = lambda prompt="": next(answers)
    sys.stdin = FakeStdin()
    obj._gateway_config_path = lambda: temp_config
    obj._muted = lambda text: text
    obj._section_header = lambda label: f"[{label}]"
    obj._ask_choice = lambda prompt, options, default="": "slack"
    try:
        message = AdvancedAIPlatform.run_messaging_setup(obj)
        payload = json.loads(temp_config.read_text(encoding="utf-8"))
        assert payload["messaging"]["slack_webhooks"]["alerts"] == "https://hooks.slack.com/services/example"
        assert "Saved Slack" in message
        print("   Slack messaging setup: OK")
        return True
    finally:
        builtins.input = original_input
        sys.stdin = original_stdin
        if temp_config.exists():
            temp_config.unlink()


def test_messaging_setup_writes_whatsapp_config():
    """Test CLI messaging setup writes WhatsApp settings to gateway config."""
    print("\n=== Testing WhatsApp Messaging Setup ===")
    from ai_assistant import AdvancedAIPlatform

    obj = AdvancedAIPlatform.__new__(AdvancedAIPlatform)
    temp_config = Path(__file__).parent / ".tmp_openclaw_whatsapp_test.json"
    if temp_config.exists():
        temp_config.unlink()
    answers = iter(["AC123", "token-456", "whatsapp:+14155238886"])
    original_input = builtins.input
    original_stdin = sys.stdin

    class FakeStdin:
        def isatty(self):
            return True

    builtins.input = lambda prompt="": next(answers)
    sys.stdin = FakeStdin()
    obj._gateway_config_path = lambda: temp_config
    obj._muted = lambda text: text
    obj._section_header = lambda label: f"[{label}]"
    obj._ask_choice = lambda prompt, options, default="": "whatsapp"
    try:
        message = AdvancedAIPlatform.run_messaging_setup(obj)
        payload = json.loads(temp_config.read_text(encoding="utf-8"))
        assert payload["messaging"]["whatsapp_account_sid"] == "AC123"
        assert payload["messaging"]["whatsapp_auth_token"] == "token-456"
        assert payload["messaging"]["whatsapp_from_number"] == "whatsapp:+14155238886"
        assert "Saved WhatsApp" in message
        print("   WhatsApp messaging setup: OK")
        return True
    finally:
        builtins.input = original_input
        sys.stdin = original_stdin
        if temp_config.exists():
            temp_config.unlink()

def test_startup_setup_prompts_for_messaging_when_missing():
    """Test startup flow prompts for messaging setup when no connector exists."""
    print("\n=== Testing Startup Messaging Prompt ===")
    from ai_assistant import AdvancedAIPlatform

    obj = AdvancedAIPlatform.__new__(AdvancedAIPlatform)
    obj.launch_profile = {"initialized": True}
    obj.ai = type("StubAI", (), {"provider": "openai"})()
    obj._has_messaging_config = lambda: False
    obj._prompt_optional_github_token = lambda: None
    calls = []
    obj._prompt_messaging_setup_if_missing = lambda: calls.append("prompted")
    original_stdin = sys.stdin

    class FakeStdin:
        def isatty(self):
            return True

    sys.stdin = FakeStdin()
    try:
        AdvancedAIPlatform._run_startup_setup(obj)
        assert calls == ["prompted"]
        print("   Startup messaging prompt: OK")
        return True
    finally:
        sys.stdin = original_stdin

def test_telegram_validation_reports_missing_config():
    """Test Telegram validation command reports missing setup."""
    print("\n=== Testing Telegram Validation ===")
    from ai_assistant import AdvancedAIPlatform

    obj = AdvancedAIPlatform.__new__(AdvancedAIPlatform)
    obj._load_gateway_json = lambda: {}
    obj._ensure_gateway_sections = AdvancedAIPlatform._ensure_gateway_sections.__get__(obj, AdvancedAIPlatform)
    message = AdvancedAIPlatform.run_telegram_validation(obj)
    assert "Run /messaging-setup first" in message
    print("   Telegram validation missing-config path: OK")
    return True

def test_provider_configuration_persists_env():
    """Test provider setup writes the project .env and refreshes config."""
    print("\n=== Testing Provider Configuration Persistence ===")
    import ai_assistant
    from ai_assistant import AIModel, Config
    from tools import auth_manager

    temp_env = Path(__file__).parent / ".tmp_provider_test.env"
    temp_env.write_text("", encoding="utf-8")

    original_input = builtins.input
    original_getpass = ai_assistant.getpass
    original_save_credential = auth_manager.save_credential
    original_ai_provider = os.environ.get("AI_PROVIDER")
    original_groq_key = os.environ.get("GROQ_API_KEY")

    builtins.input = lambda prompt="": ""
    ai_assistant.getpass = lambda prompt="": "gsk_test_provider_key"
    auth_manager.save_credential = lambda service, username, password: "ok"
    os.environ.pop("AI_PROVIDER", None)
    os.environ.pop("GROQ_API_KEY", None)
    Config.refresh_from_env()

    model = AIModel.__new__(AIModel)
    model.provider = ""
    model.model_name = ""
    model._provider_error = ""
    model._project_env_path = lambda: temp_env

    def fake_select(preferred=None, allow_fallback=True):
        model.provider = preferred or "groq"
        model.model_name = Config.GROQ_MODEL
        model._provider_error = ""

    model._select_provider = fake_select

    try:
        ok, message = model.configure_provider("groq", interactive=True)
        content = temp_env.read_text(encoding="utf-8")
        print(message)
        assert ok
        assert "AI_PROVIDER=groq" in content
        assert "GROQ_API_KEY=gsk_test_provider_key" in content
        assert Config.AI_PROVIDER == "groq"
        assert Config.GROQ_API_KEY == "gsk_test_provider_key"
        print("   Provider configuration persistence: OK")
        return True
    finally:
        builtins.input = original_input
        ai_assistant.getpass = original_getpass
        auth_manager.save_credential = original_save_credential
        if original_ai_provider is None:
            os.environ.pop("AI_PROVIDER", None)
        else:
            os.environ["AI_PROVIDER"] = original_ai_provider
        if original_groq_key is None:
            os.environ.pop("GROQ_API_KEY", None)
        else:
            os.environ["GROQ_API_KEY"] = original_groq_key
        Config.refresh_from_env()
        if temp_env.exists():
            temp_env.unlink()

def test_browser_snapshot_formatter():
    """Test browser observation formatting path."""
    print("\n=== Testing Browser Snapshot Formatter ===")
    from ai_assistant import AdvancedAIPlatform

    formatter = AdvancedAIPlatform.__dict__["_emit_agent_event"]
    obj = AdvancedAIPlatform.__new__(AdvancedAIPlatform)
    payload = {
        "snapshot": '{"url":"https://example.com","title":"Example","visible_text":"Hello world","console_errors":[],"page_errors":[],"network_failures":[],"screenshot_path":"C:/tmp/example.png"}'
    }
    formatter(obj, "observation", payload)
    print("   Browser snapshot formatter: OK")
    return True

def test_persistent_shell_session():
    """Test that shell cwd persists across commands in the same session."""
    print("\n=== Testing Persistent Shell Session ===")
    from ai_assistant import AdvancedTools

    workspace = Path(".ai_assistant_runtime") / "shell_session_test"
    workspace.mkdir(parents=True, exist_ok=True)
    session_id = "test-shell"
    first = AdvancedTools._run_shell(f'cd "{workspace}"', session_id=session_id)
    second = AdvancedTools._run_shell("pwd", session_id=session_id)
    print(first.splitlines()[0])
    print(second.splitlines()[0])
    assert f"cwd={workspace.resolve()}" in first
    assert str(workspace.resolve()).lower() in second.lower()
    print("   Persistent shell session: OK")
    return True

def test_shell_result_is_grounded():
    """Test shell output includes explicit execution metadata."""
    print("\n=== Testing Grounded Shell Result ===")
    from ai_assistant import AdvancedTools

    result = AdvancedTools._run_shell("echo hello", session_id="test-grounded")
    print(result)
    assert result.startswith("[SHELL_RESULT]")
    assert "exit_code=0" in result
    assert "stdout:" in result
    assert "hello" in result.lower()
    print("   Grounded shell result: OK")
    return True

def test_request_router_routes_tools():
    """Test that weather/search requests route to direct tools."""
    print("\n=== Testing Request Router ===")
    from ai_assistant import RequestRouter, AIModel

    router = RequestRouter()
    ai = AIModel.__new__(AIModel)
    ai.should_use_autonomous_agent = lambda user_input, history=None: False

    weather = router.route("what is the weather in Gujranwala", ai, [])
    search = router.route("search latest AI news", ai, [])
    print(f"   Weather route: {weather}")
    print(f"   Search route: {search}")
    assert weather.mode == "tool" and weather.tool_name == "weather_report"
    assert search.mode == "tool" and search.tool_name == "web_search"
    print("   Request router: OK")
    return True

def test_generated_code_fallback():
    """Test that heuristic fallback can synthesize execute_python tasks."""
    print("\n=== Testing Generated Code Fallback ===")
    from autonomous_agent import Planner, MemorySystem

    planner = Planner(ai_model=None, memory=MemorySystem())
    tasks = planner._heuristic_plan("scrape a random website and summarize it", ["observe_environment", "execute_python"])
    tool_names = [task["tool_name"] for task in tasks]
    print(f"   Tools selected: {tool_names}")
    assert "execute_python" in tool_names
    print("   Generated code fallback: OK")
    return True

def test_tool_registry_schema_repair():
    """Test strict validation plus deterministic arg repair."""
    print("\n=== Testing Tool Registry Schema Repair ===")
    from autonomous_agent import ToolRegistry

    class StubTools:
        @staticmethod
        def get_definitions():
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "run_shell_command",
                        "description": "Execute shell command",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command": {"type": "string"},
                                "cwd": {"type": "string"},
                            },
                            "required": ["command"],
                        },
                    },
                }
            ]

    registry = ToolRegistry(StubTools())
    ok, err = registry.validate("run_shell_command", {"cmd": "echo hi"})
    assert not ok
    assert "Missing required args" in err or "Unexpected args" in err

    repaired, notes = registry.repair_args("run_shell_command", {"cmd": "echo hi", "extra": "drop"})
    ok, err = registry.validate("run_shell_command", repaired)
    print(f"   Repair notes: {notes}")
    assert repaired == {"command": "echo hi"}
    assert ok, err
    print("   Tool registry schema repair: OK")
    return True

def test_nextjs_repo_planning():
    """Test that Next.js goals produce repo-oriented shell tasks."""
    print("\n=== Testing Next.js Repo Planning ===")
    from autonomous_agent import Planner, MemorySystem, WorldStateStore

    planner = Planner(ai_model=None, memory=MemorySystem(), world_state=WorldStateStore())
    tasks = planner._heuristic_plan(
        "Build a real Next.js app and commit it to a repo",
        ["observe_environment", "run_shell_command"],
    )
    commands = [task.get("tool_args", {}).get("command", "") for task in tasks if task.get("tool_name") == "run_shell_command"]
    print(f"   Commands: {commands}")
    assert any("create-next-app" in cmd for cmd in commands)
    assert any(cmd.startswith("cd project_site") or cmd == "cd project_site" for cmd in commands)
    assert any("git init" in cmd for cmd in commands)
    print("   Next.js repo planning: OK")
    return True

def test_executor_repairs_invalid_tool_args():
    """Test that executor repairs invalid tool args before failing the task."""
    print("\n=== Testing Executor Validation Repair ===")
    from autonomous_agent import (
        AgentConfig,
        Executor,
        ToolRegistry,
        Verifier,
        MemorySystem,
        SafetyManager,
        PolicyEngine,
        AuditLogger,
        WorldStateStore,
        RunState,
        Plan,
        Task,
        RunStatus,
    )

    class StubAI:
        def chat(self, messages, tools=None):
            return {"choices": [{"message": {"content": "{\"tool_name\": \"run_shell_command\", \"tool_args\": {\"command\": \"echo repaired\"}, \"reason\": \"fixed schema\"}"}}]}

    class StubTools:
        def __init__(self):
            self.calls = []

        @staticmethod
        def get_definitions():
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "run_shell_command",
                        "description": "Execute shell command",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command": {"type": "string"},
                                "cwd": {"type": "string"},
                            },
                            "required": ["command"],
                        },
                    },
                }
            ]

        def execute(self, tool_name, args):
            self.calls.append((tool_name, args))
            return f"ran {args['command']}"

    runtime_dir = Path(".ai_assistant_runtime")
    runtime_dir.mkdir(exist_ok=True)
    AgentConfig.AUDIT_LOG_FILE = runtime_dir / "test_audit.log.jsonl"
    AgentConfig.POLICY_FILE = runtime_dir / "test_policy.json"
    AgentConfig.WORLD_STATE_FILE = runtime_dir / "test_world_state.json"
    AgentConfig.STM_FILE = runtime_dir / "test_stm.json"
    AgentConfig.LTM_FILE = runtime_dir / "test_ltm.json"
    AgentConfig.FAILURES_FILE = runtime_dir / "test_failures.json"
    AgentConfig.RUNS_INDEX_FILE = runtime_dir / "test_runs_index.json"

    tools = StubTools()
    registry = ToolRegistry(tools)
    verifier = Verifier(ai_model=None)
    executor = Executor(
        ai_model=StubAI(),
        tools=tools,
        registry=registry,
        verifier=verifier,
        memory=MemorySystem(),
        safety=SafetyManager(confirm_callback=lambda task: True),
        policy=PolicyEngine(),
        audit=AuditLogger("test-secret"),
        world_state=WorldStateStore(),
    )

    run = RunState(
        run_id="repair_test",
        goal="test schema repair",
        status=RunStatus.RUNNING,
        plan=Plan(
            id="repair_test_r0",
            goal="test schema repair",
            tasks=[
                Task(
                    id="repair_test_r0_t0",
                    name="Run command",
                    description="Execute a shell command",
                    tool_name="run_shell_command",
                    tool_args={"cmd": "echo repaired"},
                    verification="output_contains:repaired",
                )
            ],
            revision=0,
        ),
    )

    updated_run, failed_task = executor.run_plan(run)
    task = updated_run.plan.tasks[0]
    assert failed_task is None
    assert task.status.value == "completed"
    assert task.tool_args == {"command": "echo repaired"}
    assert tools.calls == [("run_shell_command", {"command": "echo repaired"})]
    print("   Executor validation repair: OK")
    return True

def test_workflow_roundtrip():
    """Test saving and running a workflow."""
    print("\n=== Testing Workflow Roundtrip ===")
    workflow_name = "test_loop_workflow"
    save_result = AdvancedTools._save_workflow(
        workflow_name,
        [
            {
                "tool_name": "write_file",
                "tool_args": {
                    "path": "workflow_output_${iteration}.txt",
                    "content": "hello ${iteration}",
                },
            }
        ],
        "Writes a file with the loop index",
    )
    print(f"   Save: {save_result}")
    run_result = AdvancedTools._run_workflow(workflow_name, loop_count=2, inputs={})
    print(f"   Run: {run_result[:200]}...")
    assert "completed" in run_result
    assert Path("workflow_output_0.txt").exists()
    assert Path("workflow_output_1.txt").exists()
    print("   Workflow roundtrip: OK")
    return True

def test_generated_workflow_tools():
    """Test AI-generated workflow creation and mutation."""
    print("\n=== Testing Generated Workflow Tools ===")

    class FakeAI:
        def __init__(self):
            self.calls = 0

        def chat(self, messages, tools=None):
            self.calls += 1
            if self.calls == 1:
                content = """{
                  "description": "Generated workflow",
                  "steps": [
                    {"tool_name": "observe_environment", "tool_args": {"path": ".", "depth": 1}},
                    {"tool_name": "write_file", "tool_args": {"path": "generated_from_ai.txt", "content": "hi"}}
                  ]
                }"""
            else:
                content = """{
                  "description": "Rewritten workflow",
                  "steps": [
                    {"tool_name": "observe_environment", "tool_args": {"path": ".", "depth": 1}},
                    {"tool_name": "write_file", "tool_args": {"path": "rewritten_from_ai.txt", "content": "fixed"}}
                  ]
                }"""
            return {"choices": [{"message": {"content": content}}]}

    ai = FakeAI()
    name = "generated_ai_workflow"
    result = AdvancedTools._generate_workflow(name, "build a reusable workflow", "test", ai)
    print(f"   Generate: {result}")
    assert "Saved workflow" in result

    mutate = AdvancedTools._mutate_workflow(name, "auto_rewrite", reason="step failed", goal="build a reusable workflow", last_result="error", ai_model=ai)
    print(f"   Mutate: {mutate}")
    assert "Mutated workflow" in mutate
    print("   Generated workflow tools: OK")
    return True

def test_planner_helper_fallback():
    """Test that the planner can choose helper synthesis for unknown goals."""
    print("\n=== Testing Planner Helper Fallback ===")
    from autonomous_agent import Planner, MemorySystem, WorldStateStore

    planner = Planner(ai_model=None, memory=MemorySystem(), world_state=WorldStateStore())
    tasks = planner._heuristic_plan(
        "invent a new capability for log normalization",
        ["observe_environment", "synthesize_helper", "run_helper"],
    )
    tools = [task["tool_name"] for task in tasks]
    print(f"   Tools selected: {tools}")
    assert "synthesize_helper" in tools
    assert "run_helper" in tools
    print("   Planner helper fallback: OK")
    return True

def test_website_goal_generates_coherent_site():
    """Test that website goals generate linked pages and a shared design system."""
    print("\n=== Testing Website Goal Intent Planning ===")
    from autonomous_agent import Planner, MemorySystem, WorldStateStore

    planner = Planner(ai_model=None, memory=MemorySystem(), world_state=WorldStateStore())
    tasks = planner._heuristic_plan(
        "Build a SaaS landing page for AI Labs that looks like a real startup website",
        ["observe_environment", "create_directory", "write_file", "browser_open", "browser_snapshot"],
    )
    paths = [task.get("tool_args", {}).get("path", "") for task in tasks if task.get("tool_name") == "write_file"]
    index_task = next(task for task in tasks if task.get("tool_args", {}).get("path") == "project_site/index.html")
    index_html = index_task["tool_args"]["content"]
    print(f"   Files planned: {paths}")
    assert "project_site/index.html" in paths
    assert "project_site/about.html" in paths
    assert "project_site/contact.html" in paths
    assert "project_site/styles.css" in paths
    assert "<nav" in index_html
    assert "about.html" in index_html
    assert "contact.html" in index_html
    assert "<h1>" in index_html
    print("   Website goal intent planning: OK")
    return True

def test_goal_progress_evaluator():
    """Test goal progress evaluation and persistence."""
    print("\n=== Testing Goal Progress Evaluator ===")
    from autonomous_agent import GoalProgressEvaluator, WorldStateStore, RunState, Plan, Task, RunStatus, TaskStatus

    world = WorldStateStore()
    task = Task(
        id="t1",
        name="Observe environment",
        description="snapshot",
        tool_name="observe_environment",
        status=TaskStatus.COMPLETED,
        result="snapshot ok",
    )
    run = RunState(
        run_id="run_eval",
        goal="build a website",
        status=RunStatus.RUNNING,
        plan=Plan(id="plan1", goal="build a website", tasks=[task]),
    )
    evaluator = GoalProgressEvaluator(ai_model=None, world_state=world)
    result = evaluator.evaluate(run)
    print(f"   Result: {result}")
    assert "progress_score" in result
    assert world.state["goal_progress"]
    print("   Goal progress evaluator: OK")
    return True

def test_website_quality_fallback_is_strict():
    """Test that website evaluation does not mark placeholder work as success."""
    print("\n=== Testing Website Quality Fallback ===")
    from autonomous_agent import GoalProgressEvaluator, WorldStateStore, RunState, Plan, Task, RunStatus, TaskStatus

    world = WorldStateStore()
    tasks = [
        Task(
            id="t1",
            name="Write placeholder landing page",
            description="placeholder",
            tool_name="write_file",
            status=TaskStatus.COMPLETED,
            tool_args={
                "path": "project_site/index.html",
                "content": "<html><head><title>Landing Page</title></head><body><h1>Landing Page</h1></body></html>",
            },
        )
    ]
    run = RunState(
        run_id="run_site_eval",
        goal="build a website for AI Labs",
        status=RunStatus.RUNNING,
        plan=Plan(id="plan_site", goal="build a website for AI Labs", tasks=tasks),
    )
    evaluator = GoalProgressEvaluator(ai_model=None, world_state=world)
    result = evaluator.evaluate(run)
    print(f"   Result: {result}")
    assert result["goal_achieved"] is False
    assert result["strategy_bad"] is True
    assert result["progress_score"] < 100
    print("   Website quality fallback: OK")
    return True

def test_world_state_store():
    """Test persistent world-state recording."""
    print("\n=== Testing World State Store ===")
    from autonomous_agent import WorldStateStore

    store = WorldStateStore()
    store.record_action("test goal", "run_1", "write_file", {"path": "x.txt"}, "Written: x.txt", "completed")
    store.update_goal_progress("test goal", {"progress_score": 42, "goal_achieved": False, "on_track": True})
    snapshot = store.snapshot()
    print(f"   Snapshot keys: {list(snapshot.keys())}")
    assert snapshot["last_action"]["tool_name"] == "write_file"
    assert snapshot["goal_progress"]
    print("   World state store: OK")
    return True

def test_helper_synthesis():
    """Test bounded helper synthesis and execution."""
    print("\n=== Testing Helper Synthesis ===")
    helper_name = "test_helper_synthesis"
    synth = AdvancedTools._synthesize_helper(helper_name, "echo the payload back", "run(payload) -> payload")
    print(f"   Synthesize: {synth}")
    assert "Synthesized helper" in synth
    run = AdvancedTools._run_helper(helper_name, {"hello": "world"})
    print(f"   Run: {run[:200]}...")
    assert "hello" in run or "payload" in run
    print("   Helper synthesis: OK")
    return True

def test_api_connection():
    """Test Groq API connection."""
    print("\n=== Testing API Connection ===")
    if not Config.GROQ_API_KEY:
        print("   SKIP: No API key configured")
        return False

    try:
        from ai_assistant import AIModel
        ai = AIModel()

        messages = [{"role": "user", "content": "Say hello in one word"}]
        response = ai.chat(messages)

        if "error" in response:
            print(f"   ERROR: {response['error']}")
            return False

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"   Response: {content[:50]}...")
        print("   API Connection: OK")
        return True
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("   AI ASSISTANT - TEST SUITE")
    print("=" * 60)

    results = {
        "Configuration": test_config(),
        "Data Store": test_data_store(),
        "Tools": test_tools(),
        "Agent Tool Surface": test_agent_tool_surface(),
        "Environment Observation": test_observe_environment(),
        "Agent Event Formatter": test_agent_event_formatter(),
        "Agent Trace Formatting": test_agent_trace_formatting(),
        "Streaming API": test_streaming_api_exists(),
        "Provider Command Aliases": test_provider_command_aliases(),
        "Provider Configuration Persistence": test_provider_configuration_persists_env(),
        "Browser Snapshot Formatter": test_browser_snapshot_formatter(),
        "Persistent Shell Session": test_persistent_shell_session(),
        "Grounded Shell Result": test_shell_result_is_grounded(),
        "Request Router": test_request_router_routes_tools(),
        "Generated Code Fallback": test_generated_code_fallback(),
        "Tool Registry Schema Repair": test_tool_registry_schema_repair(),
        "Next.js Repo Planning": test_nextjs_repo_planning(),
        "Executor Validation Repair": test_executor_repairs_invalid_tool_args(),
        "Workflow Roundtrip": test_workflow_roundtrip(),
        "Generated Workflow Tools": test_generated_workflow_tools(),
        "Planner Helper Fallback": test_planner_helper_fallback(),
        "Website Goal Intent Planning": test_website_goal_generates_coherent_site(),
        "Goal Progress Evaluator": test_goal_progress_evaluator(),
        "Website Quality Fallback": test_website_quality_fallback_is_strict(),
        "World State Store": test_world_state_store(),
        "Helper Synthesis": test_helper_synthesis(),
        "API Connection": test_api_connection(),
    }

    print("\n" + "=" * 60)
    print("   TEST RESULTS")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"   {test_name}: {status}")

    all_passed = all(results.values())

    print("\n" + "=" * 60)
    if all_passed:
        print("   ALL TESTS PASSED!")
        print("\n   Run 'python ai_assistant.py' to start chatting.")
    else:
        print("   SOME TESTS FAILED!")
        print("\n   Check the errors above and fix configuration.")
        if not Config.GROQ_API_KEY:
            print("\n   To fix API key:")
            print("   1. Get key from: https://console.groq.com/keys")
            print("   2. Edit .env file and add: GROQ_API_KEY=your_key")
    print("=" * 60)

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
