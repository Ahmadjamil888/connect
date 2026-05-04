from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class ServiceStatusStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def update(self, **fields: Any) -> None:
        data = self.read()
        data.update(fields)
        self.write(data)

    def read(self) -> dict[str, Any]:
        return read_service_status(self.path.parent.parent)


def read_service_status(state_root: Path) -> dict[str, Any]:
    path = state_root / "service" / "status.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"running": False, "tray": False}
