from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from imos.adapters.vcs.common import BaseVCSAdapter


class LocalGitAdapter(BaseVCSAdapter):
    def __init__(self, name: str = "local_git", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["repo", "commits", "branches", "stash", "tags", "diff", "log"])
        self.repo_path = Path((config or {}).get("repo_path", Path.cwd())).resolve()
        self.repo = None

    async def connect(self) -> bool:
        await super().connect()
        from git import Repo

        self.repo = await asyncio.to_thread(Repo, self.repo_path)
        self.status = "connected"
        return True

    async def health_check(self) -> bool:
        return self.repo_path.exists()

    async def init(self, path: str | None = None) -> Any:
        from git import Repo

        target = Path(path or self.repo_path).resolve()
        return await asyncio.to_thread(Repo.init, target)

    async def clone(self, url: str, path: str) -> Any:
        from git import Repo

        return await asyncio.to_thread(Repo.clone_from, url, path)

    async def add(self, pattern: str = ".") -> Any:
        return await asyncio.to_thread(self.repo.git.add, pattern)

    async def commit(self, message: str) -> Any:
        return await asyncio.to_thread(self.repo.index.commit, message)

    async def push(self, remote: str = "origin", branch: str | None = None) -> Any:
        remote_obj = self.repo.remote(remote)
        return await asyncio.to_thread(remote_obj.push, branch)

    async def pull(self, remote: str = "origin", branch: str | None = None) -> Any:
        remote_obj = self.repo.remote(remote)
        return await asyncio.to_thread(remote_obj.pull, branch)

    async def branch(self, name: str) -> Any:
        return await asyncio.to_thread(self.repo.git.checkout, "-b", name)

    async def merge(self, branch_name: str) -> Any:
        return await asyncio.to_thread(self.repo.git.merge, branch_name)

    async def rebase(self, branch_name: str) -> Any:
        return await asyncio.to_thread(self.repo.git.rebase, branch_name)

    async def stash(self) -> Any:
        return await asyncio.to_thread(self.repo.git.stash)

    async def tag(self, name: str) -> Any:
        return await asyncio.to_thread(self.repo.create_tag, name)

    async def diff(self) -> Any:
        return await asyncio.to_thread(self.repo.git.diff)

    async def log(self, max_count: int = 10) -> Any:
        commits = await asyncio.to_thread(lambda: list(self.repo.iter_commits(max_count=max_count)))
        return [{"hexsha": commit.hexsha, "message": commit.message.strip()} for commit in commits]
