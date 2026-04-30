from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class ConnectMemoryStore:
    root: Path

    def __post_init__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.daily_dir = self.root / "daily"
        self.daily_dir.mkdir(parents=True, exist_ok=True)
        self.curated_path = self.root / "MEMORY.md"
        self.index_path = self.root / "memory.json"
        if not self.curated_path.exists():
            self.curated_path.write_text("# ConnectAI Memory\n\n", encoding="utf-8")
        if not self.index_path.exists():
            self.index_path.write_text("[]", encoding="utf-8")

    def _load_index(self) -> List[Dict[str, Any]]:
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def _save_index(self, rows: List[Dict[str, Any]]):
        self.index_path.write_text(json.dumps(rows[-1000:], indent=2), encoding="utf-8")

    def _daily_path(self, day: datetime | None = None) -> Path:
        day = day or datetime.utcnow()
        return self.daily_dir / f"{day.strftime('%Y-%m-%d')}.md"

    def remember(self, content: str, kind: str = "note", session_id: str = "", metadata: Dict[str, Any] | None = None):
        metadata = metadata or {}
        ts = datetime.utcnow().isoformat()
        entry = {
            "ts": ts,
            "kind": kind,
            "session_id": session_id,
            "content": content,
            "metadata": metadata,
        }
        rows = self._load_index()
        rows.append(entry)
        self._save_index(rows)
        with self._daily_path().open("a", encoding="utf-8") as handle:
            handle.write(f"- {ts} [{kind}] {content}\n")

    def context_blocks(self, session_id: str = "", query: str = "", limit: int = 8) -> List[str]:
        blocks: List[str] = []
        curated = self.curated_path.read_text(encoding="utf-8").strip()
        if curated:
            blocks.append(curated)

        for day in [datetime.utcnow() - timedelta(days=offset) for offset in (0, 1)]:
            path = self._daily_path(day)
            if path.exists():
                blocks.append(path.read_text(encoding="utf-8").strip())

        rows = self._load_index()
        lowered = query.lower().strip()
        filtered = []
        for row in reversed(rows):
            if session_id and row.get("session_id") == session_id:
                filtered.append(row)
                continue
            if lowered and lowered in str(row.get("content", "")).lower():
                filtered.append(row)
        snippets = [f"- [{row['kind']}] {row['content']}" for row in filtered[:limit]]
        if snippets:
            blocks.append("Relevant indexed memory:\n" + "\n".join(snippets))
        return [block for block in blocks if block]

    def recent_entries(self, limit: int = 30) -> List[Dict[str, Any]]:
        return self._load_index()[-limit:]
