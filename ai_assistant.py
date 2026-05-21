import json
import os
import subprocess
import sys
import textwrap
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import requests
from dotenv import load_dotenv

from core.audit import AuditLogger
from core.browser import Browser
from core.context import ContextManager
from core.dashboard import Dashboard
from core.memory import Memory
from core.router import RoutingRules
from core import model_manager
from core.operator_runtime import PLANNER_TOOLS_DOC, list_connected_services, run_operator_tool, think
from core.policy import Policy
from core.providers import get_response
from core.services_catalog import list_all_services, list_provider_types, save_custom_service
from core.tasks import TaskTracker

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
IMOS_HOME = Path.home() / ".imos"
INITIALIZED_PATH = IMOS_HOME / "initialized.json"
EXPORTS_DIR = IMOS_HOME / "exports"
conversation_history: list[dict] = []
start_time = datetime.now()
mem = Memory()
pol = Policy()
tracker = TaskTracker()
browser = Browser()
audit = AuditLogger(IMOS_HOME / "logs")
routing = RoutingRules(IMOS_HOME / "routing.json")

PROVIDER_MODEL_DEFAULTS = {
    "anthropic": "claude-opus-4-5",
    "openai": "gpt-4o",
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-1.5-pro",
    "openrouter": "openai/gpt-4o",
    "ollama": "llama3.2",
    "huggingface": "meta-llama/Llama-3.3-70B-Instruct",
}

PROVIDER_MODEL_ENVS = {
    "anthropic": "ANTHROPIC_MODEL",
    "openai": "OPENAI_MODEL",
    "groq": "GROQ_MODEL",
    "gemini": "GOOGLE_GEMINI_MODEL",
    "openrouter": "OPENROUTER_MODEL",
    "ollama": "OLLAMA_MODEL",
    "huggingface": "HUGGINGFACE_MODEL",
}

current_provider = "groq"
current_model = "unknown"


def _activate_provider_row(row: dict) -> tuple[str, str]:
    global current_provider, current_model
    provider_type = str(row.get("type") or row.get("provider", "groq")).strip().lower()
    model_name = str(row.get("model", "") or "").strip() or PROVIDER_MODEL_DEFAULTS.get(provider_type, "unknown")
    current_provider = provider_type
    current_model = model_name
    os.environ["AI_PROVIDER"] = provider_type
    env_key = PROVIDER_MODEL_ENVS.get(provider_type)
    if env_key:
        os.environ[env_key] = model_name
    if row.get("api_key"):
        key_env = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "groq": "GROQ_API_KEY",
            "gemini": "GOOGLE_GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "huggingface": "HUGGINGFACE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "alibaba": "ALIBABA_API_KEY",
            "nvidia": "NVIDIA_API_KEY",
            "together": "TOGETHER_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "cohere": "COHERE_API_KEY",
        }.get(provider_type)
        if key_env:
            os.environ[key_env] = str(row["api_key"])
    return current_provider, current_model


def _init_active_provider() -> None:
    row = model_manager.get_default()
    if row.get("no_provider_configured"):
        provider = os.getenv("AI_PROVIDER", "groq").strip().lower() or "groq"
        model = os.getenv(PROVIDER_MODEL_ENVS.get(provider, ""), "") or PROVIDER_MODEL_DEFAULTS.get(provider, "unknown")
        _activate_provider_row({"type": provider, "model": model})
        return
    _activate_provider_row(row)


_init_active_provider()
ctx = ContextManager(str(uuid4()))
ctx.switch_provider(current_provider, current_model)
dashboard = Dashboard(
    memory=mem,
    policy=pol,
    tracker=tracker,
    ctx_getter=lambda: ctx,
    provider_getter=lambda: (current_provider, current_model),
    start_time=start_time,
    audit=audit,
    routing=routing,
)
dashboard.start(port=7070)

PLANNER_SYSTEM_PROMPT = """You are IMOS Planner. Take a SHORT vague user request and expand it into a complete JSON execution plan. Never ask the user for more info. Make smart decisions yourself.

IMOS is an intelligent machine operating system: one persistent runtime unifying models, IDEs, terminals, browser automation, apps, and local execution. Solve fragmented context across ChatGPT, Claude, Cursor, and browsers with visible coordination, shared memory, routing, permissions, and auditability.
Plan like an operator system:
- Preserve continuity across the session.
- Prefer real execution when the user wants something built, launched, opened, scaffolded, written, or automated.
- Make plans explicit, inspectable, and delivery-oriented.
- Coordinate browser prompts, code prompts, files, terminal commands, workspace inspection, HTTP actions, and browser automation as one system.

For SaaS / web app / startup product requests (e.g. "I want a saas app"):
1. scaffold_saas with description and project_name (slug, no spaces)
2. transfer_context to lovable and cursor with targets
3. open_app cursor
4. lovable with a detailed UI/product prompt derived from the user request
5. cursor_build with an implementation prompt for the same product

""" + PLANNER_TOOLS_DOC + """
- claude_code: {prompt, directory?} (legacy)
- cursor_build: {prompt, directory?}
- lovable: {prompt}
- transfer_context: {target: lovable|cursor|claude|chatgpt|codex|generic}
- scaffold_saas: {description, project_name}

Prefer ai_agent with agent auto for coding tasks (picks Cursor, Codex, Claude, or configured model).
Use browser for web UI; desktop for OS-level click, type, drag; rewrite_file and delete_file for file ops.

Output only valid JSON in this exact shape:
{
  "goal": "one sentence summary",
  "reasoning": "why this approach",
  "steps": [
    {
      "step": 1,
      "description": "what this does",
      "tool": "<one of the tools above>",
      "params": {}
    }
  ]
}
"""

BUILD_KEYWORDS = (
    "saas",
    "web app",
    "webapp",
    "startup",
    "mvp",
    "landing page",
    "build me",
    "create app",
    "scaffold",
    "deploy",
    "lovable",
    "cursor",
    "click",
    "type",
    "drag",
    "open app",
    "open browser",
    "delete",
    "rewrite",
    "automate",
    "codex",
    "claude",
)

UNIFIED_OPERATOR_TOOLS = frozenset(
    {"browser", "desktop", "ai_agent", "rewrite_file", "delete_file", "open_service"}
)

CHAT_SYSTEM_PROMPT = """You are IMOS, the intelligent machine operating system — one persistent runtime for models, IDEs, terminals, browsers, apps, and local execution.
Reply directly and briefly. Continue naturally from shared session context. Do not output JSON unless the user asks for JSON.
"""

INTENT_SYSTEM_PROMPT = """You are the IMOS runtime intent router.
Default to "execute" whenever the user wants something to happen on their PC, browser, files, or apps.
Choose "execute" for: build, make, create, open, run, click, type, drag, delete, write, deploy, automate, control, websites, apps, fixes.
Choose "chat" ONLY for pure greetings, thanks, or conceptual questions with no action implied.

Output only valid JSON in exactly this shape:
{
  "mode": "chat|execute",
  "reason": "short reason",
  "reply": "direct assistant reply if mode is chat, otherwise empty string"
}
"""

UI = None
VERBOSE_THINK = False

HELP_TEXT = """Commands:
  /help                         show this help
  /dashboard                    open runtime dashboard in browser
  /status                       show runtime status (coordination layer)
  /runtime                      full snapshot: memory, routing, policy, audit, execution
  /memory                       shared memory log
  /audit [n]                    audit trail (default last 15)
  /routing                      model routing rules by task type
  /route <task> <provider>      set routing rule (e.g. /route code groq)
  /policy                       print current tool policy
  /policy-set <tool> <value>    set allow|ask|deny
  /tasks                        show recent tasks
  /task <id>                    show one task
  /switch <provider>            transfer context to a new provider
  /session                      current session stats
  /sessions                     list all saved sessions
  /resume <id>                  restore and continue a saved session
  /export                       export current session to markdown
  /transfer <target>            export full context for cursor, claude, lovable, codex, etc.
  /transfer all                 export context packs for all major targets
  /services                     list all connected services
  /service add <name> [detail]  add a custom service to the catalog
  /model list                   list saved model providers
  /model types                  list provider types you can add
  /model add <type> <model> [key] [base_url]
                                add any model (e.g. /model add openai gpt-4o sk-...)
  /model use <id>               switch active model by provider id
  /model default <id>         set default provider
  /model remove <id>          remove a saved provider
  /exit                         quit IMOS
"""


def _clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _imos_line(message: str) -> None:
    if UI:
        UI.status(message)
    else:
        print(f"imos  {message}")
    try:
        dashboard.emit_log(message)
    except Exception:
        pass


def _audit(kind: str, message: str, metadata: dict | None = None) -> None:
    entry = audit.append(kind, message, metadata or {})
    mem.append_log(f"{kind}: {message[:120]}")
    try:
        dashboard.emit_audit(entry)
        dashboard.emit_runtime()
    except Exception:
        pass


def _apply_task_routing(prompt: str) -> dict:
    global current_provider, current_model
    task_type, routed = routing.resolve_provider(prompt, current_provider)
    switched = False
    if routed:
        for row in model_manager.load_providers():
            if str(row.get("type", "")).lower() == routed or str(row.get("id", "")).lower() == routed:
                _activate_provider_row(row)
                ctx.switch_provider(current_provider, current_model)
                switched = True
                break
    info = {
        "task_type": task_type,
        "routed_provider": routed,
        "active_provider": current_provider,
        "active_model": current_model,
        "switched": switched,
    }
    mem.save("last_routing", info)
    _audit("routing", f"{task_type} → {routed or current_provider}", info)
    try:
        dashboard.emit_routing({"rules": routing.list_rules(), "last": info})
    except Exception:
        pass
    return info


def _dashboard_chat(role: str, content: str) -> None:
    try:
        dashboard.emit_chat(role, content)
    except Exception:
        pass


def _dashboard_think(think_data: dict) -> None:
    try:
        dashboard.emit_think(think_data)
    except Exception:
        pass


def _is_build_request(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in BUILD_KEYWORDS)


def _should_execute(text: str, think_data: dict | None = None) -> bool:
    if _is_build_request(text):
        return True
    if think_data and str(think_data.get("mode", "")).lower() == "execute":
        return True
    lowered = text.lower()
    execute_signals = (
        "make ",
        "build ",
        "create ",
        "open ",
        "run ",
        "launch",
        "click",
        "type ",
        "drag",
        "delete",
        "remove",
        "write ",
        "read ",
        "deploy",
        "scaffold",
        "automate",
        "control",
        "website",
        " web app",
        "saas",
        "fix ",
        "install",
        "download",
        "upload",
        "screenshot",
        "browser",
        "cursor",
        "lovable",
        "professional",
    )
    return any(signal in lowered for signal in execute_signals)


def _transfer_context_command(parts: list[str]) -> None:
    from tools.context_transfer import TRANSFER_TARGETS, build_transfer_from_imos_context, copy_to_clipboard

    if len(parts) < 2:
        sample = "|".join(TRANSFER_TARGETS[:6])
        _imos_line(f"usage: /transfer <{sample}...>  or  /transfer all")
        return
    targets = list(TRANSFER_TARGETS) if parts[1].lower() == "all" else [parts[1].lower()]
    for target in targets:
        try:
            package = build_transfer_from_imos_context(ctx, target=target, exports_dir=EXPORTS_DIR)
            path = package["transfer_path"]
            copied = copy_to_clipboard(package["transfer_text"])
            _audit("transfer", f"context → {target}", {"path": path})
            if UI:
                UI.tool_start(f"transfer → {target}", path)
                UI.tool_result(f"Saved {path}" + (" · copied to clipboard" if copied else ""), ok=True)
            else:
                _imos_line(f"context → {target}: {path}" + (" (clipboard)" if copied else ""))
            if target == "cursor":
                from tools.ide_tools import open_cursor

                open_cursor(str(PROJECT_ROOT))
            elif target == "lovable":
                webbrowser.open("https://lovable.dev")
            try:
                dashboard.emit_log(f"context transferred to {target}: {path}")
            except Exception:
                pass
        except Exception as exc:
            _imos_line(f"transfer {target} failed: {exc}")


def _truncate(text: str, limit: int) -> str:
    text = str(text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _box_top() -> str:
    return "┌" + "─" * 68 + "┐"


def _box_mid() -> str:
    return "├" + "─" * 68 + "┤"


def _box_bottom() -> str:
    return "└" + "─" * 68 + "┘"


def _box_line(text: str = "") -> str:
    return f"│{text[:68].ljust(68)}│"


def _show_box(title: str, rows: list[str]) -> None:
    print(_box_top())
    print(_box_line(f" {title}"))
    print(_box_mid())
    for row in rows:
        print(_box_line(f" {row}"))
    print(_box_bottom())


def _wrap_lines(text: str, width: int) -> list[str]:
    wrapped = textwrap.wrap(str(text), width=width, replace_whitespace=False, drop_whitespace=False)
    return wrapped or [""]


def _provider_name() -> str:
    return f"{current_provider} / {current_model}"


def _planner_prompt_with_memory() -> str:
    recent = mem.get_log(10)
    if not recent:
        return PLANNER_SYSTEM_PROMPT + "\n\nRecent activity:\n- none"
    lines = "\n".join(f"- {entry}" for entry in recent)
    return f"{PLANNER_SYSTEM_PROMPT}\n\nRecent activity:\n{lines}"


def _strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _extract_json_object(text: str) -> str:
    cleaned = _strip_markdown_fences(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("model response did not contain valid JSON")
    return cleaned[start : end + 1]


def _parse_json_response(text: str) -> dict:
    return json.loads(_extract_json_object(text))


def _resolve_directory(directory: str | None) -> str:
    target = PROJECT_ROOT if not directory else (PROJECT_ROOT / directory).resolve()
    return str(target)


def _format_uptime() -> str:
    delta = datetime.now() - start_time
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _short_tool_description(tool: str, params: dict) -> str:
    if tool == "run_shell":
        return params.get("command", "")
    if tool in {"write_file", "append_file", "read_file", "make_dir"}:
        return params.get("path", "")
    if tool == "open_url":
        return params.get("url", "")
    if tool == "lovable":
        return _truncate(params.get("prompt", ""), 100).replace("\n", " ")
    if tool == "cursor_build":
        return _truncate(params.get("prompt", ""), 100).replace("\n", " ")
    if tool == "transfer_context":
        return params.get("target", "")
    if tool == "scaffold_saas":
        return params.get("project_name", params.get("description", ""))
    if tool == "desktop":
        return str(params.get("action", ""))
    if tool == "ai_agent":
        return _truncate(params.get("prompt", ""), 100).replace("\n", " ")
    if tool == "delete_file":
        return params.get("path", "")
    if tool == "rewrite_file":
        return params.get("path", "")
    if tool == "open_app":
        return params.get("app", "")
    if tool == "claude_code":
        return _truncate(params.get("prompt", ""), 100).replace("\n", " ")
    if tool == "http_request":
        return f"{params.get('method', 'GET')} {params.get('url', '')}"
    if tool == "browser":
        return f"{params.get('action', '')} {params.get('selector', '') or params.get('url', '')}"
    if tool == "list_dir":
        return params.get("path", ".")
    return ""


def _policy_gate(tool: str, params: dict) -> str | None:
    decision = pol.check(tool)
    _audit("policy_check", f"{tool} → {decision}", {"tool": tool, "decision": decision})
    if decision == "deny":
        _imos_line(f"{tool} is blocked by policy")
        return "denied"
    if decision == "ask":
        desc = _short_tool_description(tool, params)
        if UI:
            UI.tool_start("permission", f"{tool}")
            answer = input(f"  Allow {tool} ({desc})? [y/N] ").strip().lower()
        else:
            answer = input(f"  Allow {tool}: {desc}? [y/N] ").strip().lower()
        if answer != "y":
            _audit("policy_denied", f"user declined {tool}", {"tool": tool})
            return "skipped by user"
        _audit("policy_allowed", f"user approved {tool}", {"tool": tool})
    return None


def _record_tool_result(step: dict, result: str) -> None:
    conversation_history.append({"role": "assistant", "content": {"type": "tool_result", "tool": step.get("tool"), "result": result}})
    ctx.add_message("tool_result", result, current_provider, current_model)


def _run_shell_command(command: str, directory: str) -> dict:
    print(f"  $ {command}")
    process = subprocess.Popen(
        command,
        shell=True,
        cwd=directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    assert process.stdout is not None
    assert process.stderr is not None
    for line in process.stdout:
        stdout_lines.append(line)
        print(f"   {line.rstrip()}")
    for line in process.stderr:
        stderr_lines.append(line)
        print(f"   {line.rstrip()}")
    exit_code = process.wait()
    return {"exit_code": exit_code, "stdout": "".join(stdout_lines), "stderr": "".join(stderr_lines)}


def _provider_messages() -> list[dict]:
    return ctx.export_for_provider(current_provider)


def chat(user_message: str) -> str:
    return get_response(messages=_provider_messages(), system=CHAT_SYSTEM_PROMPT)


def route_intent(user_message: str) -> dict:
    raw_response = get_response(messages=_provider_messages(), system=INTENT_SYSTEM_PROMPT)
    decision = _parse_json_response(raw_response)
    mode = str(decision.get("mode", "chat")).strip().lower()
    if mode not in {"chat", "execute"}:
        mode = "chat"
    decision["mode"] = mode
    decision.setdefault("reason", "")
    decision.setdefault("reply", "")
    return decision


def plan(user_message: str, think_data: dict | None = None) -> dict:
    system = _planner_prompt_with_memory()
    if think_data:
        steps = think_data.get("reasoning_steps") or []
        agents = think_data.get("agents") or ["auto"]
        services = think_data.get("services") or []
        system += (
            f"\n\nPrior operator analysis:\n{think_data.get('analysis', '')}\n"
            f"Reasoning steps: {json.dumps(steps)}\n"
            f"Preferred agents: {json.dumps(agents)}\n"
            f"Connected services: {json.dumps(services)}"
        )
    raw_response = get_response(messages=_provider_messages(), system=system)
    plan_data = _parse_json_response(raw_response)
    if not isinstance(plan_data, dict):
        raise ValueError("planner returned non-object JSON")
    plan_data.setdefault("goal", "")
    plan_data.setdefault("reasoning", "")
    plan_data.setdefault("steps", [])
    if not isinstance(plan_data["steps"], list):
        raise ValueError("planner steps must be a list")
    return plan_data


def _open_terminal() -> None:
    if sys.platform.startswith("win"):
        subprocess.Popen(["cmd", "/c", "start", "", "powershell"], cwd=str(PROJECT_ROOT))
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "Terminal", str(PROJECT_ROOT)])
        return
    for candidate in (["x-terminal-emulator"], ["gnome-terminal"], ["konsole"], ["xterm"]):
        try:
            subprocess.Popen(candidate, cwd=str(PROJECT_ROOT))
            return
        except FileNotFoundError:
            continue
    raise RuntimeError("no supported terminal application was found")


def _execute_legacy_tool(step: dict) -> dict:
    tool = step.get("tool")
    params = step.get("params") or {}

    if tool == "run_shell":
        command = params["command"]
        directory = _resolve_directory(params.get("directory", "."))
        result = _run_shell_command(command, directory)
        result.update({"status": "ok" if result["exit_code"] == 0 else "failed", "tool": tool, "command": command, "directory": directory, "result": f"Ran shell command in {directory}: {command}"})
        return result

    if tool == "open_url":
        url = params["url"]
        instruction = params["instruction"]
        print(f"   Opening: {url}")
        print("   Paste this prompt:")
        for line in _wrap_lines(instruction, 66):
            print(f"   {line}")
        webbrowser.open(url)
        return {"status": "ok", "tool": tool, "result": f"Opened URL: {url}"}

    if tool == "claude_code":
        prompt = params["prompt"]
        directory = _resolve_directory(params.get("directory", "."))
        completed = subprocess.run(["claude", "--print", prompt], cwd=directory, check=False)
        return {"status": "ok" if completed.returncode == 0 else "failed", "tool": tool, "result": f"Ran claude code in {directory}", "exit_code": completed.returncode}

    if tool == "write_file":
        destination = (PROJECT_ROOT / params["path"]).resolve()
        lines = str(params["content"]).splitlines() or [""]
        print(f"   Writing: {params['path']}  ({len(lines)} lines)")
        os.makedirs(destination.parent, exist_ok=True)
        with open(destination, "w", encoding="utf-8") as file_handle:
            file_handle.write(params["content"])
        return {"status": "ok", "tool": tool, "result": f"Wrote file: {destination}"}

    if tool == "append_file":
        destination = (PROJECT_ROOT / params["path"]).resolve()
        os.makedirs(destination.parent, exist_ok=True)
        with open(destination, "a", encoding="utf-8") as file_handle:
            file_handle.write(params["content"])
        return {"status": "ok", "tool": tool, "result": f"Appended file: {destination}"}

    if tool == "read_file":
        source = (PROJECT_ROOT / params["path"]).resolve()
        with open(source, "r", encoding="utf-8") as file_handle:
            content = file_handle.read()
        return {"status": "ok", "tool": tool, "result": f"Read file: {source}\n{_truncate(content, 600)}"}

    if tool == "list_dir":
        target = (PROJECT_ROOT / params.get("path", ".")).resolve()
        entries = sorted(os.listdir(target))
        return {"status": "ok", "tool": tool, "result": f"Listed directory: {target}\n{_truncate(chr(10).join(entries), 600)}"}

    if tool == "make_dir":
        destination = (PROJECT_ROOT / params["path"]).resolve()
        os.makedirs(destination, exist_ok=True)
        return {"status": "ok", "tool": tool, "result": f"Created directory: {destination}"}

    if tool == "http_request":
        method = str(params.get("method", "GET")).upper()
        url = params["url"]
        headers = params.get("headers") or {}
        body = params.get("body", "")
        save_to = params.get("save_to")
        request_kwargs = {"headers": headers, "timeout": 180}
        if method != "GET" and body != "":
            request_kwargs["data"] = body
        response = requests.request(method, url, **request_kwargs)
        response.raise_for_status()
        content = response.text
        if save_to:
            destination = (PROJECT_ROOT / save_to).resolve()
            os.makedirs(destination.parent, exist_ok=True)
            with open(destination, "w", encoding="utf-8") as file_handle:
                file_handle.write(content)
            return {"status": "ok", "tool": tool, "result": f"HTTP {method} {url} -> saved to {destination}"}
        return {"status": "ok", "tool": tool, "result": f"HTTP {method} {url}\n{_truncate(content, 600)}"}

    if tool == "browser":
        action = params["action"]
        target = params.get("url") or params.get("selector", "")
        print(f"   Browser: {action} on {target}")
        if action == "navigate":
            browser.navigate(params["url"])
            return {"status": "ok", "tool": tool, "result": f"Browser navigated to {params['url']}"}
        if action == "click":
            browser.click(params["selector"])
            return {"status": "ok", "tool": tool, "result": f"Browser clicked {params['selector']}"}
        if action == "type":
            browser.type_text(params["selector"], params["text"])
            return {"status": "ok", "tool": tool, "result": f"Browser typed into {params['selector']}"}
        if action == "get_text":
            text = browser.get_text(params["selector"])
            return {"status": "ok", "tool": tool, "result": f"Browser text from {params['selector']}:\n{_truncate(text, 600)}"}
        if action == "screenshot":
            path = params.get("path", "screenshot.png")
            browser.screenshot(path)
            return {"status": "ok", "tool": tool, "result": f"Browser screenshot saved to {Path(path).resolve()}"}
        raise ValueError(f"unsupported browser action: {action}")

    if tool == "open_app":
        app = str(params["app"]).lower()
        if app == "cursor":
            from tools.ide_tools import open_cursor

            result = open_cursor(str(PROJECT_ROOT))
            if result.get("status") != "success":
                subprocess.Popen(["cursor", "."], cwd=str(PROJECT_ROOT))
            return {"status": "ok", "tool": tool, "result": "Opened Cursor for IMOS workspace"}
        if app == "vscode":
            from tools.ide_tools import open_vscode

            result = open_vscode(str(PROJECT_ROOT))
            if result.get("status") != "success":
                subprocess.Popen(["code", "."], cwd=str(PROJECT_ROOT))
            return {"status": "ok", "tool": tool, "result": "Opened VS Code"}
        if app == "terminal":
            _open_terminal()
            return {"status": "ok", "tool": tool, "result": "Opened terminal"}
        raise ValueError(f"unsupported app: {app}")

    if tool == "lovable":
        from tools.web_platform_tools import lovable_build_project

        prompt = str(params.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("lovable requires a prompt")
        print(f"   Lovable: {_truncate(prompt, 80)}")
        outcome = lovable_build_project(prompt)
        status = "ok" if outcome.get("status") == "success" else "failed"
        urls = outcome.get("urls") or []
        summary = f"Lovable session: {outcome.get('status', 'unknown')}"
        if urls:
            summary += f" urls={', '.join(urls[:3])}"
        return {"status": status, "tool": tool, "result": summary, "detail": outcome}

    if tool == "cursor_build":
        from tools.agent_bridges import chat_with_claude_code
        from tools.ide_tools import open_cursor

        prompt = str(params.get("prompt", "")).strip()
        directory = _resolve_directory(params.get("directory", "."))
        open_cursor(directory)
        outcome = chat_with_claude_code(prompt, directory)
        status = "ok" if outcome.get("success") else "failed"
        output = _truncate(outcome.get("output") or outcome.get("error", ""), 600)
        return {"status": status, "tool": tool, "result": f"Cursor/Claude build in {directory}: {output}"}

    if tool == "transfer_context":
        from tools.context_transfer import TRANSFER_TARGETS, build_transfer_from_imos_context, copy_to_clipboard

        target = str(params.get("target", "generic")).strip().lower() or "generic"
        if target not in TRANSFER_TARGETS:
            target = "generic"
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        package = build_transfer_from_imos_context(ctx, target=target, exports_dir=EXPORTS_DIR)
        transfer_path = Path(package["transfer_path"])
        copied = copy_to_clipboard(package.get("transfer_text", ""))
        from tools.context_transfer import _target_instructions

        instruction = _target_instructions(target)
        if target == "lovable":
            webbrowser.open("https://lovable.dev")
        elif target == "cursor":
            from tools.ide_tools import open_cursor

            open_cursor(str(PROJECT_ROOT))
        clip_note = " Copied to clipboard." if copied else ""
        return {
            "status": "ok",
            "tool": tool,
            "result": f"Context transferred to {target}: {transfer_path}.{clip_note} {instruction}",
        }

    if tool == "scaffold_saas":
        from skills.scaffold_nextjs.handler import run as scaffold_run

        description = str(params.get("description", "SaaS product")).strip()
        raw_name = str(params.get("project_name", "imos-saas")).strip().lower()
        project_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in raw_name).strip("-_") or "imos-saas"
        print(f"   Scaffolding SaaS: {project_name}")
        outcome = scaffold_run(
            {
                "description": description,
                "project_name": project_name,
                "db_type": "sqlite",
                "deploy_target": "vercel",
                "include_auth": True,
                "include_payments": False,
            },
            workspace=str(PROJECT_ROOT),
            model_config={"provider": current_provider, "model": current_model},
        )
        status = "ok" if outcome.get("ok") else "failed"
        summary = outcome.get("summary") or outcome.get("error") or str(outcome)
        return {"status": status, "tool": tool, "result": f"SaaS scaffold {project_name}: {_truncate(summary, 500)}"}

    raise ValueError(f"unsupported tool: {tool}")


def execute_tool(step: dict) -> dict:
    tool = step.get("tool")
    params = step.get("params") or {}
    _audit("tool_start", str(tool), {"params": params, "step": step.get("step")})
    blocked = _policy_gate(tool, params)
    if blocked:
        result = {"status": blocked, "tool": tool, "step": step.get("step"), "result": blocked}
        _audit("tool_end", f"{tool} {blocked}", {"status": blocked})
        return result
    if tool in UNIFIED_OPERATOR_TOOLS:
        outcome = run_operator_tool(
            tool,
            params,
            project_root=PROJECT_ROOT,
            legacy_browser=browser,
            current_provider=current_provider,
            current_model=current_model,
            execute_legacy=_execute_legacy_tool,
        )
    else:
        outcome = _execute_legacy_tool(step)
    _audit("tool_end", f"{tool} → {outcome.get('status', 'ok')}", {"status": outcome.get("status")})
    return outcome


def _suggest_shell_fix(command: str, stderr_text: str) -> dict | None:
    prompt = f"This command failed: {command}\nError: {stderr_text}\nSuggest a fix as a new run_shell step JSON only."
    raw = get_response(messages=ctx.export_for_provider(current_provider) + [{"role": "user", "content": prompt}], system="Return only one JSON step object.")
    parsed = _parse_json_response(raw)
    if parsed.get("tool") == "run_shell":
        return parsed
    return None


def _show_status() -> None:
    snap = dashboard.runtime_snapshot()
    tasks = snap["execution"]
    stats = snap["session"]
    rows = [
        "Coordination layer (visible on dashboard :7070)",
        f"Provider  : {snap['provider']} / {snap['model']}",
        f"Memory    : {snap['memory']['log_count']} log entries",
        f"Routing   : {len(snap['routing']['rules'])} rules  (last: {mem.get('last_routing', {}).get('task_type', '-')})",
        f"Policy    : {len(snap['policy'])} tools gated",
        f"Audit     : {snap['audit']['count']} events",
        f"Execution : {tasks['done']} done, {tasks['running']} running, {tasks['failed']} failed",
        f"Session   : {stats['session_id'][:8]}  {stats['message_count']} msgs  ~{stats['token_estimate']} tokens",
        f"Uptime    : {snap['uptime']}",
    ]
    _show_box("IMOS Runtime Status", rows)


def _show_runtime() -> None:
    snap = dashboard.runtime_snapshot()
    _show_box("IMOS Runtime Snapshot", json.dumps(snap, indent=2, default=str).splitlines()[:28])


def _show_memory() -> None:
    rows = mem.get_log(20) or ["(empty)"]
    _show_box("Shared Memory", rows)


def _show_audit(limit: int = 15) -> None:
    rows = []
    for entry in audit.tail(limit):
        rows.append(f"{entry.get('ts', '')[:19]}  [{entry.get('kind', '')}]  {entry.get('message', '')[:70]}")
    _show_box("Audit Trail", rows or ["(empty)"])


def _show_routing() -> None:
    rules = routing.list_rules()
    rows = [f"{task:<18} → {prov or '(active model)'}" for task, prov in rules.items()]
    last = mem.get("last_routing") or {}
    if last:
        rows.append("")
        rows.append(f"Last inference: {last.get('task_type')} → {last.get('routed_provider')} (active: {last.get('active_provider')})")
    _show_box("Routing Rules", rows)


def _show_tasks() -> None:
    tasks = tracker.list_recent(5)
    if not tasks:
        _imos_line("no tasks recorded")
        return
    rows = [f"{task['id']}  {task['status']:<7} {task['steps_done']}/{task['steps_total']}  {_truncate(task['goal'], 36)}" for task in tasks]
    _show_box("Recent Tasks", rows)


def _show_task(task_id: str) -> None:
    task = tracker.get(task_id)
    if not task:
        _imos_line(f"error: task not found: {task_id}")
        return
    _show_box(f"Task {task_id}", json.dumps(task, indent=2).splitlines()[:20])


def _show_session_card(goal: str, steps_total: int, provider: str, task_id: str) -> None:
    rows = [
        f"Goal      : {_truncate(goal, 55)}",
        f"Steps     : {steps_total}",
        f"Provider  : {provider}",
        f"Task ID   : {task_id[:8]}",
    ]
    _show_box("Session", rows)


def _show_current_session() -> None:
    stats = ctx.get_stats()
    summary = stats["summary"] or "not yet generated"
    rows = [
        f"ID         : {stats['session_id'][:8]}",
        f"Messages   : {stats['message_count']}",
        f"Tokens     : ~{stats['token_estimate']}",
        f"Providers  : {'  '.join(stats['providers_used']) or current_provider}",
        f"Duration   : {stats['duration_minutes']} min",
    ]
    rows.extend([f"Summary    : {line}" if idx == 0 else f"            {line}" for idx, line in enumerate(_wrap_lines(summary, 52))])
    _show_box("Current Session", rows)


def _show_sessions() -> None:
    sessions = ContextManager.list_all()[:10]
    if not sessions:
        _imos_line("no saved sessions")
        return
    rows = []
    for session in sessions:
        rows.append(f"{session['session_id'][:8]}  {session['created_at']}  {session['message_count']} msgs")
        rows.append(f"{_truncate(session['summary_preview'] or 'no summary', 66)}")
        rows.append("")
    _show_box("Saved Sessions", rows)
    _imos_line("use /resume <session_id> to continue a session.")


def _resolve_session_id(prefix: str) -> str | None:
    for session in ContextManager.list_all():
        if session["session_id"] == prefix or session["session_id"].startswith(prefix):
            return session["session_id"]
    return None


def _resume_session(prefix: str) -> None:
    global ctx
    resolved = _resolve_session_id(prefix)
    if not resolved:
        raise ValueError(f"session not found: {prefix}")
    restored = ContextManager(resolved)
    stats = restored.get_stats()
    summary = stats["summary"] or "not yet generated"
    rows = [
        f"Session   : {stats['session_id'][:8]}",
        f"Started   : {stats['created_at']}",
        f"Messages  : {stats['message_count']}",
        f"Providers : {'  '.join(stats['providers_used'])}",
    ]
    rows.extend([f"Summary   : {line}" if idx == 0 else f"            {line}" for idx, line in enumerate(_wrap_lines(summary, 52))])
    _show_box("Resuming Session", rows)
    ctx = restored
    ctx.switch_provider(current_provider, current_model)
    _imos_line(f"session restored. continuing from {stats['message_count']} messages.")


def _export_session() -> None:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORTS_DIR / f"{ctx.session_id}.md"
    ctx.export_markdown(path)
    _imos_line(f"session exported to {path}")


def _set_current_provider(provider: str, model: str | None = None) -> tuple[str, str]:
    provider = provider.strip().lower()
    if provider not in model_manager.PROVIDER_TYPES and provider not in PROVIDER_MODEL_DEFAULTS:
        raise ValueError(f"unknown provider: {provider}. Run /model types")
    model = model or PROVIDER_MODEL_DEFAULTS.get(provider, "custom-model")
    row = model_manager.add_provider(
        {
            "id": f"{provider}-runtime",
            "name": model_manager.PROVIDER_TYPES.get(provider, {}).get("name", provider),
            "type": provider,
            "model": model,
            "api_key": os.getenv(
                {
                    "anthropic": "ANTHROPIC_API_KEY",
                    "openai": "OPENAI_API_KEY",
                    "groq": "GROQ_API_KEY",
                }.get(provider, ""),
                "",
            ),
            "is_default": True,
        }
    )
    return _activate_provider_row(row)


def _handle_model_command(parts: list[str]) -> None:
    if len(parts) < 2:
        _imos_line("usage: /model list|types|add|use|default|remove")
        return
    action = parts[1].lower()
    if action == "list":
        rows = model_manager.load_providers()
        if not rows:
            _imos_line("no models saved. use /model add <type> <model_name> [api_key]")
            return
        for row in rows:
            mark = "*" if row.get("is_default") else " "
            _imos_line(f"{mark} {row['id']:<16} {row['type']:<12} {row.get('model', '')}")
        return
    if action == "types":
        for item in list_provider_types():
            _imos_line(f"  {item['type']:<14} {item['name']}")
        _imos_line("use /model add <type> <any-model-id> [api_key] [base_url]")
        return
    if action == "add":
        if len(parts) < 4:
            _imos_line("usage: /model add <type> <model> [api_key] [base_url]")
            return
        provider_type = parts[2].lower()
        model_name = parts[3]
        api_key = parts[4] if len(parts) > 4 else ""
        base_url = parts[5] if len(parts) > 5 else model_manager.PROVIDER_TYPES.get(provider_type, {}).get("base_url", "")
        if provider_type not in model_manager.PROVIDER_TYPES:
            _imos_line(f"unknown type {provider_type}. run /model types")
            return
        payload = {
            "id": f"{provider_type}-{model_name.replace('/', '-')[:24]}",
            "name": f"{model_manager.PROVIDER_TYPES[provider_type]['name']} ({model_name})",
            "type": provider_type,
            "model": model_name,
            "api_key": api_key,
            "base_url": base_url,
            "enabled": True,
            "is_default": True,
        }
        row = model_manager.add_provider(payload)
        _activate_provider_row(row)
        ctx.switch_provider(current_provider, current_model)
        _imos_line(f"model added: {row['id']} -> {row['type']} / {row['model']}")
        try:
            dashboard.emit_models(model_manager.load_providers(), model_manager.get_default())
        except Exception:
            pass
        return
    if action == "use":
        if len(parts) < 3:
            _imos_line("usage: /model use <provider_id>")
            return
        provider_id = parts[2]
        row = next((r for r in model_manager.load_providers() if r["id"] == provider_id or r["id"].startswith(provider_id)), None)
        if not row:
            _imos_line(f"provider not found: {provider_id}")
            return
        _activate_provider_row(row)
        ctx.switch_provider(current_provider, current_model)
        _imos_line(f"active model: {_provider_name()}")
        return
    if action == "default":
        if len(parts) < 3:
            _imos_line("usage: /model default <provider_id>")
            return
        row = model_manager.set_default(parts[2])
        _activate_provider_row(row)
        _imos_line(f"default model: {row['id']} / {row['model']}")
        return
    if action == "remove":
        if len(parts) < 3:
            _imos_line("usage: /model remove <provider_id>")
            return
        if model_manager.remove_provider(parts[2]):
            _init_active_provider()
            ctx.switch_provider(current_provider, current_model)
            _imos_line(f"removed provider {parts[2]}")
        else:
            _imos_line(f"provider not found: {parts[2]}")
        return
    _imos_line("unknown /model action. try list, types, add, use, default, remove")


def _switch_provider_command(new_provider: str) -> None:
    old_provider = current_provider
    old_model = current_model
    _imos_line("generating conversation summary...")
    summary = ctx.generate_summary(get_response)
    new_provider_name, new_model_name = _set_current_provider(new_provider)
    ctx.switch_provider(new_provider_name, new_model_name)
    stats = ctx.get_stats()
    rows = [
        f"From      : {old_provider} / {old_model}",
        f"To        : {new_provider_name} / {new_model_name}",
        f"Messages  : {stats['message_count']} messages carried over",
        f"Tokens    : ~{stats['token_estimate']} estimated",
    ]
    for idx, line in enumerate(_wrap_lines(_truncate(summary, 120), 52)):
        rows.append(f"Summary   : {line}" if idx == 0 else f"            {line}")
    _imos_line("context transferred")
    _show_box("Provider Switch", rows)
    _imos_line(f"continuing on {new_provider_name}. your context is intact.")


def _first_launch_consent_gate() -> None:
    IMOS_HOME.mkdir(parents=True, exist_ok=True)
    if INITIALIZED_PATH.exists():
        return
    if UI:
        UI.clear()
        UI.assistant("Before IMOS controls this PC, grant permissions for real execution.")
        UI.status("You can change these anytime: /policy-set <tool> allow|ask|deny")
    else:
        _clear_screen()
        print(" Before IMOS takes control of this machine, you must grant permissions.")
        print("  You can change these at any time with /policy-set <tool> <allow|ask|deny>\n")
    answers = {}
    for tool_name in pol.all().keys():
        answer = input(f"  Grant {tool_name}? [y/N] ").strip().lower()
        value = "allow" if answer == "y" else "ask"
        pol.set(tool_name, value)
        answers[tool_name] = value
    try:
        with open(INITIALIZED_PATH, "w", encoding="utf-8") as file_handle:
            json.dump({"initialized_at": datetime.now().isoformat(), "answers": answers}, file_handle, indent=2)
    except Exception as error:
        _imos_line(f"error: {error}")
    print("\n   Permissions saved. You can audit them anytime with /policy\n")
    time.sleep(1.0)


def _boot_sequence() -> None:
    if UI:
        UI.clear()
        try:
            from imos.auth import current_user

            user = current_user()
            email = str(user.get("email", "") or "")
        except Exception:
            email = ""
        stats = ctx.get_stats()
        UI.banner(
            email=email,
            model=_provider_name(),
            session_id=stats["session_id"],
        )
    else:
        _clear_screen()
        print("  IMOS    Operator Runtime\n")
        print(f"  Provider: {_provider_name()}  ·  dashboard http://localhost:7070\n")
    try:
        dashboard.emit_services(list_all_services())
        dashboard.emit_models(model_manager.load_providers(), model_manager.get_default())
        from imos.auth import current_user

        dashboard.emit_auth(current_user())
        dashboard.emit_runtime()
        dashboard.emit_routing({"rules": routing.list_rules(), "path": str(routing.path)})
    except Exception:
        pass
    _audit("session_start", "IMOS operator runtime ready", {"session_id": ctx.session_id[:8]})


def execute_plan(user_input: str, plan_data: dict) -> None:
    goal = plan_data.get("goal", "")
    steps = plan_data.get("steps", [])
    goal_summary = f"Goal: {goal}. Reasoning: {plan_data.get('reasoning', '')}"
    ctx.add_message("assistant", goal_summary, current_provider, current_model)
    task_id = tracker.start(goal, len(steps))
    mem.save("last_goal", goal)
    _audit("plan_start", goal, {"steps": len(steps), "task_id": task_id[:8]})
    _show_session_card(goal, len(steps), _provider_name(), task_id)
    try:
        dashboard.emit_plan(
            {
                "goal": goal,
                "steps": len(steps),
                "task_id": task_id[:8],
                "provider": _provider_name(),
            }
        )
    except Exception:
        pass
    had_failure = False

    for index, step in enumerate(steps, start=1):
        tool = step.get("tool", "unknown")
        description = _truncate(step.get("description", ""), 60)
        if UI:
            UI.tool_start(tool, description)
        else:
            _imos_line(f"step {index}/{len(steps)}    {tool}")
            print(f"   Step {index}/{len(steps)}  {tool}")
            print(f"    {description}")
        try:
            dashboard.emit_step(
                {
                    "step": index,
                    "total": len(steps),
                    "tool": tool,
                    "description": description,
                    "status": "running",
                    "output": "",
                }
            )
        except Exception:
            pass
        try:
            result = execute_tool(step)
            result_text = result.get("result") or result.get("status", "")
            if result_text:
                _record_tool_result(step, result_text)
                tracker.update(task_id, result_text)
                try:
                    dashboard.emit_step(
                        {
                            "step": index,
                            "total": len(steps),
                            "tool": tool,
                            "description": description,
                            "status": "done" if result.get("status") not in {"denied", "skipped by user", "failed"} else "failed",
                            "output": _truncate(result_text, 240),
                        }
                    )
                except Exception:
                    pass

            if tool == "run_shell" and result.get("exit_code", 0) != 0:
                had_failure = True
                error_message = _truncate(result.get("stderr", "") or "shell command failed", 90)
                _imos_line(f"step failed: {error_message}")
                fix_step = _suggest_shell_fix(result.get("command", ""), result.get("stderr", ""))
                if fix_step:
                    fix_command = fix_step.get("params", {}).get("command", "")
                    _imos_line(f"suggested fix: {fix_command}")
                    answer = input("imos  apply fix? [y/N] ").strip().lower()
                    if answer == "y":
                        fix_result = execute_tool(fix_step)
                        fix_text = fix_result.get("result") or fix_result.get("status", "")
                        if fix_text:
                            _record_tool_result(fix_step, fix_text)
                            tracker.update(task_id, fix_text)
                            try:
                                dashboard.emit_log(f"applied fix: {fix_command}")
                            except Exception:
                                pass
                _imos_line(f"step {index}/{len(steps)} failed  {error_message}")
                try:
                    dashboard.emit_step(
                        {
                            "step": index,
                            "total": len(steps),
                            "tool": tool,
                            "description": description,
                            "status": "failed",
                            "output": error_message,
                        }
                    )
                except Exception:
                    pass
                continue

            if result.get("status") in {"denied", "skipped by user", "failed"}:
                had_failure = True
                _imos_line(f"step {index}/{len(steps)} failed  {_truncate(result.get('status', 'failed'), 60)}")
            else:
                if UI:
                    UI.tool_end(ok=True)
                else:
                    _imos_line(f"step {index}/{len(steps)} done")
        except Exception as error:
            had_failure = True
            short_error = _truncate(str(error), 60)
            tracker.update(task_id, f"Step error: {short_error}")
            _imos_line(f"step {index}/{len(steps)} failed  {short_error}")
            try:
                dashboard.emit_step(
                    {
                        "step": index,
                        "total": len(steps),
                        "tool": tool,
                        "description": description,
                        "status": "failed",
                        "output": short_error,
                    }
                )
            except Exception:
                pass

    tracker.finish(task_id, "failed" if had_failure else "done")
    mem.append_log(f"{user_input}  {goal}")
    if UI:
        UI.assistant(f"Done: {goal}")
    else:
        _imos_line(f"goal complete: {_truncate(goal, 55)}")


def _shutdown_session() -> None:
    try:
        ctx.generate_summary(get_response)
    except Exception:
        pass
    stats = ctx.get_stats()
    providers = "  ".join(stats["providers_used"]) or current_provider
    print(f"Session {stats['session_id'][:8]} saved    {stats['message_count']} messages    {providers}")


def run_operator_cli(ui_module=None) -> None:
    global UI, VERBOSE_THINK
    UI = ui_module
    _first_launch_consent_gate()
    _boot_sequence()

    while True:
        try:
            user_input = dashboard.pop_chat_inbox() or ""
            if not user_input:
                if UI:
                    user_input = UI.read_user_input()
                else:
                    user_input = input("imos  ").strip()
            elif UI:
                UI.user_echo(user_input)
            if not user_input:
                continue
            if user_input in {"/exit", "exit"}:
                _shutdown_session()
                break
            if user_input == "/help":
                print(HELP_TEXT)
                continue
            if user_input == "/dashboard":
                _imos_line("dashboard at http://localhost:7070")
                webbrowser.open("http://localhost:7070")
                continue
            if user_input == "/status":
                _show_status()
                continue
            if user_input == "/runtime":
                _show_runtime()
                continue
            if user_input == "/memory":
                _show_memory()
                continue
            if user_input.startswith("/audit"):
                parts = user_input.split()
                limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 15
                _show_audit(limit)
                continue
            if user_input == "/routing":
                _show_routing()
                continue
            if user_input.startswith("/route "):
                parts = user_input.split()
                if len(parts) != 3:
                    _imos_line("usage: /route <task_type> <provider>  e.g. /route code groq")
                else:
                    routing.set_rule(parts[1], parts[2])
                    _audit("routing", f"rule set {parts[1]} → {parts[2]}", {"rules": routing.list_rules()})
                    dashboard.emit_routing({"rules": routing.list_rules()})
                    _imos_line(f"routing: {parts[1]} → {parts[2]}")
                continue
            if user_input == "/policy":
                pol.show()
                continue
            if user_input.startswith("/policy-set "):
                parts = user_input.split()
                if len(parts) != 3:
                    _imos_line("error: usage: /policy-set <tool> <allow|ask|deny>")
                else:
                    pol.set(parts[1], parts[2])
                    _audit("policy", f"{parts[1]} → {parts[2]}", {})
                    dashboard.emit_policy(pol.all())
                    _imos_line(f"policy updated: {parts[1]}={parts[2]}")
                continue
            if user_input == "/tasks":
                _show_tasks()
                continue
            if user_input.startswith("/task "):
                _show_task(user_input.split(maxsplit=1)[1])
                continue
            if user_input.startswith("/switch "):
                _switch_provider_command(user_input.split(maxsplit=1)[1])
                continue
            if user_input == "/sessions":
                _show_sessions()
                continue
            if user_input.startswith("/resume "):
                _resume_session(user_input.split(maxsplit=1)[1])
                continue
            if user_input == "/export":
                _export_session()
                continue
            if user_input == "/session":
                _show_current_session()
                continue
            if user_input == "/services":
                services = list_all_services()
                rows = [
                    f"{s['label'][:22]:<22} {'on' if s.get('available') else 'off':<4} [{s.get('category', '')[:10]}]"
                    for s in services
                ]
                _show_box(f"Services ({len(services)})", rows[:24])
                try:
                    dashboard.emit_services(services)
                except Exception:
                    pass
                continue
            if user_input.startswith("/service add "):
                label = user_input.split(maxsplit=3)[2] if len(user_input.split()) > 2 else "Custom"
                detail = user_input.split(maxsplit=3)[3] if len(user_input.split()) > 3 else ""
                entry = save_custom_service({"label": label, "detail": detail})
                _imos_line(f"custom service added: {entry['id']}")
                try:
                    dashboard.emit_services(list_all_services())
                except Exception:
                    pass
                continue
            if user_input.startswith("/model"):
                _handle_model_command(user_input.split())
                continue
            if user_input.startswith("/transfer"):
                _transfer_context_command(user_input.split())
                continue

            if UI:
                UI.user_echo(user_input)
            conversation_history.append({"role": "user", "content": user_input})
            ctx.add_message("user", user_input, current_provider, current_model)
            _dashboard_chat("user", user_input)
            _apply_task_routing(user_input)

            if UI:
                UI.status("Running operator loop…")
            else:
                _imos_line("thinking...")
            think_data = think(user_input, get_response, _provider_messages)
            _dashboard_think(think_data)
            if VERBOSE_THINK:
                for line in think_data.get("reasoning_steps", [])[:4]:
                    if UI:
                        UI.thinking(line, verbose=True)
                    else:
                        _imos_line(f"think  {line}")

            if _should_execute(user_input, think_data):
                decision = {"mode": "execute", "reason": "real execution", "reply": ""}
            else:
                decision = route_intent(user_input)
                if decision["mode"] == "chat" and _should_execute(user_input, think_data):
                    decision = {"mode": "execute", "reason": "action implied", "reply": ""}

            if decision["mode"] == "chat":
                reply = (
                    str(think_data.get("reply", "")).strip()
                    or str(decision.get("reply", "")).strip()
                    or chat(user_input)
                )
                conversation_history.append({"role": "assistant", "content": reply})
                ctx.add_message("assistant", reply, current_provider, current_model)
                _dashboard_chat("assistant", reply)
                mem.append_log(f"chat: {_truncate(user_input, 80)}")
                if UI:
                    UI.assistant(reply)
                else:
                    print(f"imos  {reply}")
                continue

            if UI:
                UI.status("Planning real steps…")
            else:
                _imos_line("planning...")
            plan_data = plan(user_input, think_data)
            conversation_history.append({"role": "assistant", "content": plan_data})
            execute_plan(user_input, plan_data)
        except KeyboardInterrupt:
            if UI:
                UI.status("Interrupted.")
            break
        except Exception as error:
            if UI:
                UI.error(str(error))
            else:
                _imos_line(f"error: {str(error)}")
            _imos_line("runtime still active.")

    try:
        browser.close()
    except Exception:
        pass


def main() -> None:
    from imos.operator_shell import run

    run()


if __name__ == "__main__":
    main()
