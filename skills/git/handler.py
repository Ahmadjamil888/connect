"""
IMOS Git skill — real git operations via gitpython.
"""
from __future__ import annotations

from pathlib import Path

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["status", "commit", "create_branch", "log", "diff", "push"],
        },
        "repo_path": {"type": "string"},
        "message": {"type": "string"},
        "branch_name": {"type": "string"},
        "limit": {"type": "integer"},
    },
    "required": ["action"],
}


def run(inputs, *, workspace: str, **_kwargs):
    action = str(inputs.get("action", "")).strip().lower()
    repo_path = str(inputs.get("repo_path", workspace)).strip() or workspace

    try:
        import git as gitpython
    except ImportError:
        return {"ok": False, "error": "gitpython is not installed. Run: pip install gitpython"}

    try:
        repo = gitpython.Repo(repo_path, search_parent_directories=True)
    except Exception as exc:
        return {"ok": False, "error": f"Not a git repository: {repo_path} — {exc}"}

    if action == "status":
        changed = [item.a_path for item in repo.index.diff(None)]
        untracked = repo.untracked_files
        staged = [item.a_path for item in repo.index.diff("HEAD")] if not repo.head.is_detached else []
        return {
            "ok": True,
            "branch": repo.active_branch.name if not repo.head.is_detached else "DETACHED",
            "changed": changed,
            "untracked": untracked,
            "staged": staged,
            "is_dirty": repo.is_dirty(untracked_files=True),
        }

    if action == "commit":
        message = str(inputs.get("message", "IMOS auto-commit")).strip() or "IMOS auto-commit"
        repo.git.add(A=True)
        commit = repo.index.commit(message)
        return {
            "ok": True,
            "commit_sha": commit.hexsha[:12],
            "message": message,
            "branch": repo.active_branch.name,
        }

    if action == "create_branch":
        branch_name = str(inputs.get("branch_name", "")).strip()
        if not branch_name:
            return {"ok": False, "error": "branch_name is required"}
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()
        return {"ok": True, "branch": branch_name}

    if action == "log":
        limit = int(inputs.get("limit", 10) or 10)
        commits = []
        for commit in list(repo.iter_commits())[:limit]:
            commits.append({
                "sha": commit.hexsha[:12],
                "message": commit.message.strip()[:100],
                "author": str(commit.author),
                "date": commit.committed_datetime.isoformat(),
            })
        return {"ok": True, "commits": commits}

    if action == "diff":
        diff = repo.git.diff()
        return {"ok": True, "diff": diff[:4000]}

    if action == "push":
        origin = repo.remote("origin")
        push_info = origin.push()
        return {"ok": True, "result": str(push_info)}

    return {"ok": False, "error": f"Unknown git action: {action}"}
