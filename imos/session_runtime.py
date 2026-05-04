from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from gateway_runtime.sessions import SessionManager

from imos.config import IMOS_HOME
from imos.models import OrchestratorResult
from imos.orchestrator import IMOSOrchestrator


class IMOSSessionRuntime:
    def __init__(self, orchestrator: IMOSOrchestrator, root: Path | None = None) -> None:
        self.orchestrator = orchestrator
        self.root = self._resolve_root(root)
        self.sessions = SessionManager(self.root)

    def _resolve_root(self, root: Path | None) -> Path:
        candidate = root or (IMOS_HOME / "sessions")
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return candidate
        except PermissionError:
            fallback = Path.cwd() / ".imos" / "sessions"
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    def ensure_session(self, name: str = "default", profile: str = "imos") -> str:
        for row in self.sessions.list():
            if row["name"] == name:
                return row["id"]
        return self.sessions.create(name=name, profile=profile).id

    async def run_turn(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        session_name: str = "default",
        context: dict[str, Any] | None = None,
    ) -> OrchestratorResult:
        session_id = session_id or self.ensure_session(session_name)
        merged_context = dict(context or {})
        merged_context["session_id"] = session_id
        merged_context.setdefault("session_name", session_name)

        self.sessions.append_message(session_id, "user", prompt)
        self.sessions.set_status(session_id, "running")
        try:
            result = await self.orchestrator.run(prompt, context=merged_context)
            self.sessions.append_message(session_id, "assistant", result.final_response)
            self.sessions.set_status(session_id, "idle")
            self._record_delegate_sessions(session_id, prompt, result)
            result.metadata["session"] = self.sessions.status(session_id)
            return result
        except Exception:
            self.sessions.set_status(session_id, "error")
            raise

    def _record_delegate_sessions(self, parent_id: str, prompt: str, result: OrchestratorResult) -> None:
        delegate_ids: list[str] = []
        for item in result.subtask_results:
            child = next(
                (
                    row
                    for row in self.sessions.list()
                    if row["parent_id"] == parent_id and row["name"] == f"{item.adapter_name}_worker"
                ),
                None,
            )
            if child is None:
                created = self.sessions.spawn(parent_id, f"{item.adapter_name}_worker", profile="delegate")
                child_id = created.id
            else:
                child_id = child["id"]
            self.sessions.append_message(child_id, "user", prompt)
            self.sessions.append_message(child_id, "assistant", str(item.output if item.success else item.error or ""))
            self.sessions.set_status(child_id, "idle" if item.success else "error")
            delegate_ids.append(child_id)
        result.metadata["delegate_sessions"] = delegate_ids

    def list_sessions(self) -> list[dict[str, str]]:
        return self.sessions.list()

    def history(self, session_id: str, limit: int = 30) -> list[dict[str, str]]:
        return self.sessions.history(session_id, limit=limit)

    def status(self, session_id: str) -> dict[str, str]:
        return self.sessions.status(session_id)

    def export_session(self, session_id: str) -> dict[str, Any]:
        session = self.sessions.require(session_id)
        payload = asdict(session)
        payload["children"] = [row for row in self.sessions.list() if row.get("parent_id") == session_id]
        return payload
