from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class SessionRecord:
    session_id: str
    session_key: str
    channel: str
    user_id: str
    title: str = "main"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    message_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConnectSessionManager:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "sessions.json"
        self.transcripts_dir = self.root / "transcripts"
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> Dict[str, Dict[str, Any]]:
        if not self.index_path.exists():
            return {}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _save_index(self, data: Dict[str, Dict[str, Any]]):
        self.index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _transcript_path(self, session_id: str) -> Path:
        return self.transcripts_dir / f"{session_id}.jsonl"

    def get_or_create(self, session_key: str, channel: str, user_id: str, title: str = "main") -> SessionRecord:
        data = self._load_index()
        if session_key in data:
            return SessionRecord(**data[session_key])
        session = SessionRecord(
            session_id=uuid.uuid4().hex[:16],
            session_key=session_key,
            channel=channel,
            user_id=user_id,
            title=title,
        )
        data[session_key] = asdict(session)
        self._save_index(data)
        return session

    def update(self, session: SessionRecord):
        data = self._load_index()
        session.updated_at = datetime.utcnow().isoformat()
        data[session.session_key] = asdict(session)
        self._save_index(data)

    def get_by_id(self, session_id: str) -> Optional[SessionRecord]:
        for row in self._load_index().values():
            if row.get("session_id") == session_id:
                return SessionRecord(**row)
        return None

    def append_message(self, session: SessionRecord, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        payload = {
            "ts": datetime.utcnow().isoformat(),
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }
        with self._transcript_path(session.session_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        session.message_count += 1
        self.update(session)

    def history(self, session: SessionRecord, limit: int = 20) -> List[Dict[str, Any]]:
        path = self._transcript_path(session.session_id)
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows[-limit:]

    def history_by_id(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        session = self.get_by_id(session_id)
        if not session:
            return []
        return self.history(session, limit=limit)

    def list_sessions(self) -> List[SessionRecord]:
        return [SessionRecord(**row) for row in self._load_index().values()]
