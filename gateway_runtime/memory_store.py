from __future__ import annotations

import json
import sqlite3
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
        self.db_path = self.root / "memory.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_entries (
                    ts TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_session_ts ON memory_entries(session_id, ts)")

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
        metadata = metadata or {}
        rows = self._load_index()
        entry = {
            "ts": datetime.now().isoformat(),
            "kind": kind,
            "session_id": session_id,
            "content": content,
            "metadata": metadata,
        }
        rows.append(entry)
        self._save_index(rows)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO memory_entries (ts, kind, session_id, content, metadata) VALUES (?, ?, ?, ?, ?)",
                (entry["ts"], kind, session_id, content, json.dumps(metadata, ensure_ascii=True)),
            )
        with self.notes_path.open("a", encoding="utf-8") as handle:
            handle.write(f"- {datetime.now().isoformat()} [{kind}] ({session_id}) {content}\n")

    def search(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        lowered = (query or "").strip().lower()
        if lowered:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT ts, kind, session_id, content, metadata
                    FROM memory_entries
                    WHERE lower(content) LIKE ? OR lower(metadata) LIKE ?
                    ORDER BY ts DESC
                    LIMIT ?
                    """,
                    (f"%{lowered}%", f"%{lowered}%", limit),
                ).fetchall()
            if rows:
                return [
                    {
                        "ts": ts,
                        "kind": kind,
                        "session_id": session_id,
                        "content": content,
                        "metadata": json.loads(metadata or "{}"),
                    }
                    for ts, kind, session_id, content, metadata in rows
                ]
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
        with sqlite3.connect(self.db_path) as conn:
            if session_id:
                rows = conn.execute(
                    """
                    SELECT ts, kind, session_id, content, metadata
                    FROM memory_entries
                    WHERE session_id = ?
                    ORDER BY ts DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT ts, kind, session_id, content, metadata
                    FROM memory_entries
                    ORDER BY ts DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        if rows:
            return list(
                reversed(
                    [
                        {
                            "ts": ts,
                            "kind": kind,
                            "session_id": session_id_value,
                            "content": content,
                            "metadata": json.loads(metadata or "{}"),
                        }
                        for ts, kind, session_id_value, content, metadata in rows
                    ]
                )
            )
        rows = self._load_index()
        if session_id:
            rows = [row for row in rows if row.get("session_id") == session_id]
        return rows[-limit:]
