"""
IMOS GitHub skill — full GitHub access via token.
Create repos, push code, create PRs, manage branches, list repos.
Token is loaded from env — never exposed to users.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import requests

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "push",
                "create_repo",
                "create_pr",
                "list_repos",
                "clone",
                "init_and_push",
                "get_repo",
                "create_branch",
                "list_prs",
            ],
        },
        "repo_dir": {"type": "string"},
        "commit_message": {"type": "string"},
        "repo_name": {"type": "string"},
        "description": {"type": "string"},
        "private": {"type": "boolean"},
        "branch": {"type": "string"},
        "base_branch": {"type": "string"},
        "pr_title": {"type": "string"},
        "pr_body": {"type": "string"},
        "clone_url": {"type": "string"},
        "remote_url": {"type": "string"},
    },
    "required": ["action"],
}

GITHUB_API = "https://api.github.com"


def _token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        from config.config import _env_value
        token = _env_value("GITHUB_TOKEN")
    return token


def _headers() -> dict:
    return {
        "Authorization": f"token {_token()}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gh(method: str, path: str, **kwargs) -> dict:
    url = f"{GITHUB_API}{path}" if path.startswith("/") else path
    r = requests.request(method, url, headers=_headers(), timeout=30, **kwargs)
    try:
        data = r.json()
    except Exception:
        data = {"message": r.text}
    if r.status_code >= 400:
        raise RuntimeError(f"GitHub {method} {path} → {r.status_code}: {data.get('message', data)}")
    return data


def _git(cmd: str, cwd: str, env: dict = None) -> tuple[int, str, str]:
    full_env = {**os.environ}
    if env:
        full_env.update(env)
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, env=full_env, timeout=120)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _get_username() -> str:
    data = _gh("GET", "/user")
    return data.get("login", "")


def run(inputs, *, workspace: str, **_kwargs):
    action = str(inputs.get("action", "push")).strip().lower()
    token = _token()
    if not token:
        return {"ok": False, "error": "GITHUB_TOKEN not configured. Add it to .env or API Keys settings."}

    # ── PUSH ──────────────────────────────────────────────────────────────
    if action == "push":
        repo_dir = Path(workspace) / str(inputs.get("repo_dir", "."))
        msg = str(inputs.get("commit_message", "IMOS auto-commit")).strip() or "IMOS auto-commit"
        branch = str(inputs.get("branch", "main")).strip() or "main"
        outputs = []
        env = {"GIT_ASKPASS": "echo", "GIT_TERMINAL_PROMPT": "0"}
        for cmd in [
            "git add -A",
            f'git commit -m "{msg}" --allow-empty',
            f"git push origin {branch}",
        ]:
            rc, out, err = _git(cmd, str(repo_dir), env)
            outputs.append(f"$ {cmd}\n{out}\n{err}".strip())
        return {"ok": True, "output": "\n\n".join(outputs)}

    # ── CREATE REPO ────────────────────────────────────────────────────────
    if action == "create_repo":
        name = str(inputs.get("repo_name", "")).strip()
        if not name:
            return {"ok": False, "error": "repo_name is required"}
        desc = str(inputs.get("description", "Created by IMOS")).strip()
        private = bool(inputs.get("private", False))
        data = _gh("POST", "/user/repos", json={
            "name": name, "description": desc, "private": private,
            "auto_init": True, "default_branch": "main",
        })
        return {
            "ok": True,
            "repo_name": data["full_name"],
            "clone_url": data["clone_url"],
            "html_url": data["html_url"],
            "ssh_url": data["ssh_url"],
        }

    # ── INIT AND PUSH (create repo + push local dir) ───────────────────────
    if action == "init_and_push":
        repo_dir = Path(workspace) / str(inputs.get("repo_dir", "."))
        name = str(inputs.get("repo_name", repo_dir.name)).strip() or repo_dir.name
        desc = str(inputs.get("description", f"IMOS project: {name}")).strip()
        private = bool(inputs.get("private", False))
        msg = str(inputs.get("commit_message", "Initial commit by IMOS")).strip()
        branch = str(inputs.get("branch", "main")).strip() or "main"

        # Create GitHub repo
        try:
            repo_data = _gh("POST", "/user/repos", json={
                "name": name, "description": desc, "private": private, "auto_init": False,
            })
            clone_url = repo_data["clone_url"]
            html_url = repo_data["html_url"]
        except RuntimeError as e:
            if "already exists" in str(e).lower() or "name already exists" in str(e).lower():
                username = _get_username()
                clone_url = f"https://github.com/{username}/{name}.git"
                html_url = f"https://github.com/{username}/{name}"
            else:
                return {"ok": False, "error": str(e)}

        # Inject token into URL
        auth_url = clone_url.replace("https://", f"https://{token}@")
        env = {"GIT_ASKPASS": "echo", "GIT_TERMINAL_PROMPT": "0"}
        steps = []

        # Init git if needed
        if not (repo_dir / ".git").exists():
            rc, out, err = _git("git init", str(repo_dir), env)
            steps.append(f"git init: {out or err}")

        # Set remote
        rc, out, err = _git("git remote -v", str(repo_dir), env)
        if "origin" in out:
            _git(f"git remote set-url origin {auth_url}", str(repo_dir), env)
        else:
            _git(f"git remote add origin {auth_url}", str(repo_dir), env)
        steps.append(f"remote set to {html_url}")

        # Commit and push
        for cmd in [
            "git add -A",
            f'git commit -m "{msg}" --allow-empty',
            f"git branch -M {branch}",
            f"git push -u origin {branch} --force",
        ]:
            rc, out, err = _git(cmd, str(repo_dir), env)
            steps.append(f"$ {cmd}: {'ok' if rc == 0 else err[:200]}")

        return {"ok": True, "html_url": html_url, "clone_url": clone_url, "steps": steps}

    # ── CREATE PR ──────────────────────────────────────────────────────────
    if action == "create_pr":
        repo_name = str(inputs.get("repo_name", "")).strip()
        if not repo_name:
            return {"ok": False, "error": "repo_name is required (owner/repo format)"}
        title = str(inputs.get("pr_title", "IMOS automated PR")).strip()
        body = str(inputs.get("pr_body", "Created by IMOS")).strip()
        head = str(inputs.get("branch", "main")).strip()
        base = str(inputs.get("base_branch", "main")).strip()
        data = _gh("POST", f"/repos/{repo_name}/pulls", json={
            "title": title, "body": body, "head": head, "base": base,
        })
        return {"ok": True, "pr_url": data["html_url"], "pr_number": data["number"]}

    # ── LIST REPOS ─────────────────────────────────────────────────────────
    if action == "list_repos":
        data = _gh("GET", "/user/repos?per_page=30&sort=updated")
        return {
            "ok": True,
            "repos": [
                {"name": r["full_name"], "url": r["html_url"], "private": r["private"], "updated": r["updated_at"]}
                for r in data
            ],
        }

    # ── CLONE ──────────────────────────────────────────────────────────────
    if action == "clone":
        url = str(inputs.get("clone_url", "")).strip()
        if not url:
            return {"ok": False, "error": "clone_url is required"}
        auth_url = url.replace("https://", f"https://{token}@")
        target = Path(workspace) / url.rstrip("/").split("/")[-1].replace(".git", "")
        rc, out, err = _git(f"git clone {auth_url} {target}", str(Path(workspace)))
        return {"ok": rc == 0, "path": str(target), "output": out or err}

    # ── GET REPO ───────────────────────────────────────────────────────────
    if action == "get_repo":
        repo_name = str(inputs.get("repo_name", "")).strip()
        if not repo_name:
            return {"ok": False, "error": "repo_name is required"}
        data = _gh("GET", f"/repos/{repo_name}")
        return {"ok": True, "name": data["full_name"], "url": data["html_url"],
                "stars": data["stargazers_count"], "language": data["language"]}

    # ── CREATE BRANCH ──────────────────────────────────────────────────────
    if action == "create_branch":
        repo_dir = Path(workspace) / str(inputs.get("repo_dir", "."))
        branch = str(inputs.get("branch", "")).strip()
        if not branch:
            return {"ok": False, "error": "branch is required"}
        rc, out, err = _git(f"git checkout -b {branch}", str(repo_dir))
        return {"ok": rc == 0, "branch": branch, "output": out or err}

    # ── LIST PRs ───────────────────────────────────────────────────────────
    if action == "list_prs":
        repo_name = str(inputs.get("repo_name", "")).strip()
        if not repo_name:
            return {"ok": False, "error": "repo_name is required"}
        data = _gh("GET", f"/repos/{repo_name}/pulls?state=open&per_page=20")
        return {"ok": True, "prs": [{"number": p["number"], "title": p["title"], "url": p["html_url"]} for p in data]}

    return {"ok": False, "error": f"Unknown action: {action}"}
