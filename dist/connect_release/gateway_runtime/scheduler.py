from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional


def parse_schedule_interval(schedule: str) -> Optional[int]:
    value = (schedule or "").strip().lower()
    if not value:
        return None
    if value == "@hourly":
        return 3600
    if value == "@daily":
        return 86400
    match = re.fullmatch(r"@every\s+(\d+)([smhd])", value)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        scale = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
        return amount * scale
    # Simple cron-like support: "*/5 * * * *" => every 5 minutes
    match = re.fullmatch(r"\*/(\d+)\s+\*\s+\*\s+\*\s+\*", value)
    if match:
        return int(match.group(1)) * 60
    return None


class CronScheduler:
    def __init__(self, load_jobs: Callable[[], List[Dict[str, Any]]], save_jobs: Callable[[List[Dict[str, Any]]], None], submit_job: Callable[[str, Dict[str, Any]], Any]):
        self.load_jobs = load_jobs
        self.save_jobs = save_jobs
        self.submit_job = submit_job
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, name="cron-scheduler", daemon=True)

    def start(self):
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run_loop(self):
        while not self._stop.is_set():
            try:
                jobs = self.load_jobs()
                changed = False
                now = datetime.now()
                for job in jobs:
                    interval = parse_schedule_interval(str(job.get("schedule", "")))
                    if not interval:
                        continue
                    last_run = job.get("last_run", "")
                    next_run = job.get("next_run", "")
                    if not next_run:
                        job["next_run"] = (now + timedelta(seconds=interval)).isoformat()
                        changed = True
                        continue
                    try:
                        next_dt = datetime.fromisoformat(next_run)
                    except Exception:
                        job["next_run"] = (now + timedelta(seconds=interval)).isoformat()
                        changed = True
                        continue
                    if now >= next_dt:
                        self.submit_job(
                            "run_prompt",
                            {
                                "session_id": job.get("session_id", ""),
                                "text": job.get("prompt", ""),
                                "source": "cron",
                                "cron_name": job.get("name", ""),
                            },
                        )
                        job["last_run"] = now.isoformat()
                        job["next_run"] = (now + timedelta(seconds=interval)).isoformat()
                        changed = True
                    elif not last_run:
                        job["last_run"] = ""
                if changed:
                    self.save_jobs(jobs)
            except Exception:
                pass
            time.sleep(1.0)
