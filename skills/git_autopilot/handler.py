from __future__ import annotations

from connectai.gitops import GitAutopilot

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["status", "create_branch", "commit", "diff", "log"],
        },
        "task_name": {"type": "string"},
        "message": {"type": "string"},
        "count": {"type": "integer"},
    },
    "required": ["action"],
}


def run(inputs, *, workspace: str, **_kwargs):
    git = GitAutopilot(workspace)
    action = str(inputs["action"]).strip()
    if action == "status":
        return {"ok": True, **git.status()}
    if action == "create_branch":
        return {"ok": True, "branch": git.create_task_branch(str(inputs.get("task_name", "task")))}
    if action == "commit":
        return {"ok": True, "commit": git.stage_and_commit(str(inputs.get("message", "update")))}
    if action == "diff":
        return {"ok": True, "diff": git.diff_summary()}
    if action == "log":
        return {"ok": True, "items": git.get_log(int(inputs.get("count", 5) or 5))}
    return {"ok": False, "error": f"Unknown action: {action}"}
