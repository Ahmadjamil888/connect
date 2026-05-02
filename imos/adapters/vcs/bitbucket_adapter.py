from __future__ import annotations

from typing import Any

import aiohttp

from imos.adapters.vcs.common import BaseVCSAdapter


class BitbucketAdapter(BaseVCSAdapter):
    def __init__(self, name: str = "bitbucket", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["repo", "commits", "pull_requests", "issues"])
        self.username = (config or {}).get("BITBUCKET_USERNAME", "")
        self.password = (config or {}).get("BITBUCKET_APP_PASSWORD", "")
        self.workspace_name = (config or {}).get("workspace_name", self.username)

    async def health_check(self) -> bool:
        return bool(self.username and self.password)

    async def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(auth=aiohttp.BasicAuth(self.username, self.password))
        async with self.session.request(method, url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as response:
            if response.status >= 400:
                raise RuntimeError(await response.text())
            return await response.json()

    async def create_repo(self, slug: str, is_private: bool = True) -> Any:
        return await self._request("POST", f"https://api.bitbucket.org/2.0/repositories/{self.workspace_name}/{slug}", {"scm": "git", "is_private": is_private})

    async def list_repos(self) -> Any:
        return await self._request("GET", f"https://api.bitbucket.org/2.0/repositories/{self.workspace_name}")

    async def list_commits(self, repo_slug: str) -> Any:
        return await self._request("GET", f"https://api.bitbucket.org/2.0/repositories/{self.workspace_name}/{repo_slug}/commits")

    async def create_pr(self, repo_slug: str, title: str, source_branch: str, destination_branch: str) -> Any:
        return await self._request(
            "POST",
            f"https://api.bitbucket.org/2.0/repositories/{self.workspace_name}/{repo_slug}/pullrequests",
            {
                "title": title,
                "source": {"branch": {"name": source_branch}},
                "destination": {"branch": {"name": destination_branch}},
            },
        )

    async def create_issue(self, repo_slug: str, title: str, content: str) -> Any:
        return await self._request(
            "POST",
            f"https://api.bitbucket.org/2.0/repositories/{self.workspace_name}/{repo_slug}/issues",
            {"title": title, "content": {"raw": content}},
        )
