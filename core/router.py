from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RoutingRules:
    DEFAULT_RULES = {
        "default": "",
        "code": "",
        "research": "",
        "writing": "",
        "computer_control": "",
        "devops": "",
    }

    KEYWORDS = {
        "code": ("code", "build", "debug", "fix", "refactor"),
        "research": ("search", "find", "research", "scrape"),
        "writing": ("write", "draft", "email", "message"),
        "computer_control": ("click", "type", "open", "screenshot"),
        "devops": ("deploy", "launch", "push"),
    }

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save(dict(self.DEFAULT_RULES))

    def _load(self) -> dict[str, str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = dict(self.DEFAULT_RULES)
                merged.update({str(k): str(v) for k, v in data.items()})
                return merged
        except Exception:
            pass
        return dict(self.DEFAULT_RULES)

    def _save(self, data: dict[str, str]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def infer_task_type(self, prompt: str) -> str:
        lowered = (prompt or "").strip().lower()
        for task_type, keywords in self.KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return task_type
        return "default"

    def set_rule(self, task_type: str, provider: str) -> dict[str, str]:
        rules = self._load()
        rules[task_type] = provider.strip().lower()
        self._save(rules)
        return rules

    def resolve_provider(self, prompt: str, fallback_provider: str) -> tuple[str, str]:
        rules = self._load()
        task_type = self.infer_task_type(prompt)
        provider = rules.get(task_type) or rules.get("default") or fallback_provider
        return task_type, provider or fallback_provider

    def list_rules(self) -> dict[str, str]:
        return self._load()

    def status(self) -> dict[str, Any]:
        rules = self._load()
        return {"path": str(self.path), "rules": rules}
