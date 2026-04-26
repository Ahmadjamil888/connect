from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Session:
    id: str
    name: str
    created_at: str
    updated_at: str
    status: str = "idle"
    profile: str = "coding"
    parent_id: str = ""
    target: str = ""
    messages: List[Dict[str, str]] = field(default_factory=list)


class SessionManager:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"

    def _session_path(self, session_id: str) -> Path:
        return self.root / f"{session_id}.json"

    def _load_index(self) -> List[str]:
        if not self.index_path.exists():
            return []
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_index(self, items: List[str]):
        self.index_path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def _write(self, session: Session):
        self._session_path(session.id).write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")
        index = self._load_index()
        if session.id not in index:
            index.append(session.id)
            self._save_index(index)

    def create(self, name: str = "default", profile: str = "coding", parent_id: str = "", target: str = "") -> Session:
        now = datetime.now().isoformat()
        session = Session(
            id=uuid.uuid4().hex[:12],
            name=name,
            created_at=now,
            updated_at=now,
            status="idle",
            profile=profile,
            parent_id=parent_id,
            target=target,
        )
        self._write(session)
        return session

    def get(self, session_id: str) -> Optional[Session]:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        try:
            return Session(**json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return None

    def require(self, session_id: str) -> Session:
        session = self.get(session_id)
        if not session:
            raise KeyError(f"session not found: {session_id}")
        return session

    def list(self) -> List[Dict[str, str]]:
        rows = []
        for session_id in self._load_index():
            session = self.get(session_id)
            if session:
                rows.append(
                    {
                        "id": session.id,
                        "name": session.name,
                        "status": session.status,
                        "profile": session.profile,
                        "parent_id": session.parent_id,
                        "updated_at": session.updated_at,
                    }
                )
        return rows

    def append_message(self, session_id: str, role: str, content: str):
        session = self.require(session_id)
        session.messages.append({"role": role, "content": content, "ts": datetime.now().isoformat()})
        session.updated_at = datetime.now().isoformat()
        self._write(session)

    def history(self, session_id: str, limit: int = 30) -> List[Dict[str, str]]:
        return self.require(session_id).messages[-limit:]

    def set_status(self, session_id: str, status: str):
        session = self.require(session_id)
        session.status = status
        session.updated_at = datetime.now().isoformat()
        self._write(session)

    def spawn(self, parent_id: str, name: str, profile: str = "coding") -> Session:
        return self.create(name=name, profile=profile, parent_id=parent_id)

    def status(self, session_id: str) -> Dict[str, str]:
        session = self.require(session_id)
        return {
            "id": session.id,
            "name": session.name,
            "status": session.status,
            "profile": session.profile,
            "parent_id": session.parent_id,
            "updated_at": session.updated_at,
            "message_count": str(len(session.messages)),
        }
