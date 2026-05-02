from __future__ import annotations

import asyncio
import time
from typing import Any

from imos.adapters.ides.common import BaseIDEAdapter, cli_available
from imos.models import IMOSResult, IMOSTask


class EmacsAdapter(BaseIDEAdapter):
    def __init__(self, name: str = "emacs", config: dict[str, Any] | None = None) -> None:
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
                "eval_elisp",
            ],
        )

    async def connect(self) -> bool:
        await super().connect()
        self.status = "connected" if cli_available("emacsclient") else "error"
        return self.status == "connected"

    async def open_file(self, path: str, line: int | None = None) -> str:
        if cli_available("emacsclient"):
            process = await asyncio.create_subprocess_exec("emacsclient", "-n", str(self._resolve(path)))
            await process.communicate()
        return await super().open_file(path, line)

    async def send(self, task: IMOSTask) -> IMOSResult:
        action = task.metadata.get("action") or task.subtask_type
        if action == "eval_elisp":
            started = time.perf_counter()
            try:
                process = await asyncio.create_subprocess_exec(
                    "emacsclient",
                    "--eval",
                    task.metadata.get("code", task.prompt),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()
                return IMOSResult(
                    task.task_id,
                    self.name,
                    process.returncode == 0,
                    output=stdout.decode(),
                    error=stderr.decode() or None,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            except Exception as exc:
                return IMOSResult(task.task_id, self.name, False, error=str(exc), duration_ms=int((time.perf_counter() - started) * 1000))
        return await super().send(task)
