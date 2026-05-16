from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from core.runtime_session import runtime_session
from core.events import event_bus

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "prompt": {"type": "string"},
        "project_name": {"type": "string"},
        "preferred_tool": {"type": "string"},
        "tool": {"type": "string"},
        "messages": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["action"],
}

_ACTIVE_STATE: dict[str, str] = {}
_SESSION_STATE: dict[str, Any] = {}
_CREDIT_PATH = Path(__file__).resolve().parents[2] / "config" / "vibe_credits.json"
_DEFAULT_CREDITS = {
    "lovable": {"exhausted": False, "last_checked": ""},
    "bolt": {"exhausted": False, "last_checked": ""},
    "v0": {"exhausted": False, "last_checked": ""},
    "replit": {"exhausted": False, "last_checked": ""},
    "stackblitz": {"exhausted": False, "last_checked": ""},
}


def _timestamp() -> str:
    return datetime.utcnow().isoformat()


def _ensure_credit_state() -> dict[str, dict[str, Any]]:
    _CREDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _CREDIT_PATH.exists():
        _CREDIT_PATH.write_text(json.dumps(_DEFAULT_CREDITS, indent=2), encoding="utf-8")
        return json.loads(json.dumps(_DEFAULT_CREDITS))
    try:
        loaded = json.loads(_CREDIT_PATH.read_text(encoding="utf-8"))
    except Exception:
        loaded = {}
    merged = json.loads(json.dumps(_DEFAULT_CREDITS))
    for name, payload in loaded.items():
        if name in merged and isinstance(payload, dict):
            merged[name].update(payload)
    _CREDIT_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged


def load_credit_state() -> dict[str, dict[str, Any]]:
    return _ensure_credit_state()


def save_credit_state(state: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    _CREDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CREDIT_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def mark_exhausted(tool_name: str, exhausted: bool = True) -> dict[str, dict[str, Any]]:
    state = load_credit_state()
    if tool_name in state:
        state[tool_name]["exhausted"] = exhausted
        state[tool_name]["last_checked"] = _timestamp()
    return save_credit_state(state)


def reset_credit_state(tool_name: str | None = None) -> dict[str, dict[str, Any]]:
    state = load_credit_state()
    targets = [tool_name] if tool_name else list(state.keys())
    for name in targets:
        if name in state:
            state[name]["exhausted"] = False
            state[name]["last_checked"] = _timestamp()
    return save_credit_state(state)


def summarize_credit_state() -> str:
    state = load_credit_state()
    return "\n".join(
        f"{name}: {'exhausted' if payload.get('exhausted') else 'ok'}"
        for name, payload in state.items()
    )


def get_active_tool() -> str:
    return _ACTIVE_STATE.get("tool", "") or str(runtime_session.active_tool or "")


def set_active_tool(tool_name: str, project_name: str = "") -> None:
    _ACTIVE_STATE["tool"] = tool_name
    _ACTIVE_STATE["project_name"] = project_name
    runtime_session.update_state(active_tool=tool_name, active_project=project_name)


def clear_active_tool() -> None:
    _ACTIVE_STATE.clear()
    runtime_session.update_state(active_tool=None, active_project=None)


def get_active_project() -> str:
    return _ACTIVE_STATE.get("project_name", "") or str(runtime_session.active_project or "")


def _session_messages() -> list[str]:
    messages = _SESSION_STATE.get("messages")
    return messages if isinstance(messages, list) else []


def _set_session(project_name: str, tool_name: str, source_prompt: str, build_prompt: str) -> None:
    _SESSION_STATE.clear()
    _SESSION_STATE.update(
        {
            "project_name": project_name,
            "tool_name": tool_name,
            "source_prompt": source_prompt,
            "build_prompt": build_prompt,
            "messages": [source_prompt],
        }
    )


def _set_session_path(path: str) -> None:
    if path:
        _SESSION_STATE["path"] = path


def _append_session_messages(messages: list[str]) -> None:
    history = _session_messages()
    history.extend(messages)
    _SESSION_STATE["messages"] = history[-24:]


def _session_path() -> str:
    return str(_SESSION_STATE.get("path", "") or "")


def _derive_project_name(prompt: str) -> str:
    words = prompt.lower().split()[:4]
    project_name = "-".join(
        word for word in words if word not in {"me", "a", "the", "an", "build", "make", "create"}
    )
    return project_name or "my-project"


def _vibe_output_base(project_name: str) -> tuple[str, str]:
    output_base = os.path.join(os.path.expanduser("~"), "Desktop", "imos_projects")
    output_dir = os.path.join(output_base, project_name)
    os.makedirs(output_dir, exist_ok=True)
    return output_base, output_dir


def _heuristic_build_prompt(prompt: str, project_name: str) -> str:
    cleaned = " ".join(prompt.split())
    return "\n".join(
        [
            f"Build a production-ready AI SaaS application named {project_name}.",
            "",
            "Primary request:",
            cleaned,
            "",
            "Requirements:",
            "- Do not generate a generic starter or placeholder project.",
            "- Expand the request into a complete scoped product with real flows and detailed implementation.",
            "- Include auth, onboarding, settings, data persistence, billing-ready structure, and responsive UI.",
            "- Preserve project context so future prompts continue the same app instead of restarting.",
            "- Include deployment and publish flow support where relevant.",
            "- Build the actual app, not only a landing page.",
        ]
    )


def _build_generation_prompt(prompt: str, project_name: str) -> str:
    from tools.agent_bridges import chat_with_configured_model

    rewrite_prompt = (
        "Rewrite the user's request into a single detailed build brief for a vibe-coding tool.\n"
        "The output must force the tool to build the real product, not a generic starter.\n"
        "Use these sections exactly: Product, Users, Core Features, AI Providers and Model Support, Integrations, "
        "Dashboard and Admin, Data and Storage, Auth and Access, Deployment, Quality Bar.\n"
        "Do not use markdown code fences. Do not say 'make a project'.\n\n"
        f"Project name: {project_name}\n"
        f"User request:\n{prompt}"
    )
    result = chat_with_configured_model(rewrite_prompt)
    if result.get("success"):
        reply = str(result.get("reply", "")).strip()
        if reply and "make a project" not in reply.lower():
            return reply
    return _heuristic_build_prompt(prompt, project_name)


def _local_scaffold(prompt: str, project_name: str, workspace: str) -> dict[str, Any]:
    from skills.scaffold_react_app.handler import run as scaffold_react_app_run

    return scaffold_react_app_run(
        {"project_name": project_name, "template": "react", "package_manager": "npm"},
        workspace=workspace,
    )


def _tool_runs():
    from skills.vibe_coder.browser import (
        run_on_bolt,
        run_on_lovable,
        run_on_replit,
        run_on_stackblitz,
        run_on_v0,
    )

    return [
        ("lovable", run_on_lovable),
        ("bolt", run_on_bolt),
        ("v0", run_on_v0),
        ("replit", run_on_replit),
        ("stackblitz", run_on_stackblitz),
    ]


def _extract_current(tool_name: str, project_name: str, output_base: str, output_dir: str) -> dict[str, Any]:
    from skills.vibe_coder.extractor import click_download_and_save, clone_if_github_visible, copy_code_from_screen
    from tools.agent_bridges import open_ide_with_fallback

    extracted = click_download_and_save(tool_name, project_name, output_base)
    if not extracted.get("ok"):
        extracted = copy_code_from_screen(output_dir)
    if not extracted.get("ok"):
        extracted = clone_if_github_visible()
    if extracted.get("ok"):
        try:
            open_ide_with_fallback(extracted["path"])
        except Exception:
            pass
    return extracted


def _run_orchestrator(prompt: str, project_name: str | None, preferred_tool: str | None, workspace: str) -> dict[str, Any]:
    project = project_name or _derive_project_name(prompt)
    build_prompt = _build_generation_prompt(prompt, project)
    runtime_session.update_state(active_project=project)
    runtime_session.log_operation(
        "vibe_coder",
        {"prompt": prompt, "build_prompt": build_prompt, "project_name": project, "preferred_tool": preferred_tool or ""},
    )
    event_bus.publish("tool_progress", message=f"Starting build orchestration for {project}")
    output_base, output_dir = _vibe_output_base(project)
    if not preferred_tool:
        event_bus.publish("tool_progress", message="Trying local scaffold first...")
        local_result = _local_scaffold(prompt, project, workspace)
        if local_result.get("ok"):
            clear_active_tool()
            runtime_session.complete_operation("vibe_coder", {"result": local_result})
            return local_result

    credits = load_credit_state()
    tool_runs = _tool_runs()
    if preferred_tool:
        tool_runs.sort(key=lambda item: 0 if item[0] == preferred_tool else 1)

    for tool_name, tool_fn in tool_runs:
        if credits.get(tool_name, {}).get("exhausted"):
            print(f"  Skipping {tool_name} (credits exhausted)")
            continue
        print(f"\n  Trying {tool_name}...")
        event_bus.publish("tool_progress", message=f"Trying {tool_name}...")
        result = tool_fn(build_prompt, project)
        status = result.get("status")
        if status == "exhausted":
            print(f"  {tool_name}: credits exhausted  trying next tool")
            event_bus.publish("tool_progress", message=f"{tool_name} credits exhausted")
            mark_exhausted(tool_name)
            credits = load_credit_state()
            continue
        if status == "auth_required":
            set_active_tool(tool_name, project)
            _set_session(project, tool_name, prompt, build_prompt)
            auth_message = result.get("error", f"{tool_name} requires sign-in before it can continue.")
            runtime_session.complete_operation("vibe_coder", {"tool": tool_name, "status": status, "message": auth_message})
            return {"ok": False, "tool": tool_name, "status": status, "message": auth_message}
        if status == "complete":
            print(f"  {tool_name}: generation complete  extracting code")
            event_bus.publish("tool_progress", message=f"{tool_name} generation complete  extracting code")
            set_active_tool(tool_name, project)
            _set_session(project, tool_name, prompt, build_prompt)
            extracted = _extract_current(tool_name, project, output_base, output_dir)
            if extracted.get("ok"):
                _set_session_path(str(extracted.get("path", "")))
                event_bus.publish("tool_progress", message=f"Done  project at {extracted['path']}")
                event_bus.publish("tool_progress", message="Opening in editor...")
                runtime_session.complete_operation("vibe_coder", {"tool": tool_name, "path": extracted["path"]})
                return {
                    "ok": True,
                    "tool": tool_name,
                    "path": extracted["path"],
                    "message": f"Project built with {tool_name} and saved to {extracted['path']}. Opening in editor.",
                }
            return {"ok": False, "message": extracted.get("error", "Could not extract generated code.")}
        if status == "timeout":
            print(f"  {tool_name}: timed out  trying next tool")
            event_bus.publish("tool_progress", message=f"{tool_name} timed out")
            continue
        if status == "error":
            print(f"  {tool_name}: error  trying next tool")
            event_bus.publish("tool_progress", message=f"{tool_name} error")
            continue

    final_state = load_credit_state()
    tracked_tools = [name for name, _ in _tool_runs()]
    all_exhausted = all(final_state.get(name, {}).get("exhausted") for name in tracked_tools)
    if all_exhausted:
        result = {
            "ok": False,
            "message": (
                "Credits finished on all tools (Lovable, Bolt, v0). "
                "To continue: sign up for a new account on any of these tools, or use your local scaffold instead. "
                "Run: /vibe reset  to reset credit tracking."
            ),
        }
        runtime_session.complete_operation("vibe_coder", {"result": result})
        return result
    result = {
        "ok": False,
        "message": "All vibe coding tools failed or timed out. Try: build me a react website  to use local scaffold.",
    }
    runtime_session.complete_operation("vibe_coder", {"result": result})
    return result


def run(inputs, *, workspace: str, **_kwargs):
    action = str(inputs.get("action", "orchestrate")).strip().lower()
    if action == "status":
        return {"ok": True, "state": load_credit_state(), "summary": summarize_credit_state()}
    if action == "reset":
        tool_name = str(inputs.get("tool", "")).strip().lower() or None
        state = reset_credit_state(tool_name)
        return {"ok": True, "state": state}
    if action == "extract":
        tool_name = get_active_tool()
        project_name = get_active_project() or str(inputs.get("project_name", "")).strip() or "project"
        output_base, output_dir = _vibe_output_base(project_name)
        extracted = _extract_current(tool_name or "current", project_name, output_base, output_dir)
        return extracted
    if action == "continue":
        from skills.vibe_coder.browser import continue_conversation

        tool_name = get_active_tool()
        if not tool_name:
            return {"ok": False, "error": "No active vibe coding tool session."}
        messages = inputs.get("messages") or []
        if not messages:
            single = str(inputs.get("prompt", "")).strip()
            messages = [single] if single else []
        cleaned = [str(item).strip() for item in messages if str(item).strip()]
        if cleaned:
            _append_session_messages(cleaned)
        return continue_conversation(
            tool_name,
            cleaned,
            project_name=get_active_project(),
            session_messages=_session_messages(),
        )
    if action == "publish":
        tool_name = get_active_tool()
        target = str(inputs.get("tool", "")).strip().lower()
        project_path = _session_path()
        if project_path and target in {"vercel", "netlify"}:
            if target == "vercel":
                from skills.deploy_vercel.handler import run as deploy_vercel_run

                return deploy_vercel_run(
                    {"action": "deploy", "project_dir": project_path, "project_name": get_active_project() or Path(project_path).name},
                    workspace=workspace,
                )
            from skills.deploy_netlify.handler import run as deploy_netlify_run

            return deploy_netlify_run(
                {"action": "deploy", "project_dir": project_path, "site_name": get_active_project() or Path(project_path).name},
                workspace=workspace,
            )
        if tool_name:
            from skills.vibe_coder.browser import automate_publish

            return automate_publish(tool_name, project_name=get_active_project(), target=target or "publish")
        return {"ok": False, "error": "No active vibe coding session or extracted project to publish."}

    prompt = str(inputs.get("prompt", "")).strip()
    project_name = str(inputs.get("project_name", "")).strip() or None
    preferred_tool = str(inputs.get("preferred_tool", "")).strip().lower() or None
    if not prompt:
        return {"ok": False, "message": "Prompt is required."}
    return _run_orchestrator(prompt, project_name, preferred_tool, workspace)
