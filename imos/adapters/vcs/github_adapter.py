from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import aiohttp

from imos.adapters.vcs.common import BaseVCSAdapter


class GithubAdapter(BaseVCSAdapter):
    def __init__(self, name: str = "github", config: dict[str, Any] | None = None) -> None:
        super().__init__(
            name=name,
            config=config,
            capabilities=["repo", "files", "commits", "branches", "pull_requests", "issues", "actions", "releases", "gists", "search", "webhooks"],
        )
        self.token = (config or {}).get("GITHUB_TOKEN") or (config or {}).get("api_key", "")
        self.username = (config or {}).get("GITHUB_USERNAME", "")
        self.client = None

    async def connect(self) -> bool:
        await super().connect()
        try:
            from github import Github
        except ModuleNotFoundError:
            self.status = "error"
            return False
        self.client = Github(self.token)
        return await self.health_check()

    async def health_check(self) -> bool:
        if self.client is None:
            return False
        try:
            await asyncio.to_thread(self.client.get_user().login.__str__)
            self.status = "connected"
            return True
        except Exception:
            self.status = "error"
            return False

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}

    async def _rest(self, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        async with self.session.request(method, url, json=payload, headers=self._headers(), timeout=aiohttp.ClientTimeout(total=120)) as response:
            if response.status >= 400:
                raise RuntimeError(await response.text())
            if response.status == 204:
                return {"status": 204}
            data = await response.text()
            return await response.json() if data else {"status": response.status}

    async def create_repo(self, name: str, private: bool = True, description: str = "") -> Any:
        return await asyncio.to_thread(self.client.get_user().create_repo, name=name, private=private, description=description)

    async def clone_repo(self, clone_url: str, path: str) -> Any:
        from git import Repo

        return await asyncio.to_thread(Repo.clone_from, clone_url, path)

    async def list_repos(self) -> Any:
        return [repo.full_name for repo in await asyncio.to_thread(lambda: list(self.client.get_user().get_repos()))]

    async def get_repo_info(self, full_name: str) -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, full_name)
        return {"full_name": repo.full_name, "default_branch": repo.default_branch, "private": repo.private, "url": repo.html_url}

    async def fork_repo(self, full_name: str) -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, full_name)
        return await asyncio.to_thread(self.client.get_user().create_fork, repo)

    async def delete_repo(self, full_name: str) -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, full_name)
        return await asyncio.to_thread(repo.delete)

    async def create_file(self, repo_name: str, path: str, content: str, message: str, branch: str = "main") -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        return await asyncio.to_thread(repo.create_file, path, message, content, branch=branch)

    async def update_file(self, repo_name: str, path: str, content: str, message: str, branch: str = "main") -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        existing = await asyncio.to_thread(repo.get_contents, path, ref=branch)
        return await asyncio.to_thread(repo.update_file, path, message, content, existing.sha, branch=branch)

    async def delete_file(self, repo_name: str, path: str, message: str, branch: str = "main") -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        existing = await asyncio.to_thread(repo.get_contents, path, ref=branch)
        return await asyncio.to_thread(repo.delete_file, path, message, existing.sha, branch=branch)

    async def get_file_content(self, repo_name: str, path: str, ref: str = "main") -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        content = await asyncio.to_thread(repo.get_contents, path, ref=ref)
        return content.decoded_content.decode("utf-8", errors="replace")

    async def list_directory(self, repo_name: str, path: str = "", ref: str = "main") -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        items = await asyncio.to_thread(repo.get_contents, path, ref=ref)
        return [{"path": item.path, "type": item.type} for item in items]

    async def create_commit(self, repo_name: str, branch: str, message: str, files: list[dict[str, str]]) -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        for file in files:
            try:
                await self.update_file(repo_name, file["path"], file["content"], message, branch=branch)
            except Exception:
                await self.create_file(repo_name, file["path"], file["content"], message, branch=branch)
        return {"status": "committed", "branch": branch, "message": message}

    async def list_commits(self, repo_name: str, branch: str = "main") -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        commits = await asyncio.to_thread(lambda: list(repo.get_commits(sha=branch)[:20]))
        return [{"sha": item.sha, "message": item.commit.message} for item in commits]

    async def get_commit_diff(self, repo_name: str, sha: str) -> Any:
        return await self._rest("GET", f"https://api.github.com/repos/{repo_name}/commits/{sha}")

    async def cherry_pick(self, repo_name: str, sha: str, branch: str) -> Any:
        repo_path = Path((self.config or {}).get("workspace", Path.cwd()))
        from git import Repo

        repo = await asyncio.to_thread(Repo, repo_path)
        await asyncio.to_thread(repo.git.checkout, branch)
        return await asyncio.to_thread(repo.git.cherry_pick, sha)

    async def create_branch(self, repo_name: str, branch_name: str, source_branch: str = "main") -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        ref = await asyncio.to_thread(repo.get_git_ref, f"heads/{source_branch}")
        return await asyncio.to_thread(repo.create_git_ref, ref=f"refs/heads/{branch_name}", sha=ref.object.sha)

    async def list_branches(self, repo_name: str) -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        branches = await asyncio.to_thread(lambda: list(repo.get_branches()))
        return [branch.name for branch in branches]

    async def delete_branch(self, repo_name: str, branch_name: str) -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        ref = await asyncio.to_thread(repo.get_git_ref, f"heads/{branch_name}")
        return await asyncio.to_thread(ref.delete)

    async def switch_branch(self, repo_name: str, branch_name: str) -> Any:
        from git import Repo

        repo = await asyncio.to_thread(Repo, Path((self.config or {}).get("workspace", Path.cwd())))
        return await asyncio.to_thread(repo.git.checkout, branch_name)

    async def merge_branch(self, repo_name: str, base: str, head: str) -> Any:
        return await self._rest("POST", f"https://api.github.com/repos/{repo_name}/merges", {"base": base, "head": head})

    async def create_pr(self, repo_name: str, title: str, body: str, head: str, base: str = "main") -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        pr = await asyncio.to_thread(repo.create_pull, title=title, body=body, head=head, base=base)
        return {"number": pr.number, "url": pr.html_url}

    async def list_prs(self, repo_name: str, state: str = "open") -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        prs = await asyncio.to_thread(lambda: list(repo.get_pulls(state=state)))
        return [{"number": pr.number, "title": pr.title, "state": pr.state} for pr in prs]

    async def merge_pr(self, repo_name: str, number: int) -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        pr = await asyncio.to_thread(repo.get_pull, number)
        return await asyncio.to_thread(pr.merge)

    async def close_pr(self, repo_name: str, number: int) -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        pr = await asyncio.to_thread(repo.get_pull, number)
        pr.state = "closed"
        return await asyncio.to_thread(pr.edit, state="closed")

    async def add_reviewers(self, repo_name: str, number: int, reviewers: list[str]) -> Any:
        return await self._rest("POST", f"https://api.github.com/repos/{repo_name}/pulls/{number}/requested_reviewers", {"reviewers": reviewers})

    async def comment_on_pr(self, repo_name: str, number: int, body: str) -> Any:
        return await self._rest("POST", f"https://api.github.com/repos/{repo_name}/issues/{number}/comments", {"body": body})

    async def get_pr_diff(self, repo_name: str, number: int) -> Any:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        headers = self._headers() | {"Accept": "application/vnd.github.v3.diff"}
        async with self.session.get(f"https://api.github.com/repos/{repo_name}/pulls/{number}", headers=headers) as response:
            response.raise_for_status()
            return await response.text()

    async def create_issue(self, repo_name: str, title: str, body: str = "") -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        issue = await asyncio.to_thread(repo.create_issue, title=title, body=body)
        return {"number": issue.number, "url": issue.html_url}

    async def list_issues(self, repo_name: str, state: str = "open") -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        issues = await asyncio.to_thread(lambda: list(repo.get_issues(state=state)))
        return [{"number": issue.number, "title": issue.title, "state": issue.state} for issue in issues]

    async def close_issue(self, repo_name: str, number: int) -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        issue = await asyncio.to_thread(repo.get_issue, number)
        return await asyncio.to_thread(issue.edit, state="closed")

    async def comment_on_issue(self, repo_name: str, number: int, body: str) -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        issue = await asyncio.to_thread(repo.get_issue, number)
        return await asyncio.to_thread(issue.create_comment, body)

    async def add_labels(self, repo_name: str, number: int, labels: list[str]) -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        issue = await asyncio.to_thread(repo.get_issue, number)
        return await asyncio.to_thread(issue.add_to_labels, *labels)

    async def assign_issue(self, repo_name: str, number: int, assignees: list[str]) -> Any:
        return await self._rest("POST", f"https://api.github.com/repos/{repo_name}/issues/{number}/assignees", {"assignees": assignees})

    async def trigger_workflow(self, repo_name: str, workflow_id: str, ref: str = "main", inputs: dict[str, Any] | None = None) -> Any:
        return await self._rest(
            "POST",
            f"https://api.github.com/repos/{repo_name}/actions/workflows/{workflow_id}/dispatches",
            {"ref": ref, "inputs": inputs or {}},
        )

    async def get_workflow_runs(self, repo_name: str) -> Any:
        return await self._rest("GET", f"https://api.github.com/repos/{repo_name}/actions/runs")

    async def get_run_logs(self, repo_name: str, run_id: int) -> Any:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        async with self.session.get(f"https://api.github.com/repos/{repo_name}/actions/runs/{run_id}/logs", headers=self._headers()) as response:
            return {"status": response.status, "location": response.headers.get("Location")}

    async def cancel_run(self, repo_name: str, run_id: int) -> Any:
        return await self._rest("POST", f"https://api.github.com/repos/{repo_name}/actions/runs/{run_id}/cancel")

    async def create_release(self, repo_name: str, tag_name: str, name: str, body: str = "") -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        release = await asyncio.to_thread(repo.create_git_release, tag_name, name, body)
        return {"id": release.id, "url": release.html_url}

    async def list_releases(self, repo_name: str) -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        releases = await asyncio.to_thread(lambda: list(repo.get_releases()))
        return [{"id": rel.id, "tag_name": rel.tag_name, "url": rel.html_url} for rel in releases]

    async def upload_release_asset(self, repo_name: str, release_id: int, asset_path: str) -> Any:
        repo = await asyncio.to_thread(self.client.get_repo, repo_name)
        release = await asyncio.to_thread(repo.get_release, release_id)
        return await asyncio.to_thread(release.upload_asset, asset_path)

    async def create_gist(self, description: str, files: dict[str, str], public: bool = False) -> Any:
        payload = {"description": description, "public": public, "files": {name: {"content": content} for name, content in files.items()}}
        return await self._rest("POST", "https://api.github.com/gists", payload)

    async def list_gists(self) -> Any:
        return await self._rest("GET", "https://api.github.com/gists")

    async def search_code(self, query: str) -> Any:
        return await self._rest("GET", f"https://api.github.com/search/code?q={query}")

    async def search_issues(self, query: str) -> Any:
        return await self._rest("GET", f"https://api.github.com/search/issues?q={query}")

    async def search_repos(self, query: str) -> Any:
        return await self._rest("GET", f"https://api.github.com/search/repositories?q={query}")

    async def register_webhook(self, repo_name: str, callback_url: str, events: list[str] | None = None) -> Any:
        return await self._rest(
            "POST",
            f"https://api.github.com/repos/{repo_name}/hooks",
            {
                "name": "web",
                "active": True,
                "events": events or ["push", "pull_request"],
                "config": {"url": callback_url, "content_type": "json"},
            },
        )
