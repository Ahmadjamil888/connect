from __future__ import annotations

import time
from typing import Any

from core.ai_tool_driver import ai_tool
from core.browser_driver import browser
from core.events import event_bus
from core.social_driver import social

_EVENT_BUS = None
_ROUTE_HANDLER = None


def bind_event_bus(event_bus) -> None:
    global _EVENT_BUS
    _EVENT_BUS = event_bus
    try:
        from core.events import event_bus as event_bus_proxy

        event_bus_proxy.bind(event_bus)
    except Exception:
        pass


def bind_route_handler(handler) -> None:
    global _ROUTE_HANDLER
    _ROUTE_HANDLER = handler


class RuntimeSession:
    def __init__(self):
        self.active_tool = None
        self.active_url = None
        self.active_project = None
        self.current_operation = None
        self.operations: list[dict[str, Any]] = []
        self.browser = browser
        self.ai_tool = ai_tool
        self.social = social

    def update_state(self, **changes: Any) -> None:
        for key, value in changes.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def log_operation(self, op_type: str, details: dict[str, Any], status: str = "running") -> dict[str, Any]:
        entry = {
            "type": op_type,
            "details": details,
            "status": status,
            "timestamp": time.time(),
        }
        self.current_operation = entry if status == "running" else None
        self.operations.append(entry)
        self.operations = self.operations[-200:]
        if _EVENT_BUS is not None:
            try:
                _EVENT_BUS.publish("operation", entry=entry, operations=self.operations[-20:])
            except Exception:
                pass
        return entry

    def complete_operation(self, op_type: str, details: dict[str, Any]) -> dict[str, Any]:
        return self.log_operation(op_type, details, status="completed")

    def runtime_state(self) -> dict[str, Any]:
        return {
            "active_tool": self.active_tool,
            "active_url": self.active_url,
            "active_project": self.active_project,
            "current_operation": self.current_operation,
            "operations": self.operations[-20:],
        }

    def execute(self, instruction: str) -> dict[str, Any]:
        if _ROUTE_HANDLER is None:
            result = {"ok": False, "error": "Route handler not bound"}
            self.log_operation("execute", {"instruction": instruction, "result": result}, status="failed")
            return result
        self.log_operation("execute", {"instruction": instruction})
        result = _ROUTE_HANDLER(instruction)
        payload = result if isinstance(result, dict) else {"result": result}
        self.complete_operation("execute", {"instruction": instruction, "result": payload})
        return payload


runtime_session = RuntimeSession()
