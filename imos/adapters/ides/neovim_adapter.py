from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from imos.adapters.ides.common import BaseIDEAdapter
from imos.models import IMOSResult, IMOSTask


class NeovimAdapter(BaseIDEAdapter):
    def __init__(self, name: str = "neovim", config: dict[str, Any] | None = None) -> None:
        super().__init__(
            name=name,
            config=config,
            capabilities=[
                "write_file",
                "read_file",
                "create_file",
                "delete_file",
                "run_terminal",
                "open_file",
                "apply_diff",
                "get_open_files",
                "get_project_tree",
                "get_current_file_content",
                "eval_lua",
            ],
        )
        self.nvim = None
        self.socket_path = (config or {}).get("socket_path") or os.getenv("NVIM")

    async def connect(self) -> bool:
        await super().connect()
        try:
            import pynvim
        except ModuleNotFoundError:
            self.status = "error"
            return False
        if self.socket_path:
            self.nvim = await asyncio.to_thread(pynvim.attach, "socket", path=self.socket_path)
            self.status = "connected"
            return True
        self.status = "connected"
        return True

    async def open_file(self, path: str, line: int | None = None) -> str:
        if self.nvim:
            await asyncio.to_thread(self.nvim.command, f"edit {self._resolve(path)}")
            if line:
                await asyncio.to_thread(self.nvim.command, str(line))
        return await super().open_file(path, line)

    async def send(self, task: IMOSTask) -> IMOSResult:
        if (task.metadata.get("action") or task.subtask_type) == "eval_lua":
            started = time.perf_counter()
            try:
                result = await asyncio.to_thread(self.nvim.exec_lua, task.metadata.get("code", task.prompt)) if self.nvim else ""
                return IMOSResult(task.task_id, self.name, True, output=result, duration_ms=int((time.perf_counter() - started) * 1000))
            except Exception as exc:
                return IMOSResult(task.task_id, self.name, False, error=str(exc), duration_ms=int((time.perf_counter() - started) * 1000))
        return await super().send(task)
