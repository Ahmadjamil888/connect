"""Runtime coordination snapshot — memory, routing, policy, audit, execution."""

from __future__ import annotations

from typing import Any, Callable

from core.audit import AuditLogger
from core.context import ContextManager
from core.memory import Memory
from core.policy import Policy
from core.router import RoutingRules
from core.tasks import TaskTracker


def build_runtime_snapshot(
    *,
    memory: Memory,
    policy: Policy,
    tracker: TaskTracker,
    ctx: ContextManager,
    audit: AuditLogger,
    routing: RoutingRules,
    provider: str,
    model: str,
    uptime: str,
    auth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tasks = tracker.all()
    stats = ctx.get_stats()
    mem_data = memory.all()
    rules = routing.list_rules()
    return {
        "provider": provider,
        "model": model,
        "uptime": uptime,
        "auth": auth or {},
        "session": {
            "session_id": stats["session_id"],
            "message_count": stats["message_count"],
            "token_estimate": stats["token_estimate"],
            "providers_used": stats["providers_used"],
            "summary": stats.get("summary", ""),
        },
        "memory": {
            "log_count": len(mem_data.get("log", [])),
            "recent": memory.get_log(12),
            "keys": [k for k in mem_data.keys() if k != "log"],
        },
        "routing": {
            "rules": rules,
            "path": str(routing.path),
        },
        "policy": policy.all(),
        "audit": {
            "count": audit.count(),
            "recent": audit.tail(15),
        },
        "execution": {
            "tasks_total": len(tasks),
            "done": sum(1 for t in tasks if t.get("status") == "done"),
            "running": sum(1 for t in tasks if t.get("status") == "running"),
            "failed": sum(1 for t in tasks if t.get("status") == "failed"),
            "recent": tracker.list_recent(8),
        },
    }
