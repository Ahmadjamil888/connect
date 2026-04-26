from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class NodePairingStore:
    path: Path

    def __post_init__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _default(self) -> Dict[str, Any]:
        return {"pending_pairs": [], "nodes": []}

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
        self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def create_pairing(self, label: str = "mobile") -> Dict[str, str]:
        state = self.load()
        pairing = {
            "pair_code": secrets.token_hex(4),
            "pair_secret": secrets.token_urlsafe(16),
            "label": label,
            "created_at": datetime.now().isoformat(),
        }
        state.setdefault("pending_pairs", []).append(pairing)
        self.save(state)
        return pairing

    def register_node(self, pair_code: str, pair_secret: str, node_name: str, platform: str) -> Dict[str, Any]:
        state = self.load()
        pending = state.get("pending_pairs", [])
        match = next((item for item in pending if item["pair_code"] == pair_code and item["pair_secret"] == pair_secret), None)
        if not match:
            raise KeyError("invalid pairing credentials")
        pending.remove(match)
        node = {
            "node_id": f"node_{secrets.token_hex(6)}",
            "name": node_name,
            "platform": platform,
            "paired_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "screen": "",
            "camera": "",
            "location": {},
            "notifications": [],
        }
        state.setdefault("nodes", []).append(node)
        self.save(state)
        return node

    def list_nodes(self) -> List[Dict[str, Any]]:
        return self.load().get("nodes", [])

    def _find_node(self, node_id: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
        state = self.load()
        node = next((item for item in state.get("nodes", []) if item["node_id"] == node_id), None)
        if not node:
            raise KeyError(f"node not found: {node_id}")
        node["last_seen"] = datetime.now().isoformat()
        return state, node

    def notify(self, node_id: str, message: str) -> Dict[str, Any]:
        state, node = self._find_node(node_id)
        event = {"message": message, "ts": datetime.now().isoformat()}
        node.setdefault("notifications", []).append(event)
        self.save(state)
        return event

    def update_screen(self, node_id: str, payload: str):
        state, node = self._find_node(node_id)
        node["screen"] = payload
        self.save(state)

    def update_camera(self, node_id: str, payload: str):
        state, node = self._find_node(node_id)
        node["camera"] = payload
        self.save(state)

    def update_location(self, node_id: str, payload: Dict[str, Any]):
        state, node = self._find_node(node_id)
        node["location"] = payload
        self.save(state)

    def screen(self, node_id: str) -> str:
        _, node = self._find_node(node_id)
        return str(node.get("screen", ""))

    def camera(self, node_id: str) -> str:
        _, node = self._find_node(node_id)
        return str(node.get("camera", ""))

    def location(self, node_id: str) -> Dict[str, Any]:
        _, node = self._find_node(node_id)
        return dict(node.get("location", {}))
