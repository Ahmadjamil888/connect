from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _target_instructions(target: str) -> str:
    normalized = str(target or "generic").strip().lower()
    mapping = {
        "chatgpt": "Paste this into ChatGPT as the first message so it can continue the same task context.",
        "openai": "Paste this into an OpenAI chat session as the first message to restore context.",
        "claude": "Paste this into Claude as the first message and continue from the latest action items.",
        "gemini": "Paste this into Gemini as the first message to restore project context.",
        "lovable": "Paste this into the existing Lovable project chat so the build continues from the same requirements.",
        "bolt": "Paste this into the existing Bolt project chat so it continues without resetting scope.",
        "v0": "Paste this into the current v0 chat so it continues the same project.",
        "generic": "Paste this into the target provider to restore the same working context.",
    }
    return mapping.get(normalized, mapping["generic"])


def build_transfer_package(
    session_manager: Any,
    session_identifier: str,
    *,
    target: str = "generic",
    include_memory: bool = True,
) -> dict[str, Any]:
    session = session_manager.get(session_identifier) or session_manager.get_by_id(session_identifier)
    if session is None:
        raise KeyError(session_identifier)
    payload = session_manager.export_session(session.name)
    history = payload.get("history", []) or []
    recent_turns = history[-20:]
    memory_snapshot = payload.get("memory_snapshot", {}) if include_memory else {}
    short_term = memory_snapshot.get("short_term", [])[:10] if isinstance(memory_snapshot, dict) else []
    long_term = memory_snapshot.get("long_term", [])[:10] if isinstance(memory_snapshot, dict) else []
    transcript_lines = []
    for row in recent_turns:
        role = str(row.get("role", "")).strip() or "unknown"
        content = str(row.get("content", "")).strip()
        if content:
            transcript_lines.append(f"{role.upper()}: {content}")
    memory_lines = []
    for row in [*short_term, *long_term]:
        content = str((row or {}).get("content", "")).strip()
        kind = str((row or {}).get("kind", "")).strip()
        if content:
            memory_lines.append(f"- [{kind}] {content}")
    transfer_text = "\n".join(
        [
            f"Context transfer for session: {session.name}",
            f"Active provider: {session.active_provider or 'unknown'}",
            f"Target provider/tool: {target}",
            "",
            _target_instructions(target),
            "",
            "Current objective:",
            "Continue the same project, preserve requirements, and do not restart from scratch.",
            "",
            "Recent conversation:",
            "\n".join(transcript_lines) or "(no transcript available)",
            "",
            "Relevant memory:",
            "\n".join(memory_lines) or "(no memory snapshot available)",
            "",
            "Instructions:",
            "- Continue from the most recent unresolved task.",
            "- Preserve architecture, constraints, and user preferences already established.",
            "- If context is compressed, ask only for the smallest missing detail and otherwise continue execution.",
        ]
    ).strip()
    export_dir = Path(session_manager.exports_dir)
    target_name = str(target or "generic").strip().lower() or "generic"
    transfer_path = export_dir / f"{session.name}.{target_name}.transfer.txt"
    transfer_path.write_text(transfer_text + "\n", encoding="utf-8")
    return {
        "ok": True,
        "session_id": session.session_id,
        "session_name": session.name,
        "target": target_name,
        "transfer_text": transfer_text,
        "transfer_path": str(transfer_path),
        "history_count": len(recent_turns),
    }
