from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import requests


def _git(args: list[str], cwd: str | None = None) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(Path(cwd).expanduser().resolve()) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "status": "success" if result.returncode == 0 else "error",
            "command": ["git", *args],
            "cwd": str(Path(cwd).expanduser().resolve()) if cwd else None,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "command": ["git", *args]}


def git_init(cwd: str) -> dict[str, Any]:
    return _git(["init"], cwd=cwd)


def git_status(cwd: str) -> dict[str, Any]:
    return _git(["status", "--short", "--branch"], cwd=cwd)


def git_add(cwd: str, paths: list[str] | None = None) -> dict[str, Any]:
    return _git(["add", *(paths or ["."])], cwd=cwd)


def git_commit(cwd: str, message: str) -> dict[str, Any]:
    return _git(["commit", "-m", message], cwd=cwd)


def git_push(cwd: str, remote: str = "origin", branch: str = "main", set_upstream: bool = False) -> dict[str, Any]:
    args = ["push"]
    if set_upstream:
        args.append("-u")
    args.extend([remote, branch])
    return _git(args, cwd=cwd)


def git_clone(repo_url: str, destination: str) -> dict[str, Any]:
    return _git(["clone", repo_url, destination])


def git_create_branch(cwd: str, branch: str, checkout: bool = True) -> dict[str, Any]:
    args = ["checkout", "-b", branch] if checkout else ["branch", branch]
    return _git(args, cwd=cwd)


def git_log(cwd: str, max_count: int = 10) -> dict[str, Any]:
    return _git(["log", f"--max-count={max_count}", "--oneline", "--decorate"], cwd=cwd)


def github_create_repo(name: str, private: bool = True, description: str = "") -> dict[str, Any]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        return {"status": "error", "error": "GITHUB_TOKEN is not set", "repo_name": name}
    try:
        response = requests.post(
            "https://api.github.com/user/repos",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json={"name": name, "private": private, "description": description},
            timeout=60,
        )
        data = response.json()
        if response.status_code >= 400:
            return {"status": "error", "error": data.get("message", response.text), "http_status": response.status_code}
        return {
            "status": "success",
            "repo_name": data.get("name"),
            "html_url": data.get("html_url"),
            "clone_url": data.get("clone_url"),
            "ssh_url": data.get("ssh_url"),
            "default_branch": data.get("default_branch"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "repo_name": name}


def github_create_pr(repo_owner: str, repo_name: str, head: str, base: str, title: str, body: str = "") -> dict[str, Any]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        return {"status": "error", "error": "GITHUB_TOKEN is not set", "repo": f"{repo_owner}/{repo_name}"}
    try:
        response = requests.post(
            f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json={"title": title, "head": head, "base": base, "body": body},
            timeout=60,
        )
        data = response.json()
        if response.status_code >= 400:
            return {"status": "error", "error": data.get("message", response.text), "http_status": response.status_code}
        return {
            "status": "success",
            "number": data.get("number"),
            "html_url": data.get("html_url"),
            "state": data.get("state"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "repo": f"{repo_owner}/{repo_name}"}


def create_github_repo_and_push(project_path: str, repo_name: str, commit_message: str = "Initial commit", private: bool = True) -> dict[str, Any]:
    project_dir = Path(project_path).expanduser().resolve()
    repo_result = github_create_repo(repo_name, private=private)
    if repo_result.get("status") != "success":
        return repo_result
    steps = [
        git_init(str(project_dir)),
        git_add(str(project_dir)),
        git_commit(str(project_dir), commit_message),
        _git(["remote", "add", "origin", str(repo_result["clone_url"])], cwd=str(project_dir)),
        git_push(str(project_dir), remote="origin", branch="main", set_upstream=True),
    ]
    failed = next((step for step in steps if step.get("status") != "success"), None)
    if failed is not None:
        return {
            "status": "error",
            "error": failed.get("stderr") or failed.get("error") or "git push flow failed",
            "repo_url": repo_result.get("html_url"),
            "steps": steps,
        }
    return {
        "status": "success",
        "repo_url": repo_result.get("html_url"),
        "clone_url": repo_result.get("clone_url"),
        "steps": steps,
    }
