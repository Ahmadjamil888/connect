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

from core.browser import Browser
from core.context import ContextManager
from core.dashboard import Dashboard
from core.memory import Memory
from core.policy import Policy
from core.providers import get_response
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

current_provider = os.getenv("AI_PROVIDER", "groq").strip().lower() or "groq"
current_model = os.getenv(PROVIDER_MODEL_ENVS.get(current_provider, ""), "") or PROVIDER_MODEL_DEFAULTS.get(current_provider, "unknown")
ctx = ContextManager(str(uuid4()))
ctx.switch_provider(current_provider, current_model)
dashboard = Dashboard(
    memory=mem,
    policy=pol,
    tracker=tracker,
    ctx_getter=lambda: ctx,
    provider_getter=lambda: (current_provider, current_model),
    start_time=start_time,
)
dashboard.start(port=7070)

PLANNER_SYSTEM_PROMPT = """You are IMOS Planner. Take a SHORT vague user request and expand it into a complete JSON execution plan. Never ask the user for more info. Make smart decisions yourself.

IMOS exists to solve AI fragmentation. It connects inputs to visible execution and keeps work, memory, preferences, and execution attached across models, browsers, terminals, code editors, apps, and machine actions.
Plan like an operator system:
- Preserve continuity across the session.
- Prefer real execution when the user wants something built, launched, opened, scaffolded, written, or automated.
- Make plans explicit, inspectable, and delivery-oriented.
- Coordinate browser prompts, code prompts, files, terminal commands, workspace inspection, HTTP actions, and browser automation as one system.

Output only valid JSON in this exact shape:
{
  "goal": "one sentence summary",
  "reasoning": "why this approach",
  "steps": [
    {
      "step": 1,
      "description": "what this does",
      "tool": "run_shell | open_url | claude_code | write_file | open_app | read_file | list_dir | append_file | make_dir | http_request | browser",
      "params": {}
    }
  ]
}
"""

CHAT_SYSTEM_PROMPT = """You are IMOS, a terminal AI assistant.
Reply directly and briefly. Continue naturally from the existing session context.
Do not output JSON unless the user asks for JSON.
"""

INTENT_SYSTEM_PROMPT = """You are the IMOS runtime intent router.
Decide whether the latest user message should be handled as "chat" or "execute".
Choose "execute" when the user wants something created, launched, opened, scaffolded, written, automated, deployed, or run.
Choose "chat" for greetings, discussion, questions, ideation, explanation, feedback, or product positioning.

Output only valid JSON in exactly this shape:
{
  "mode": "chat|execute",
  "reason": "short reason",
  "reply": "direct assistant reply if mode is chat, otherwise empty string"
}
"""

HELP_TEXT = """Commands:
  /help                         show this help
  /dashboard                    open runtime dashboard in browser
  /status                       show runtime status
  /policy                       print current tool policy
  /policy-set <tool> <value>    set allow|ask|deny
  /tasks                        show recent tasks
  /task <id>                    show one task
  /switch <provider>            transfer context to a new provider
  /session                      current session stats
  /sessions                     list all saved sessions
  /resume <id>                  restore and continue a saved session
  /export                       export current session to markdown
  /exit                         quit IMOS
"""


def _clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _imos_line(message: str) -> None:
    print(f"imos  {message}")
    try:
        dashboard.emit_log(message)
    except Exception:
        pass


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
    if decision == "deny":
        _imos_line(f"{tool} is blocked by policy")
        return "denied"
    if decision == "ask":
        answer = input(f"  Allow {tool}: {_short_tool_description(tool, params)}? [y/N] ").strip().lower()
        if answer != "y":
            return "skipped by user"
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


def plan(user_message: str) -> dict:
    raw_response = get_response(messages=_provider_messages(), system=_planner_prompt_with_memory())
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


def execute_tool(step: dict) -> dict:
    tool = step.get("tool")
    params = step.get("params") or {}
    blocked = _policy_gate(tool, params)
    if blocked:
        return {"status": blocked, "tool": tool, "step": step.get("step"), "result": blocked}

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
            subprocess.Popen(["cursor", "."], cwd=str(PROJECT_ROOT))
            return {"status": "ok", "tool": tool, "result": "Opened Cursor"}
        if app == "vscode":
            subprocess.Popen(["code", "."], cwd=str(PROJECT_ROOT))
            return {"status": "ok", "tool": tool, "result": "Opened VS Code"}
        if app == "terminal":
            _open_terminal()
            return {"status": "ok", "tool": tool, "result": "Opened terminal"}
        raise ValueError(f"unsupported app: {app}")

    raise ValueError(f"unsupported tool: {tool}")


def _suggest_shell_fix(command: str, stderr_text: str) -> dict | None:
    prompt = f"This command failed: {command}\nError: {stderr_text}\nSuggest a fix as a new run_shell step JSON only."
    raw = get_response(messages=ctx.export_for_provider(current_provider) + [{"role": "user", "content": prompt}], system="Return only one JSON step object.")
    parsed = _parse_json_response(raw)
    if parsed.get("tool") == "run_shell":
        return parsed
    return None


def _show_status() -> None:
    tasks = tracker.all()
    done_count = sum(1 for task in tasks if task.get("status") == "done")
    running_count = sum(1 for task in tasks if task.get("status") == "running")
    failed_count = sum(1 for task in tasks if task.get("status") == "failed")
    policy_line = ", ".join(f"{key}={value}" for key, value in list(pol.all().items())[:4]) + ".."
    stats = ctx.get_stats()
    provider_history = "  ".join(stats["providers_used"]) or current_provider
    rows = [
        f"Provider  : {_provider_name()}",
        f"Memory    : {len(mem.all().get('log', []))} entries",
        f"Tasks     : {done_count} done, {running_count} running, {failed_count} failed",
        f"Policy    : {policy_line}",
        f"Session   : {stats['session_id'][:8]}    {stats['message_count']} msgs    ~{stats['token_estimate']} tokens",
        f"Providers : {provider_history}",
        f"Uptime    : {_format_uptime()}",
    ]
    _show_box("IMOS Runtime Status", rows)


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
    global current_provider, current_model
    provider = provider.strip().lower()
    if provider not in PROVIDER_MODEL_DEFAULTS:
        raise ValueError(f"unknown provider: {provider}")
    model = model or PROVIDER_MODEL_DEFAULTS[provider]
    current_provider = provider
    current_model = model
    os.environ["AI_PROVIDER"] = provider
    os.environ[PROVIDER_MODEL_ENVS[provider]] = model
    return current_provider, current_model


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
    _clear_screen()
    print("  IMOS    Operator Runtime\n")
    for line in [
        "[0.0s]  Initializing memory layer...",
        "[0.1s]  Loading policy gates...",
        "[0.2s]  Starting task tracker...",
        f"[0.3s]  Connecting AI provider: {current_provider}",
        "[0.4s]  Runtime ready.",
        "[0.5s]  Dashboard starting on :7070...",
    ]:
        print(f"  {line}")
        time.sleep(0.15)
    print("\n  Sessions  Memory  Execution  All under one surface.\n")
    print("  Type a goal or command. /help for reference.\n")


def execute_plan(user_input: str, plan_data: dict) -> None:
    goal = plan_data.get("goal", "")
    steps = plan_data.get("steps", [])
    goal_summary = f"Goal: {goal}. Reasoning: {plan_data.get('reasoning', '')}"
    ctx.add_message("assistant", goal_summary, current_provider, current_model)
    task_id = tracker.start(goal, len(steps))
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
    _imos_line(f"goal complete: {_truncate(goal, 55)}")


def _shutdown_session() -> None:
    try:
        ctx.generate_summary(get_response)
    except Exception:
        pass
    stats = ctx.get_stats()
    providers = "  ".join(stats["providers_used"]) or current_provider
    print(f"Session {stats['session_id'][:8]} saved    {stats['message_count']} messages    {providers}")


def main() -> None:
    _first_launch_consent_gate()
    _boot_sequence()

    while True:
        try:
            user_input = input("imos  ").strip()
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
            if user_input == "/policy":
                pol.show()
                continue
            if user_input.startswith("/policy-set "):
                parts = user_input.split()
                if len(parts) != 3:
                    _imos_line("error: usage: /policy-set <tool> <allow|ask|deny>")
                else:
                    pol.set(parts[1], parts[2])
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

            conversation_history.append({"role": "user", "content": user_input})
            ctx.add_message("user", user_input, current_provider, current_model)
            _imos_line("planning...")
            decision = route_intent(user_input)

            if decision["mode"] == "chat":
                reply = str(decision.get("reply", "")).strip() or chat(user_input)
                conversation_history.append({"role": "assistant", "content": reply})
                ctx.add_message("assistant", reply, current_provider, current_model)
                print(f"imos  {reply}")
                continue

            plan_data = plan(user_input)
            conversation_history.append({"role": "assistant", "content": plan_data})
            execute_plan(user_input, plan_data)
        except Exception as error:
            _imos_line(f"error: {str(error)}")
            _imos_line("the runtime is still active. type your next goal.")

    try:
        browser.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
