from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from imos.config import IMOS_HOME


class IMOSContextManager:
    def __init__(self) -> None:
        self.path = IMOS_HOME / "context.json"
        if not self.path.parent.exists():
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                self.path = Path.cwd() / ".imos" / "context.json"
                self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"history": [], "project_context": {}, "current_ide": "", "open_repo": ""}

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        except PermissionError:
            self.path = Path.cwd() / ".imos" / "context.json"
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def add_entry(self, prompt: str, results: list[dict[str, Any]], context: dict[str, Any] | None = None) -> None:
        self.state.setdefault("history", []).append({"prompt": prompt, "results": results, "context": context or {}})
        self.state["history"] = self.state["history"][-100:]
        self.save()

    def set_project_context(self, **kwargs) -> None:
        self.state.setdefault("project_context", {}).update(kwargs)
        self.save()

    def recent_history(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.state.get("history", [])[-limit:]
