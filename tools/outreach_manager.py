from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tools.email_manager import send_email

CAMPAIGN_PATH = Path(__file__).resolve().parents[1] / "data" / "outreach_campaigns.json"


def _ensure_store() -> None:
    CAMPAIGN_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CAMPAIGN_PATH.exists():
        CAMPAIGN_PATH.write_text("[]", encoding="utf-8")


def _load() -> list[dict[str, Any]]:
    _ensure_store()
    try:
        data = json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save(rows: list[dict[str, Any]]) -> None:
    _ensure_store()
    CAMPAIGN_PATH.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def list_campaigns() -> list[dict[str, Any]]:
    return _load()


def save_campaign(payload: dict[str, Any]) -> dict[str, Any]:
    rows = _load()
    campaign_id = str(payload.get("id", "")).strip() or f"campaign-{int(time.time())}"
    leads = payload.get("leads") or []
    if isinstance(leads, str):
        parsed: list[dict[str, Any]] = []
        for line in leads.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [item.strip() for item in line.split("|")]
            parsed.append(
                {
                    "name": parts[0] if len(parts) > 0 else "",
                    "email": parts[1] if len(parts) > 1 else "",
                    "company": parts[2] if len(parts) > 2 else "",
                    "notes": parts[3] if len(parts) > 3 else "",
                    "status": "pending",
                }
            )
        leads = parsed
    record = {
        "id": campaign_id,
        "name": str(payload.get("name", "")).strip() or campaign_id,
        "channel": str(payload.get("channel", "email")).strip() or "email",
        "subject_template": str(payload.get("subject_template", "")).strip(),
        "body_template": str(payload.get("body_template", "")).strip(),
        "leads": leads if isinstance(leads, list) else [],
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    rows = [item for item in rows if str(item.get("id")) != campaign_id]
    rows.append(record)
    _save(rows)
    return record


def _render(template: str, lead: dict[str, Any]) -> str:
    output = str(template or "")
    for key, value in lead.items():
        output = output.replace("{{" + str(key) + "}}", str(value or ""))
    return output


def run_campaign(campaign_id: str, *, limit: int | None = None, dry_run: bool = False) -> dict[str, Any]:
    rows = _load()
    campaign = next((item for item in rows if str(item.get("id")) == str(campaign_id)), None)
    if campaign is None:
        return {"ok": False, "error": f"Campaign not found: {campaign_id}"}
    sent = 0
    processed: list[dict[str, Any]] = []
    for lead in campaign.get("leads", []):
        if limit is not None and sent >= limit:
            break
        lead = dict(lead)
        subject = _render(campaign.get("subject_template", ""), lead)
        body = _render(campaign.get("body_template", ""), lead)
        if dry_run:
            lead["status"] = "preview"
            lead["last_result"] = {"subject": subject, "body": body}
        else:
            if campaign.get("channel") != "email":
                lead["status"] = "unsupported"
                lead["last_result"] = f"Unsupported channel: {campaign.get('channel')}"
            elif not str(lead.get("email", "")).strip():
                lead["status"] = "failed"
                lead["last_result"] = "Missing email address"
            else:
                try:
                    lead["last_result"] = send_email(str(lead.get("email")), subject, body)
                    lead["status"] = "sent" if "sent" in str(lead["last_result"]).lower() else "failed"
                except Exception as exc:
                    lead["status"] = "failed"
                    lead["last_result"] = str(exc)
        lead["last_attempt_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        processed.append(lead)
        sent += 1
    campaign["leads"] = processed + campaign.get("leads", [])[len(processed):]
    campaign["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save(rows)
    return {
        "ok": True,
        "campaign": campaign,
        "processed": processed,
        "sent_count": len([lead for lead in processed if lead.get("status") == "sent"]),
        "preview_count": len([lead for lead in processed if lead.get("status") == "preview"]),
    }
