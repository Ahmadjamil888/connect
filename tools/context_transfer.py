from __future__ import annotations

import json
import os
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
        "vscode": "Open VS Code / Copilot and paste this as the first instruction for the workspace.",
        "windsurf": "Paste into Windsurf Cascade to continue the same implementation.",
        "codex": "Paste into Codex CLI or OpenAI Codex with full project context.",
        "cursor": "Paste into Cursor Agent (Composer) as the first message for this repo.",
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


TRANSFER_TARGETS = (
    "cursor",
    "claude",
    "chatgpt",
    "openai",
    "codex",
    "gemini",
    "lovable",
    "bolt",
    "v0",
    "vscode",
    "windsurf",
    "generic",
)


def build_transfer_from_imos_context(ctx: Any, *, target: str = "generic", exports_dir: Path | None = None) -> dict[str, Any]:
    """Build a full context package from IMOS ContextManager (CLI sessions)."""
    target_name = str(target or "generic").strip().lower() or "generic"
    export_root = exports_dir or Path.home() / ".imos" / "exports"
    export_root.mkdir(parents=True, exist_ok=True)
    stats = ctx.get_stats()
    messages = ctx.data.get("messages", [])[-30:]
    transcript_lines = []
    for row in messages:
        role = str(row.get("role", "user")).upper()
        content = str(row.get("content", "")).strip()
        if content:
            transcript_lines.append(f"{role}: {content[:4000]}")
    summary = str(ctx.data.get("summary", "") or "").strip()
    history = ctx.data.get("provider_history") or []
    last_provider = history[-1] if history else {}
    active_model = f"{last_provider.get('provider', '')} / {last_provider.get('model', '')}".strip(" /")
    transfer_text = "\n".join(
        [
            f"IMOS context transfer — session {stats['session_id']}",
            f"Active model: {active_model or 'unknown'}",
            f"Target: {target_name}",
            "",
            _target_instructions(target),
            "",
            "Session summary:",
            summary or "(generate from transcript below)",
            "",
            "Full transcript:",
            "\n".join(transcript_lines) or "(empty)",
            "",
            "Continue this exact project. Do not restart scope.",
        ]
    ).strip()
    transfer_path = export_root / f"{ctx.session_id}.{target_name}.transfer.txt"
    transfer_path.write_text(transfer_text + "\n", encoding="utf-8")
    md_path = export_root / f"{ctx.session_id}.md"
    ctx.export_markdown(md_path)
    return {
        "ok": True,
        "session_id": ctx.session_id,
        "target": target_name,
        "transfer_text": transfer_text,
        "transfer_path": str(transfer_path),
        "markdown_path": str(md_path),
        "message_count": len(messages),
    }


def copy_to_clipboard(text: str) -> bool:
    try:
        if os.name == "nt":
            import subprocess

            proc = subprocess.Popen(
                ["clip"],
                stdin=subprocess.PIPE,
                shell=True,
            )
            proc.communicate(input=text.encode("utf-16le"), timeout=5)
            return proc.returncode == 0
        import subprocess

        proc = subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)
        return proc.returncode == 0
    except Exception:
        return False
