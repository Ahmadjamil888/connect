from __future__ import annotations

from tools.ide_automation import continue_ide_session, start_ide_session

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "target": {"type": "string"},
        "prompt": {"type": "string"},
        "project_name": {"type": "string"},
        "project_path": {"type": "string"},
        "wait_for_response": {"type": "boolean"},
    },
    "required": ["action"],
}


def run(inputs, *, workspace: str, **_kwargs):
    action = str(inputs.get("action", "start")).strip().lower() or "start"
    target = str(inputs.get("target", "cursor")).strip().lower() or "cursor"
    prompt = str(inputs.get("prompt", "")).strip()
    if action in {"start", "launch"}:
        if not prompt:
            return {"ok": False, "error": "Prompt is required."}
        return start_ide_session(
            target=target,
            workspace=workspace,
            prompt=prompt,
            project_name=str(inputs.get("project_name", "")).strip(),
            project_path=str(inputs.get("project_path", "")).strip(),
            wait_for_response=bool(inputs.get("wait_for_response", True)),
        )
    if action == "continue":
        if not prompt:
            return {"ok": False, "error": "Prompt is required."}
        return continue_ide_session(
            target=target,
            prompt=prompt,
            wait_for_response=bool(inputs.get("wait_for_response", True)),
        )
    return {"ok": False, "error": f"Unsupported action: {action}"}
