from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class CanvasStore:
    path: Path

    def __post_init__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _default(self) -> Dict[str, Any]:
        return {
            "updated_at": "",
            "cards": [],
            "events": [],
        }

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = self._default()
                merged.update(data)
                return merged
        except Exception:
            pass
        return self._default()

    def save(self, state: Dict[str, Any]):
        state["updated_at"] = datetime.now().isoformat()
        self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def present(self, content: str, title: str = "Canvas Card", kind: str = "note") -> Dict[str, Any]:
        state = self.load()
        cards: List[Dict[str, Any]] = state.setdefault("cards", [])
        card = {
            "id": f"card_{len(cards) + 1}",
            "title": title,
            "kind": kind,
            "content": content,
            "created_at": datetime.now().isoformat(),
        }
        cards.append(card)
        state.setdefault("events", []).append({"type": "present", "card_id": card["id"], "ts": datetime.now().isoformat()})
        self.save(state)
        return card

    def evaluate(self, expression: str) -> Dict[str, Any]:
        state = self.load()
        summary = {
            "card_count": len(state.get("cards", [])),
            "event_count": len(state.get("events", [])),
            "updated_at": state.get("updated_at", ""),
        }
        local_vars = {"canvas": state, "summary": summary}
        result = eval(expression, {"__builtins__": {}}, local_vars)
        event = {"type": "eval", "expression": expression, "result": result, "ts": datetime.now().isoformat()}
        state.setdefault("events", []).append(event)
        self.save(state)
        return {"expression": expression, "result": result, "summary": summary}

    def snapshot(self) -> Dict[str, Any]:
        return self.load()
