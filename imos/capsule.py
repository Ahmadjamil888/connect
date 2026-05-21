from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from imos.config import IMOS_HOME


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "").strip().lower())
    cleaned = cleaned.strip("-_")
    return cleaned or "session"


def capsule_export_dir() -> Path:
    path = IMOS_HOME / "capsules"
    path.mkdir(parents=True, exist_ok=True)
    return path


def handoff_export_dir() -> Path:
    path = IMOS_HOME / "handoffs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_capsule_path(session_name: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d")
    return capsule_export_dir() / f"{_safe_name(session_name)}-{stamp}.imos"


def read_capsule(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_capsule(payload: dict[str, Any], path: str | Path | None = None) -> Path:
    target = Path(path) if path else default_capsule_path(str(payload.get("session", {}).get("name", "session")))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def _collect_workspace_map(root: Path, limit: int = 200) -> dict[str, Any]:
    if not root.exists():
        return {"rootPath": str(root), "exists": False, "files": []}
    files: list[str] = []
    for path in sorted(root.rglob("*")):
        if ".git" in path.parts or ".imos" in path.parts or "__pycache__" in path.parts:
            continue
        if path.is_file():
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                rel = str(path)
            files.append(rel)
        if len(files) >= limit:
            break
    return {"rootPath": str(root), "exists": True, "files": files}


def build_capsule(
    session: dict[str, Any],
    history: list[dict[str, Any]],
    *,
    workspace: str | None = None,
    context_history: list[dict[str, Any]] | None = None,
    source: str = "imos",
) -> dict[str, Any]:
    workspace_root = Path(workspace).resolve() if workspace else Path.cwd()
    project_name = workspace_root.name or "project"
    latest_prompt = next((item.get("content", "") for item in reversed(history) if item.get("role") == "user"), "")
    latest_response = next((item.get("content", "") for item in reversed(history) if item.get("role") == "assistant"), "")
    adapter_names: list[str] = []
    decisions: list[dict[str, Any]] = []
    for row in context_history or []:
        context = row.get("context", {}) if isinstance(row, dict) else {}
        targets = context.get("target_adapters", []) if isinstance(context, dict) else []
        for item in targets:
            if item and item not in adapter_names:
                adapter_names.append(str(item))
        if row.get("prompt"):
            decisions.append(
                {
                    "choice": str(row.get("prompt", ""))[:120],
                    "reason": "Captured from IMOS session history",
                    "madeBy": "imos",
                    "session": session.get("id", ""),
                }
            )
    return {
        "version": "1.0",
        "created": _utc_now(),
        "source": source,
        "project": {
            "name": project_name,
            "rootPath": str(workspace_root),
            "workspace": _collect_workspace_map(workspace_root),
        },
        "session": {
            "id": session.get("id", ""),
            "name": session.get("name", "default"),
            "status": session.get("status", "idle"),
            "profile": session.get("profile", "imos"),
        },
        "goal": latest_prompt,
        "latest_response": latest_response,
        "decisions": decisions[-20:],
        "models_used": adapter_names,
        "messages": history[-50:],
        "context_history": (context_history or [])[-20:],
        "tests": {},
        "connectors": {},
        "audit": [],
    }


def handoff_payload(capsule: dict[str, Any], target: str) -> dict[str, Any]:
    project = capsule.get("project", {}) if isinstance(capsule, dict) else {}
    session = capsule.get("session", {}) if isinstance(capsule, dict) else {}
    return {
        "target": target,
        "sent_at": _utc_now(),
        "project": project,
        "session": session,
        "goal": capsule.get("goal", ""),
        "latest_response": capsule.get("latest_response", ""),
        "messages": capsule.get("messages", [])[-20:],
        "instructions": f"Continue this IMOS handoff in {target} without restarting scope.",
    }


def write_handoff(capsule: dict[str, Any], target: str, workspace: str | Path | None = None) -> Path:
    base = Path(workspace).resolve() if workspace else Path.cwd()
    folder = base / ".imos" / "handoffs" / _safe_name(target)
    folder.mkdir(parents=True, exist_ok=True)
    session_name = _safe_name(str(capsule.get("session", {}).get("name", "session")))
    path = folder / f"{session_name}.json"
    path.write_text(json.dumps(handoff_payload(capsule, target), indent=2), encoding="utf-8")
    return path
