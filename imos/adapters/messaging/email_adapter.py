from __future__ import annotations

import asyncio
import email
import imaplib
import smtplib
from email.message import EmailMessage
from typing import Any

from imos.adapters.messaging.common import BaseMessagingAdapter


class EmailAdapter(BaseMessagingAdapter):
    def __init__(self, name: str = "email", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.provider = (config or {}).get("EMAIL_PROVIDER", "smtp")
        self.address = (config or {}).get("EMAIL_ADDRESS", "")
        self.password = (config or {}).get("EMAIL_PASSWORD", "")
        self.smtp_server = (config or {}).get("EMAIL_SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int((config or {}).get("EMAIL_SMTP_PORT", 587))
        self.imap_server = (config or {}).get("EMAIL_IMAP_SERVER", "imap.gmail.com")
        self.imap_port = int((config or {}).get("EMAIL_IMAP_PORT", 993))
        self.default_recipient = (config or {}).get("default_recipient", self.address)

    async def health_check(self) -> bool:
        return bool(self.address and self.password)

    async def send_message(self, message: str, channel: str | None = None) -> Any:
        def _send():
            msg = EmailMessage()
            msg["From"] = self.address
            msg["To"] = channel or self.default_recipient
            msg["Subject"] = "[IMOS] Notification"
            msg.set_content(message)
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(self.address, self.password)
                smtp.send_message(msg)
            return {"to": channel or self.default_recipient, "status": "sent"}

        return await asyncio.to_thread(_send)

    async def fetch_messages(self) -> Any:
        def _fetch():
            rows = []
            with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as imap:
                imap.login(self.address, self.password)
                imap.select("INBOX")
                _, data = imap.search(None, 'SUBJECT "[IMOS]"')
                ids = data[0].split()[-20:]
                for message_id in ids:
                    _, raw = imap.fetch(message_id, "(RFC822)")
                    msg = email.message_from_bytes(raw[0][1])
                    rows.append({"id": message_id.decode(), "subject": msg.get("Subject", ""), "from": msg.get("From", "")})
            return rows

        return await asyncio.to_thread(_fetch)
