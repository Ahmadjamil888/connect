from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass
class EventRecord:
    event_id: int
    event_type: str
    ts: str
    payload: dict[str, Any] = field(default_factory=dict)


class EventBus:
    def __init__(self, root: Path | None = None, limit: int = 1000):
        self.root = root
        self.limit = limit
        self._events: list[EventRecord] = []
        self._subscribers: dict[int, Callable[[EventRecord], None]] = {}
        self._next_event_id = 1
        self._next_subscriber_id = 1
        self._lock = threading.Lock()
        self.path: Path | None = None
        if self.root is not None:
            self.root.mkdir(parents=True, exist_ok=True)
            self.path = self.root / "events.jsonl"

    def publish(self, event_type: str, **payload: Any) -> EventRecord:
        with self._lock:
            event = EventRecord(
                event_id=self._next_event_id,
                event_type=event_type,
                ts=_utcnow_iso(),
                payload=dict(payload),
            )
            self._next_event_id += 1
            self._events.append(event)
            if len(self._events) > self.limit:
                self._events = self._events[-self.limit :]
            if self.path is not None:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
            subscribers = list(self._subscribers.values())
        for callback in subscribers:
            try:
                callback(event)
            except Exception:
                continue
        return event

    def subscribe(self, callback: Callable[[EventRecord], None]) -> int:
        with self._lock:
            token = self._next_subscriber_id
            self._next_subscriber_id += 1
            self._subscribers[token] = callback
            return token

    def unsubscribe(self, token: int) -> None:
        with self._lock:
            self._subscribers.pop(token, None)

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._events[-limit:]
            return [asdict(item) for item in rows]

    def since(self, last_event_id: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            rows = [item for item in self._events if item.event_id > last_event_id]
            return [asdict(item) for item in rows]

    def status(self) -> dict[str, Any]:
        with self._lock:
            last = self._events[-1] if self._events else None
            return {
                "active": True,
                "subscriber_count": len(self._subscribers),
                "event_count": len(self._events),
                "last_event_type": last.event_type if last else "",
                "last_event_ts": last.ts if last else "",
            }

    def tool_start(self, name: str, input_summary: str, **payload: Any) -> EventRecord:
        return self.publish("tool_start", name=name, input_summary=input_summary, **payload)

    def tool_progress(self, name: str, message: str, **payload: Any) -> EventRecord:
        return self.publish("tool_progress", name=name, message=message, **payload)

    def tool_end(self, name: str, status: str, duration: float, **payload: Any) -> EventRecord:
        return self.publish("tool_end", name=name, status=status, duration=duration, **payload)


class _EventBusProxy:
    def __init__(self):
        self._bus = EventBus()

    def bind(self, bus: EventBus) -> None:
        self._bus = bus

    def __getattr__(self, name: str):
        return getattr(self._bus, name)


event_bus = _EventBusProxy()
