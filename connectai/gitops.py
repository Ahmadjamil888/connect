from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List


class GitAutopilot:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def _ensure_repo(self):
        if not (self.repo_path / ".git").exists():
            result = self._run("init")
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git init failed")

    def status(self) -> Dict[str, Any]:
        self._ensure_repo()
        branch = self._run("branch", "--show-current").stdout.strip() or "main"
        porcelain = self._run("status", "--porcelain").stdout.splitlines()
        untracked = [line[3:] for line in porcelain if line.startswith("?? ")]
        modified = [line[3:] for line in porcelain if line and not line.startswith("?? ")]
        return {
            "branch": branch,
            "dirty": bool(porcelain),
            "untracked": untracked,
            "modified": modified,
        }

    def create_task_branch(self, task_name: str) -> str:
        self._ensure_repo()
        slug = re.sub(r"[^a-z0-9._-]+", "-", task_name.lower()).strip("-")[:50] or "task"
        branch = f"agent/{slug}"
        branches = self._run("branch", "--list", branch).stdout.strip()
        if not branches:
            created = self._run("checkout", "-b", branch)
            if created.returncode != 0:
                raise RuntimeError(created.stderr.strip() or created.stdout.strip() or "git checkout -b failed")
        else:
            switched = self._run("checkout", branch)
            if switched.returncode != 0:
                raise RuntimeError(switched.stderr.strip() or switched.stdout.strip() or "git checkout failed")
        return branch

    def stage_and_commit(self, message: str) -> str:
        self._ensure_repo()
        self._run("add", "-A")
        status = self._run("status", "--porcelain").stdout.strip()
        if not status:
            return "nothing-to-commit"
        result = self._run("commit", "-m", f"[agent] {message[:120]}")
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git commit failed")
        sha = self._run("rev-parse", "--short", "HEAD").stdout.strip()
        return sha

    def diff_summary(self) -> str:
        self._ensure_repo()
        result = self._run("diff", "--stat")
        return result.stdout.strip() or "no changes"

    def get_log(self, n: int = 5) -> List[Dict[str, Any]]:
        self._ensure_repo()
        result = self._run("log", f"-{n}", "--pretty=format:%h|%an|%s")
        rows = []
        for line in result.stdout.splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                rows.append({"hash": parts[0], "author": parts[1], "msg": parts[2]})
        return rows
