from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass
class PersistentSession:
    session_id: str
    name: str
    session_key: str
    channel: str
    user_id: str
    title: str = "main"
    status: str = "active"
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    message_count: int = 0
    active_provider: str = ""
    routing_rules: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionManager:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "sessions.json"
        self.active_path = self.root / "active.json"
        self.transcripts_dir = self.root / "transcripts"
        self.exports_dir = self.root / "exports"
        self.tool_audit_dir = self.root / "tool_audit"
        self.snapshots_dir = self.root / "snapshots"
        self.token_usage_dir = self.root / "token_usage"
        for path in [self.transcripts_dir, self.exports_dir, self.tool_audit_dir, self.snapshots_dir, self.token_usage_dir]:
            path.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> dict[str, dict[str, Any]]:
        if not self.index_path.exists():
            return {}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                changed = False
                normalized: dict[str, dict[str, Any]] = {}
                for key, row in data.items():
                    if not isinstance(row, dict):
                        continue
                    fixed = self._normalize_row(key, row)
                    normalized[key] = fixed
                    if fixed != row:
                        changed = True
                if changed:
                    self._save_index(normalized)
                return normalized
        except Exception:
            pass
        return {}

    def _normalize_row(self, key: str, row: dict[str, Any]) -> dict[str, Any]:
        fixed = dict(row)
        session_key = str(fixed.get("session_key") or key).strip() or key
        fixed.setdefault("name", session_key)
        fixed["session_key"] = session_key
        fixed.setdefault("channel", "cli")
        fixed.setdefault("user_id", "local-user")
        fixed.setdefault("title", "main")
        fixed.setdefault("status", "active")
        fixed.setdefault("created_at", _utcnow_iso())
        fixed.setdefault("updated_at", fixed.get("created_at", _utcnow_iso()))
        fixed.setdefault("message_count", 0)
        fixed.setdefault("active_provider", "")
        fixed.setdefault("routing_rules", {})
        fixed.setdefault("metadata", {})
        return fixed

    def _save_index(self, data: dict[str, dict[str, Any]]) -> None:
        self.index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _transcript_path(self, session_id: str) -> Path:
        return self.transcripts_dir / f"{session_id}.jsonl"

    def _tool_audit_path(self, session_id: str) -> Path:
        return self.tool_audit_dir / f"{session_id}.jsonl"

    def _snapshot_path(self, session_id: str) -> Path:
        return self.snapshots_dir / f"{session_id}.json"

    def _token_usage_path(self, session_id: str) -> Path:
        return self.token_usage_dir / f"{session_id}.json"

    def ensure_default(self) -> PersistentSession:
        session = self.get("default")
        if session is None:
            session = self.create("default", channel="cli", user_id="local-user")
        elif not self.active_path.exists():
            self.set_active(session.name)
        return session

    def create(self, name: str, *, channel: str = "cli", user_id: str = "local-user", title: str = "main") -> PersistentSession:
        key = name.strip() or "default"
        existing = self.get(key)
        if existing is not None:
            existing.status = "active"
            self.update(existing)
            self.set_active(existing.name)
            return existing
        session = PersistentSession(
            session_id=uuid.uuid4().hex[:16],
            name=key,
            session_key=key,
            channel=channel,
            user_id=user_id,
            title=title,
        )
        data = self._load_index()
        data[key] = asdict(session)
        self._save_index(data)
        self.set_active(key)
        return session

    def update(self, session: PersistentSession) -> None:
        data = self._load_index()
        session.updated_at = _utcnow_iso()
        data[session.name] = asdict(session)
        self._save_index(data)

    def set_active(self, name: str) -> None:
        data = self._load_index()
        changed = False
        for key, row in data.items():
            desired = "active" if key == name else ("paused" if row.get("status") == "active" else row.get("status", "paused"))
            if row.get("status") != desired:
                row["status"] = desired
                row["updated_at"] = _utcnow_iso()
                changed = True
        if changed:
            self._save_index(data)
        self.active_path.write_text(json.dumps({"name": name, "updated_at": _utcnow_iso()}, indent=2), encoding="utf-8")

    def get_active(self) -> PersistentSession:
        if self.active_path.exists():
            try:
                payload = json.loads(self.active_path.read_text(encoding="utf-8"))
                name = str(payload.get("name", "")).strip()
                if name:
                    session = self.get(name)
                    if session is not None:
                        return session
            except Exception:
                pass
        return self.ensure_default()

    def get(self, name: str) -> PersistentSession | None:
        row = self._load_index().get(name)
        if not row:
            return None
        return PersistentSession(**row)

    def get_by_id(self, session_id: str) -> PersistentSession | None:
        for row in self._load_index().values():
            if row.get("session_id") == session_id:
                return PersistentSession(**row)
        return None

    def list_sessions(self) -> list[PersistentSession]:
        rows = [PersistentSession(**row) for row in self._load_index().values()]
        return sorted(rows, key=lambda item: item.updated_at)

    def get_or_create(self, session_key: str, channel: str, user_id: str, title: str = "main") -> PersistentSession:
        existing = self.get(session_key)
        if existing is not None:
            return existing
        return self.create(session_key, channel=channel, user_id=user_id, title=title)

    def append_message(self, session: PersistentSession, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        payload = {
            "ts": _utcnow_iso(),
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }
        with self._transcript_path(session.session_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        session.message_count += 1
        self.update(session)

    def history(self, session: PersistentSession, limit: int = 20) -> list[dict[str, Any]]:
        path = self._transcript_path(session.session_id)
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows[-limit:]

    def history_by_id(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        session = self.get_by_id(session_id)
        if session is None:
            return []
        return self.history(session, limit=limit)

    def update_status(self, session_name: str, status: str) -> PersistentSession | None:
        session = self.get(session_name)
        if session is None:
            return None
        session.status = status
        self.update(session)
        return session

    def record_memory_snapshot(self, session_id: str, short_term: list[dict[str, Any]], long_term: list[dict[str, Any]]) -> None:
        self._snapshot_path(session_id).write_text(
            json.dumps(
                {
                    "updated_at": _utcnow_iso(),
                    "short_term": short_term,
                    "long_term": long_term,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def record_tool_call(
        self,
        session_id: str,
        *,
        name: str,
        input_summary: str,
        status: str,
        duration: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "ts": _utcnow_iso(),
            "name": name,
            "input_summary": input_summary,
            "status": status,
            "duration": duration,
            "metadata": metadata or {},
        }
        with self._tool_audit_path(session_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def recent_tool_calls(self, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        path = self._tool_audit_path(session_id)
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows[-limit:]

    def set_provider_and_routing(self, session_id: str, active_provider: str, routing_rules: dict[str, str]) -> None:
        session = self.get_by_id(session_id)
        if session is None:
            return
        session.active_provider = active_provider
        session.routing_rules = dict(routing_rules)
        self.update(session)

    def add_token_usage(self, session_id: str, provider: str, input_tokens: int, output_tokens: int) -> None:
        path = self._token_usage_path(session_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            data = {}
        provider_row = data.setdefault(provider, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
        provider_row["input_tokens"] += int(input_tokens or 0)
        provider_row["output_tokens"] += int(output_tokens or 0)
        provider_row["total_tokens"] = provider_row["input_tokens"] + provider_row["output_tokens"]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def token_usage(self, session_id: str) -> dict[str, Any]:
        path = self._token_usage_path(session_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def export_session(self, name: str) -> dict[str, Any]:
        session = self.get(name)
        if session is None:
            raise KeyError(name)
        payload = {
            "session": asdict(session),
            "history": self.history(session, limit=10000),
            "memory_snapshot": json.loads(self._snapshot_path(session.session_id).read_text(encoding="utf-8"))
            if self._snapshot_path(session.session_id).exists()
            else {},
            "tool_calls": self.recent_tool_calls(session.session_id, limit=10000),
            "token_usage": self.token_usage(session.session_id),
        }
        export_path = self.exports_dir / f"{session.name}.json"
        export_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        payload["export_path"] = str(export_path)
        return payload
