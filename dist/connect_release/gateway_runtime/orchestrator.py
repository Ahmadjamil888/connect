from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class Orchestrator:
    path: Path
    handler: Any

    def __post_init__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, name="runtime-orchestrator", daemon=True)

    def start(self):
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self):
        self._stop.set()
        self._queue.put({"type": "stop"})
        if self._thread.is_alive():
            self._thread.join(timeout=2)

    def _load(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, jobs: List[Dict[str, Any]]):
        self.path.write_text(json.dumps(jobs[-500:], indent=2), encoding="utf-8")

    def submit(self, job_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        job = {
            "job_id": f"job_{int(time.time() * 1000)}_{len(self._load())}",
            "type": job_type,
            "payload": payload,
            "status": "queued",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "result": None,
        }
        jobs = self._load()
        jobs.append(job)
        self._save(jobs)
        self._queue.put(job)
        return job

    def jobs(self) -> List[Dict[str, Any]]:
        return self._load()

    def _run_loop(self):
        while not self._stop.is_set():
            job = self._queue.get()
            if job.get("type") == "stop":
                return
            jobs = self._load()
            current = next((item for item in jobs if item["job_id"] == job["job_id"]), None)
            if not current:
                continue
            current["status"] = "running"
            current["updated_at"] = datetime.now().isoformat()
            self._save(jobs)
            try:
                result = self.handler(job["type"], job.get("payload", {}))
                current["status"] = "completed"
                current["result"] = result
            except Exception as exc:
                current["status"] = "failed"
                current["result"] = str(exc)
            current["updated_at"] = datetime.now().isoformat()
            self._save(jobs)
