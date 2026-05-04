from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


CONSENT_VERSION = "1.0"


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass
class ConsentRecord:
    granted: bool
    timestamp: str
    version: str = CONSENT_VERSION


class ConsentManager:
    def __init__(self, state_root: Path):
        self.state_root = state_root
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.path = self.state_root / "consent.json"

    def load(self) -> ConsentRecord | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return ConsentRecord(
                granted=bool(payload.get("granted", False)),
                timestamp=str(payload.get("timestamp", "")),
                version=str(payload.get("version", CONSENT_VERSION)),
            )
        except Exception:
            return None

    def save(self, granted: bool) -> ConsentRecord:
        record = ConsentRecord(granted=granted, timestamp=_utcnow_iso(), version=CONSENT_VERSION)
        self.path.write_text(json.dumps(record.__dict__, indent=2), encoding="utf-8")
        return record

    def status(self) -> dict[str, Any]:
        record = self.load()
        return {
            "granted": bool(record and record.granted),
            "timestamp": record.timestamp if record else "",
            "version": record.version if record else CONSENT_VERSION,
            "path": str(self.path),
        }

    def is_granted(self) -> bool:
        record = self.load()
        return bool(record and record.granted)

    def ensure(self) -> ConsentRecord:
        existing = self.load()
        if existing is not None and existing.granted:
            return existing

        auto = os.getenv("IMOS_AUTO_CONSENT", "").strip().lower()
        if auto in {"agree", "granted", "yes", "true", "1"}:
            return self.save(True)
        if auto in {"decline", "no", "false", "0"}:
            return self.save(False)

        if not sys.stdin or not sys.stdin.isatty():
            return self.save(False)

        print()
        print("IMOS needs your permission to control this computer.")
        print()
        print("This allows IMOS to:")
        print("   Open and control any installed application")
        print("   Send messages via WhatsApp, Telegram, email")
        print("   Create, move, and delete files and folders")
        print("   Execute terminal commands")
        print("   Shut down, restart, sleep the PC")
        print("   Take screenshots to verify actions")
        print("   Type and click on your behalf")
        print()
        print("Type AGREE to grant access, or DECLINE to run in read-only mode.")
        while True:
            answer = input("> ").strip().upper()
            if answer == "AGREE":
                return self.save(True)
            if answer == "DECLINE":
                return self.save(False)
            print("Type AGREE or DECLINE.")

