from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class MemoryStore:
    root: Path

    def __post_init__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "memory_index.json"
        self.notes_path = self.root / "notes.md"

    def _load_index(self) -> List[Dict[str, Any]]:
        if not self.index_path.exists():
            return []
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_index(self, rows: List[Dict[str, Any]]):
        self.index_path.write_text(json.dumps(rows[-500:], indent=2), encoding="utf-8")

    def remember(self, kind: str, session_id: str, content: str, metadata: Dict[str, Any] | None = None):
        rows = self._load_index()
        rows.append(
            {
                "ts": datetime.now().isoformat(),
                "kind": kind,
                "session_id": session_id,
                "content": content,
                "metadata": metadata or {},
            }
        )
        self._save_index(rows)
        with self.notes_path.open("a", encoding="utf-8") as handle:
            handle.write(f"- {datetime.now().isoformat()} [{kind}] ({session_id}) {content}\n")

    def search(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        lowered = (query or "").strip().lower()
        rows = self._load_index()
        if not lowered:
            return rows[-limit:]
        matches = [
            row
            for row in reversed(rows)
            if lowered in str(row.get("content", "")).lower() or lowered in json.dumps(row.get("metadata", {})).lower()
        ]
        return list(reversed(matches[:limit]))

    def get_recent(self, session_id: str = "", limit: int = 10) -> List[Dict[str, Any]]:
        rows = self._load_index()
        if session_id:
            rows = [row for row in rows if row.get("session_id") == session_id]
        return rows[-limit:]
