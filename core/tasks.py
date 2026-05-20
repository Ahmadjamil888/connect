import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4


class TaskTracker:
    def __init__(self) -> None:
        self.base_dir = Path.home() / ".imos"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / "tasks.json"
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[dict]:
        try:
            with open(self.path, "r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def _write(self, data: list[dict]) -> None:
        with open(self.path, "w", encoding="utf-8") as file_handle:
            json.dump(data, file_handle, indent=2, ensure_ascii=False)

    def start(self, goal: str, steps_total: int) -> str:
        tasks = self._read()
        task_id = uuid4().hex[:8]
        tasks.append(
            {
                "id": task_id,
                "goal": goal,
                "status": "running",
                "steps_total": steps_total,
                "steps_done": 0,
                "started_at": datetime.now().isoformat(),
                "finished_at": None,
                "log": [],
            }
        )
        self._write(tasks)
        return task_id

    def update(self, task_id: str, step_result: str) -> None:
        tasks = self._read()
        for task in tasks:
            if task["id"] == task_id:
                task["steps_done"] += 1
                task.setdefault("log", []).append(step_result)
                break
        self._write(tasks)

    def finish(self, task_id: str, status: str) -> None:
        tasks = self._read()
        for task in tasks:
            if task["id"] == task_id:
                task["status"] = status
                task["finished_at"] = datetime.now().isoformat()
                break
        self._write(tasks)

    def list_recent(self, n: int = 5) -> list[dict]:
        return self._read()[-n:]

    def get(self, task_id: str):
        for task in self._read():
            if task["id"] == task_id:
                return task
        return None

    def all(self) -> list[dict]:
        return self._read()
