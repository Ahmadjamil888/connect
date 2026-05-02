from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from imos.adapters.vcs.common import BaseVCSAdapter


class GitlabAdapter(BaseVCSAdapter):
    def __init__(self, name: str = "gitlab", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["repo", "files", "commits", "branches", "pull_requests", "issues", "search"])
        self.url = (config or {}).get("GITLAB_URL", "https://gitlab.com")
        self.token = (config or {}).get("GITLAB_TOKEN", "")
        self.client = None

    async def connect(self) -> bool:
        await super().connect()
        try:
            import gitlab
        except ModuleNotFoundError:
            self.status = "error"
            return False
        self.client = gitlab.Gitlab(self.url, private_token=self.token)
        return await self.health_check()

    async def health_check(self) -> bool:
        if self.client is None:
            return False
        try:
            await asyncio.to_thread(self.client.auth)
            self.status = "connected"
            return True
        except Exception:
            self.status = "error"
            return False

    async def create_repo(self, name: str, visibility: str = "private") -> Any:
        return await asyncio.to_thread(self.client.projects.create, {"name": name, "visibility": visibility})

    async def list_repos(self) -> Any:
        return await asyncio.to_thread(lambda: [project.path_with_namespace for project in self.client.projects.list(membership=True)])

    async def get_repo_info(self, project_id: str) -> Any:
        project = await asyncio.to_thread(self.client.projects.get, project_id)
        return {"id": project.id, "name": project.path_with_namespace, "default_branch": project.default_branch}

    async def create_file(self, project_id: str, path: str, content: str, branch: str, message: str) -> Any:
        project = await asyncio.to_thread(self.client.projects.get, project_id)
        return await asyncio.to_thread(project.files.create, {"file_path": path, "branch": branch, "content": content, "commit_message": message})

    async def update_file(self, project_id: str, path: str, content: str, branch: str, message: str) -> Any:
        project = await asyncio.to_thread(self.client.projects.get, project_id)
        file = await asyncio.to_thread(project.files.get, file_path=path, ref=branch)
        file.content = content
        file.branch = branch
        file.commit_message = message
        return await asyncio.to_thread(file.save)

    async def delete_file(self, project_id: str, path: str, branch: str, message: str) -> Any:
        project = await asyncio.to_thread(self.client.projects.get, project_id)
        return await asyncio.to_thread(project.files.delete, file_path=path, branch=branch, commit_message=message)

    async def list_commits(self, project_id: str, ref_name: str = "main") -> Any:
        project = await asyncio.to_thread(self.client.projects.get, project_id)
        return await asyncio.to_thread(lambda: [commit.attributes for commit in project.commits.list(ref_name=ref_name)])

    async def create_branch(self, project_id: str, branch_name: str, ref: str = "main") -> Any:
        project = await asyncio.to_thread(self.client.projects.get, project_id)
        return await asyncio.to_thread(project.branches.create, {"branch": branch_name, "ref": ref})

    async def list_branches(self, project_id: str) -> Any:
        project = await asyncio.to_thread(self.client.projects.get, project_id)
        return await asyncio.to_thread(lambda: [branch.name for branch in project.branches.list()])

    async def merge_branch(self, project_id: str, source_branch: str, target_branch: str, title: str) -> Any:
        project = await asyncio.to_thread(self.client.projects.get, project_id)
        return await asyncio.to_thread(
            project.mergerequests.create,
            {"source_branch": source_branch, "target_branch": target_branch, "title": title},
        )
