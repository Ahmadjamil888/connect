import email
import imaplib
import os
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Dict, List

from tools.connection_auth import open_connection_signin


def _smtp_config():
    return (
        os.getenv("EMAIL_SMTP_SERVER", "") or os.getenv("EMAIL_SMTP_HOST", ""),
        int(os.getenv("EMAIL_SMTP_PORT", "587")),
        os.getenv("EMAIL_FROM", "") or os.getenv("EMAIL_USERNAME", ""),
        os.getenv("EMAIL_PASSWORD", ""),
    )


def _imap_config():
    return (
        os.getenv("EMAIL_IMAP_SERVER", os.getenv("EMAIL_SMTP_SERVER", "") or os.getenv("EMAIL_SMTP_HOST", "")),
        int(os.getenv("EMAIL_IMAP_PORT", "993")),
        os.getenv("EMAIL_FROM", "") or os.getenv("EMAIL_USERNAME", ""),
        os.getenv("EMAIL_PASSWORD", ""),
    )


def gmail_status() -> Dict[str, str | bool]:
    smtp_server, smtp_port, from_addr, password = _smtp_config()
    imap_server, imap_port, imap_user, imap_password = _imap_config()
    return {
        "ok": bool(smtp_server and smtp_port and from_addr and password and imap_server and imap_user and imap_password),
        "smtp_server": smtp_server,
        "imap_server": imap_server,
        "from": from_addr,
        "smtp_port": smtp_port,
        "imap_port": imap_port,
    }


def send_email(to: str, subject: str, body: str, from_addr: str = None) -> str:
    server, port, default_from, password = _smtp_config()
    sender = from_addr or default_from
    if not all([server, port, sender, password]):
        return "Email configuration missing in .env"
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid()
    msg.set_content(body)
    with smtplib.SMTP(server, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(sender, password)
        smtp.send_message(msg)
    return f"Email sent to {to}"


def _read_messages(count: int, folder: str, criterion: str) -> List[Dict[str, str]]:
    server, port, user, password = _imap_config()
    if not all([server, port, user, password]):
        return [{"error": "Email configuration missing in .env"}]
    rows: List[Dict[str, str]] = []
    with imaplib.IMAP4_SSL(server, port) as imap:
        imap.login(user, password)
        imap.select(folder)
        _, data = imap.search(None, criterion)
        ids = list(reversed(data[0].split()))[:count]
        for email_id in ids:
            _, raw = imap.fetch(email_id, "(RFC822)")
            msg = email.message_from_bytes(raw[0][1])
            rows.append(
                {
                    "id": email_id.decode(),
                    "subject": msg.get("Subject", ""),
                    "from": msg.get("From", ""),
                    "date": msg.get("Date", ""),
                }
            )
    return rows


def read_emails(count: int = 10, folder: str = "INBOX"):
    return _read_messages(count, folder, "ALL")


def search_emails(query: str, folder: str = "INBOX"):
    return _read_messages(20, folder, f'TEXT "{query}"')


def read_email_detail(email_id: str, folder: str = "INBOX") -> Dict[str, str]:
    server, port, user, password = _imap_config()
    if not all([server, port, user, password]):
        return {"error": "Email configuration missing in .env"}
    with imaplib.IMAP4_SSL(server, port) as imap:
        imap.login(user, password)
        imap.select(folder)
        _, raw = imap.fetch(email_id.encode(), "(RFC822)")
        msg = email.message_from_bytes(raw[0][1])
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")
                break
    else:
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        body = payload.decode(charset, errors="replace")
    return {
        "id": email_id,
        "subject": msg.get("Subject", ""),
        "from": msg.get("From", ""),
        "to": msg.get("To", ""),
        "date": msg.get("Date", ""),
        "body": body[:12000],
    }


def reply_to_email(email_id: str, body: str) -> str:
    server, port, user, password = _imap_config()
    smtp_server, smtp_port, smtp_user, smtp_password = _smtp_config()
    if not all([server, port, user, password, smtp_server, smtp_port, smtp_user, smtp_password]):
        return "Email configuration missing in .env"
    with imaplib.IMAP4_SSL(server, port) as imap:
        imap.login(user, password)
        imap.select("INBOX")
        _, raw = imap.fetch(email_id.encode(), "(RFC822)")
        original = email.message_from_bytes(raw[0][1])
    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = email.utils.parseaddr(original.get("Reply-To") or original.get("From"))[1]
    msg["Subject"] = f"Re: {original.get('Subject', '')}"
    if original.get("Message-ID"):
        msg["In-Reply-To"] = original["Message-ID"]
        msg["References"] = original["Message-ID"]
    msg.set_content(body)
    with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)
    return f"Replied to email {email_id}"


def gmail_signin() -> Dict[str, str | bool]:
    return open_connection_signin("gmail")

