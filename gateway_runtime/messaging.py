from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import requests


@dataclass
class TelegramConnector:
    token: str
    on_message: Callable[[Dict[str, Any]], None]
    polling_interval: float = 1.5

    def __post_init__(self):
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self._offset = 0
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="telegram-poll", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def send_message(self, chat_id: str, content: str) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": chat_id, "text": content},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def _poll_loop(self):
        while not self._stop.is_set():
            try:
                response = requests.get(
                    f"{self.base_url}/getUpdates",
                    params={"timeout": 20, "offset": self._offset},
                    timeout=25,
                )
                response.raise_for_status()
                payload = response.json()
                for update in payload.get("result", []):
                    self._offset = max(self._offset, int(update.get("update_id", 0)) + 1)
                    message = update.get("message") or update.get("edited_message")
                    if not message:
                        continue
                    text = str(message.get("text", "")).strip()
                    if not text:
                        continue
                    self.on_message(
                        {
                            "connector": "telegram",
                            "chat_id": str(message.get("chat", {}).get("id", "")),
                            "user_id": str(message.get("from", {}).get("id", "")),
                            "text": text,
                        }
                    )
            except Exception:
                time.sleep(self.polling_interval)


@dataclass
class DiscordWebhookConnector:
    webhook_urls: Dict[str, str]

    def send_message(self, target: str, content: str) -> Dict[str, Any]:
        webhook_url = self.webhook_urls.get(target)
        if not webhook_url:
            raise KeyError(f"discord webhook target not configured: {target}")
        response = requests.post(
            webhook_url,
            json={"content": content},
            timeout=15,
        )
        response.raise_for_status()
        if response.text.strip():
            try:
                return response.json()
            except Exception:
                return {"status_code": response.status_code, "body": response.text[:500]}
        return {"status_code": response.status_code, "ok": True}


@dataclass
class SlackWebhookConnector:
    webhook_urls: Dict[str, str]

    def send_message(self, target: str, content: str) -> Dict[str, Any]:
        webhook_url = self.webhook_urls.get(target)
        if not webhook_url:
            raise KeyError(f"slack webhook target not configured: {target}")
        response = requests.post(
            webhook_url,
            json={"text": content},
            timeout=15,
        )
        response.raise_for_status()
        if response.text.strip():
            return {"status_code": response.status_code, "body": response.text[:500]}
        return {"status_code": response.status_code, "ok": True}


@dataclass
class SlackBotConnector:
    bot_token: str
    signing_secret: str
    on_message: Callable[[Dict[str, Any]], None]

    def send_message(self, channel: str, content: str) -> Dict[str, Any]:
        response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {self.bot_token}"},
            json={"channel": channel, "text": content},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def verify_signature(self, timestamp: str, body: bytes, signature: str) -> bool:
        if not self.signing_secret or not timestamp or not signature:
            return False
        base = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
        digest = "v0=" + hmac.new(self.signing_secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, signature)

    def handle_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if payload.get("type") == "url_verification":
            return {"challenge": payload.get("challenge", "")}
        event = payload.get("event", {}) if isinstance(payload.get("event"), dict) else {}
        if event.get("type") == "message" and not event.get("bot_id"):
            self.on_message(
                {
                    "connector": "slack",
                    "chat_id": str(event.get("channel", "")),
                    "user_id": str(event.get("user", "")),
                    "text": str(event.get("text", "")).strip(),
                }
            )
        return {"ok": True}


@dataclass
class WhatsAppTwilioConnector:
    account_sid: str
    auth_token: str
    from_number: str
    on_message: Callable[[Dict[str, Any]], None]

    def send_message(self, to_number: str, content: str) -> Dict[str, Any]:
        response = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
            data={
                "From": self.from_number,
                "To": to_number,
                "Body": content,
            },
            auth=(self.account_sid, self.auth_token),
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def handle_inbound(self, form: Dict[str, Any]) -> Dict[str, Any]:
        body = str(form.get("Body", "")).strip()
        from_number = str(form.get("From", "")).strip()
        if body and from_number:
            self.on_message(
                {
                    "connector": "whatsapp",
                    "chat_id": from_number,
                    "user_id": from_number,
                    "text": body,
                }
            )
        return {"ok": True, "received": bool(body and from_number)}
