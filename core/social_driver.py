from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import quote
from typing import Any

from core.browser_driver import browser
from core.events import event_bus
from core.vision import ask_vision, ask_vision_coordinates
from tools.computer_control import click, open_app, press_key, screenshot, type_text
from tools.whatsapp import send_whatsapp


def _update_runtime(**changes: Any) -> None:
    try:
        from core.runtime_session import runtime_session

        runtime_session.update_state(**changes)
    except Exception:
        pass


class SocialDriver:
    PLATFORMS = {
        "whatsapp": "app",
        "telegram": "app",
        "instagram": "https://www.instagram.com",
        "twitter": "https://www.twitter.com",
        "facebook": "https://www.facebook.com",
        "linkedin": "https://www.linkedin.com",
        "discord": "app",
        "slack": "app",
    }

    def __init__(self):
        self.driver = browser
        self.contacts = self._load_contacts()

    def _load_contacts(self) -> dict[str, dict[str, Any]]:
        path = Path("config/contacts.json")
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, list):
            return {}
        return {
            str(item.get("name", "")).lower(): item
            for item in data
            if isinstance(item, dict) and item.get("name")
        }

    def send_message(self, platform: str, contact: str, message: str) -> dict[str, Any]:
        platform_name = str(platform or "").lower()
        handler = getattr(self, f"_send_{platform_name}", None)
        if handler is None:
            return self._send_generic(contact, message, platform_name)
        _update_runtime(active_tool=platform_name)
        return handler(contact, message)

    def resolve_contact(self, name: str) -> str:
        key = str(name or "").strip().lower()
        contact = self.contacts.get(key)
        if contact:
            return str(contact.get("number") or contact.get("name") or name)
        print(f"  I don't have '{name}' in contacts.")
        identifier = input("  What's their WhatsApp name or number? (I'll remember this): ").strip()
        if identifier:
            self._save_contact(key, identifier)
            return identifier
        return name

    def _save_contact(self, name: str, identifier: str) -> None:
        path = Path("config/contacts.json")
        contacts: list[dict[str, Any]] = []
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    contacts = loaded
            except Exception:
                contacts = []
        existing = [item for item in contacts if str(item.get("name", "")).lower() == name.lower()]
        if existing:
            existing[0]["number"] = identifier
            entry = existing[0]
        else:
            entry = {"name": name, "number": identifier}
            contacts.append(entry)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contacts, indent=2), encoding="utf-8")
        self.contacts[name] = entry
        print(f"  Saved '{name}'  '{identifier}'")

    def _send_whatsapp(self, contact: str, message: str) -> dict[str, Any]:
        result = send_whatsapp(contact, message)
        return {"ok": bool(result.get("success")), "platform": "whatsapp", "contact": contact, "message": message, **result}

    def _send_telegram(self, contact: str, message: str) -> dict[str, Any]:
        result = open_app("telegram")
        if not result.get("ok"):
            self.driver.open_url("https://web.telegram.org")
            time.sleep(5)
        time.sleep(2)
        return self._send_generic(contact, message, "telegram")

    def _send_instagram(self, contact: str, message: str) -> dict[str, Any]:
        self.driver.open_url("https://www.instagram.com/direct/new/")
        time.sleep(3)
        self.driver.find_and_type("To: or search people input", contact)
        time.sleep(1.5)
        shot = screenshot()
        coords = ask_vision_coordinates(
            shot["path"],
            f"Where is '{contact}' in the suggestion list? Return x,y coordinates.",
        ) if shot.get("ok") else None
        if coords:
            click(coords["x"], coords["y"])
            time.sleep(0.5)
            self.driver.find_and_click("Next button")
            time.sleep(1)
        self.driver.find_and_type("message input", message, submit=True)
        return {"ok": True, "platform": "instagram", "contact": contact}

    def _send_generic(self, contact: str, message: str, platform: str = "unknown") -> dict[str, Any]:
        shot = screenshot()
        if not shot.get("ok"):
            return {"ok": False, "error": "Could not capture screen"}
        coords = ask_vision_coordinates(
            shot["path"],
            "Where is the search or new message input? Return x,y coordinates only.",
        )
        if coords:
            click(coords["x"], coords["y"])
            time.sleep(0.3)
            type_text(contact)
            time.sleep(1.5)
        shot = screenshot()
        if shot.get("ok"):
            contact_coords = ask_vision_coordinates(
                shot["path"],
                f"Where is '{contact}' in results? Return x,y coordinates.",
            )
            if contact_coords:
                click(contact_coords["x"], contact_coords["y"])
                time.sleep(1)
        shot = screenshot()
        if not shot.get("ok"):
            return {"ok": False, "error": "Could not capture message entry"}
        input_coords = ask_vision_coordinates(
            shot["path"],
            "Where is the message input field? Return x,y coordinates.",
        )
        if not input_coords:
            return {"ok": False, "error": "Could not complete message flow"}
        click(input_coords["x"], input_coords["y"])
        type_text(message)
        press_key("enter")
        return {"ok": True, "platform": platform, "contact": contact, "message": message}

    def post_content(self, platform: str, text: str, image_path: str | None = None) -> dict[str, Any]:
        platform_name = str(platform or "").lower()
        url = self.PLATFORMS.get(platform_name, "")
        if url.startswith("http"):
            self.driver.open_url(url)
            time.sleep(3)
        result = self.driver.find_and_click("New Post, Compose, Tweet, or Write button")
        if not result.get("ok"):
            return result
        time.sleep(1)
        self.driver.find_and_type("post text input", text)
        if image_path:
            self.driver.find_and_click("attach image or photo button")
        self.driver.find_and_click("Post, Tweet, Share, or Publish button")
        _update_runtime(active_tool=platform_name)
        return {"ok": True, "platform": platform_name, "posted": text[:50]}


social = SocialDriver()
