from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ContactBook:
    def __init__(self, state_root: Path):
        self.state_root = state_root
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.path = self.state_root / "contacts.json"

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
            if isinstance(data, list):
                loaded: dict[str, str] = {}
                for item in data:
                    if isinstance(item, dict) and item.get("name"):
                        loaded[str(item["name"])] = str(item.get("number") or item.get("value") or "")
                return loaded
        except Exception:
            pass
        return {}

    def _save(self, data: dict[str, str]) -> None:
        self.path.write_text(json.dumps(dict(sorted(data.items())), indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, name: str, value: str) -> dict[str, Any]:
        data = self._load()
        data[name.strip()] = value.strip()
        self._save(data)
        return {"ok": True, "name": name.strip(), "value": value.strip()}

    def remove(self, name: str) -> dict[str, Any]:
        data = self._load()
        removed = data.pop(name.strip(), None)
        self._save(data)
        return {"ok": removed is not None, "name": name.strip(), "value": removed or ""}

    def list(self) -> dict[str, str]:
        return self._load()

    def count(self) -> int:
        return len(self._load())

    def resolve(self, query: str) -> dict[str, Any]:
        data = self._load()
        exact = data.get(query.strip())
        if exact:
            return {"ok": True, "name": query.strip(), "value": exact, "match": "exact"}
        partial = [(name, value) for name, value in data.items() if query.strip().lower() in name.lower()]
        if len(partial) == 1:
            name, value = partial[0]
            return {"ok": True, "name": name, "value": value, "match": "partial"}
        return {"ok": False, "query": query.strip(), "matches": [name for name, _ in partial]}

    def resolve_contact(self, name: str) -> str:
        resolved = self.resolve(name)
        if resolved.get("ok"):
            return str(resolved.get("value") or name)
        return name
