from __future__ import annotations

import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ModuleNotFoundError:
    FileSystemEventHandler = object  # type: ignore[assignment]
    Observer = None  # type: ignore[assignment]

from imos.adapters.base import IMOSAdapter
from imos.models import IMOSResult, IMOSTask


class IDEEventHandler(FileSystemEventHandler):
    def __init__(self, sink: list[dict[str, Any]]) -> None:
        self.sink = sink

    def on_any_event(self, event) -> None:
        self.sink.append({"event_type": event.event_type, "src_path": event.src_path, "is_directory": event.is_directory})


class BaseIDEAdapter(IMOSAdapter):
    def __init__(self, name: str, config: dict[str, Any] | None = None, capabilities: list[str] | None = None) -> None:
        super().__init__(
            name=name,
            adapter_type="ide",
            capabilities=capabilities
            or [
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
            ],
            config=config,
        )
        self.workspace = Path((config or {}).get("workspace") or Path.cwd()).resolve()
        self.current_file: str | None = None
        self.open_files: list[str] = []
        self._watch_events: list[dict[str, Any]] = []
        self._observer: Observer | None = None

    async def connect(self) -> bool:
        self.workspace.mkdir(parents=True, exist_ok=True)
        if self._observer is None and Observer is not None:
            handler = IDEEventHandler(self._watch_events)
            self._observer = Observer()
            self._observer.schedule(handler, str(self.workspace), recursive=True)
            self._observer.start()
        self.status = "connected"
        return True

    async def disconnect(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None
        self.status = "disconnected"

    async def health_check(self) -> bool:
        return self.workspace.exists()

    async def get_capabilities(self) -> list[str]:
        return list(self.capabilities)

    async def send(self, task: IMOSTask) -> IMOSResult:
        started = time.perf_counter()
        action = str(task.metadata.get("action") or task.subtask_type or "").lower()
        try:
            if action in {"delegate_prompt", "question_answer", "code_generation", "code_editing", "multi_step", "chat", ""}:
                prompt = str(task.metadata.get("params", {}).get("prompt") or task.prompt)
                output = await self.delegate_prompt(task.task_id, prompt, metadata=task.metadata)
            elif action in {"write_file", "create_file"}:
                output = await self.write_file(task.metadata["path"], task.metadata.get("content", task.prompt))
            elif action == "read_file":
                output = await self.read_file(task.metadata["path"])
            elif action == "delete_file":
                output = await self.delete_file(task.metadata["path"])
            elif action in {"run_terminal", "shell_command", "run_shell"}:
                output = await self.run_terminal(task.metadata.get("command", task.prompt), cwd=task.metadata.get("cwd"))
            elif action == "open_file":
                output = await self.open_file(task.metadata["path"], line=task.metadata.get("line"))
            elif action == "apply_diff":
                output = await self.apply_diff(task.metadata["path"], task.metadata.get("diff", ""), task.metadata.get("content"))
            elif action == "get_open_files":
                output = await self.get_open_files()
            elif action == "get_project_tree":
                output = await self.get_project_tree(task.metadata.get("path"))
            elif action == "get_current_file_content":
                output = await self.get_current_file_content()
            else:
                raise ValueError(f"Unsupported IDE action: {action or '(none)'}")
            success = not (isinstance(output, dict) and output.get("returncode") not in {None, 0})
            error = None
            if not success and isinstance(output, dict):
                error = str(output.get("stderr") or output.get("stdout") or f"Command failed with return code {output.get('returncode')}")
            return IMOSResult(
                task.task_id,
                self.name,
                success,
                output=output,
                error=error,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            self.status = "error"
            return IMOSResult(task.task_id, self.name, False, output=None, error=str(exc), duration_ms=int((time.perf_counter() - started) * 1000))

    async def delegate_prompt(self, task_id: str, prompt: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        inbox = self.workspace / ".imos" / "delegated_tasks" / self.name
        inbox.mkdir(parents=True, exist_ok=True)
        target = inbox / f"{task_id}.json"
        payload = {
            "task_id": task_id,
            "adapter": self.name,
            "workspace": str(self.workspace),
            "prompt": prompt,
            "metadata": metadata or {},
        }
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {
            "delegated": True,
            "adapter": self.name,
            "inbox_path": str(target),
            "workspace": str(self.workspace),
        }

    async def write_file(self, path: str, content: str) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.current_file = str(target)
        if str(target) not in self.open_files:
            self.open_files.append(str(target))
        return f"Wrote {target}"

    async def read_file(self, path: str) -> str:
        target = self._resolve(path)
        self.current_file = str(target)
        if str(target) not in self.open_files:
            self.open_files.append(str(target))
        return target.read_text(encoding="utf-8", errors="replace")

    async def delete_file(self, path: str) -> str:
        target = self._resolve(path)
        if target.exists():
            target.unlink()
        self.open_files = [item for item in self.open_files if item != str(target)]
        return f"Deleted {target}"

    async def run_terminal(self, command: str, cwd: str | None = None) -> dict[str, Any]:
        target_cwd = Path(cwd).resolve() if cwd else self.workspace
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(target_cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return {
            "command": command,
            "cwd": str(target_cwd),
            "returncode": process.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }

    async def open_file(self, path: str, line: int | None = None) -> str:
        target = self._resolve(path)
        self.current_file = str(target)
        if str(target) not in self.open_files:
            self.open_files.append(str(target))
        return f"Opened {target}" + (f":{line}" if line else "")

    async def apply_diff(self, path: str, diff: str, content: str | None = None) -> str:
        target = self._resolve(path)
        original = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
        if content is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"Applied full-content patch to {target}"
        if not diff:
            return f"No diff supplied for {target}"
        patched = self._apply_simple_diff(original, diff)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(patched, encoding="utf-8")
        return f"Applied diff to {target}"

    async def get_open_files(self) -> list[str]:
        return list(self.open_files)

    async def get_project_tree(self, path: str | None = None) -> list[dict[str, Any]]:
        base = self._resolve(path or ".")
        items: list[dict[str, Any]] = []
        for item in sorted(base.rglob("*")):
            if ".git" in item.parts:
                continue
            items.append({"path": str(item), "type": "directory" if item.is_dir() else "file"})
            if len(items) >= 500:
                break
        return items

    async def get_current_file_content(self) -> str:
        if not self.current_file:
            return ""
        return Path(self.current_file).read_text(encoding="utf-8", errors="replace")

    def _resolve(self, path: str) -> Path:
        candidate = Path(path)
        return candidate.resolve() if candidate.is_absolute() else (self.workspace / candidate).resolve()

    def _apply_simple_diff(self, original: str, diff: str) -> str:
        if "@@" not in diff:
            return diff
        kept: list[str] = []
        for line in diff.splitlines():
            if line.startswith(("---", "+++", "@@")):
                continue
            if line.startswith("+"):
                kept.append(line[1:])
            elif line.startswith(" "):
                kept.append(line[1:])
            elif line.startswith("-"):
                continue
        return "\n".join(kept) + ("\n" if diff.endswith("\n") else "")


class MCPServerBase(BaseIDEAdapter):
    def __init__(self, name: str, config: dict[str, Any] | None = None, mcp_config_path: Path | None = None) -> None:
        super().__init__(name=name, config=config)
        self.mcp_config_path = mcp_config_path

    async def connect(self) -> bool:
        await super().connect()
        if self.mcp_config_path:
            self.mcp_config_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "imos": {
                    "command": "python",
                    "args": ["-m", "imos.mcp_server"],
                }
            }
            serialized = json.dumps(payload, indent=2)
            try:
                existing = self.mcp_config_path.read_text(encoding="utf-8") if self.mcp_config_path.exists() else None
                if existing != serialized:
                    self.mcp_config_path.write_text(serialized, encoding="utf-8")
            except PermissionError:
                if not self.mcp_config_path.exists():
                    raise
        return True


def cli_available(command: str) -> bool:
    return subprocess.call(["where", command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False) == 0
