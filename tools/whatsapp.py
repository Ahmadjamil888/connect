from __future__ import annotations

import os
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote

import pyautogui
import pyperclip

from core.contacts import ContactBook
from core.events import event_bus
from core.voice import VoiceManager
from tools.computer_control import screenshot
from tools.vision import parse_json_response, vision_query

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1


def _voice_manager() -> VoiceManager | None:
    try:
        state_root = Path.cwd() / ".imos" / "voice"
        return VoiceManager(state_root)
    except Exception:
        return None


def _speak(message: str) -> None:
    speaker = _voice_manager()
    if speaker is None:
        return
    try:
        speaker.speak(message)
    except Exception:
        pass


def _vision_json(image_path: str, prompt: str) -> dict | None:
    return parse_json_response(vision_query(image_path, prompt))


def find_whatsapp_desktop() -> str | None:
    paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%APPDATA%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\WhatsApp.exe"),
    ]
    for path in paths:
        if os.path.exists(path):
            return path
    try:
        result = subprocess.run(
            ["cmd", "/c", "start", "", "whatsapp:"],
            capture_output=True,
            timeout=3,
            check=False,
        )
        if result.returncode == 0:
            return "uri:whatsapp:"
    except Exception:
        pass
    return None


def fuzzy_match(query: str, candidates: list) -> str | None:
    if not candidates:
        return None
    lowered_query = query.lower().strip()
    words = lowered_query.split()
    for candidate in candidates:
        if str(candidate).lower() == lowered_query:
            return str(candidate)
    for candidate in candidates:
        lowered_candidate = str(candidate).lower()
        if all(word in lowered_candidate for word in words):
            return str(candidate)
    if words:
        for candidate in candidates:
            if words[0] in str(candidate).lower():
                return str(candidate)
    for candidate in candidates:
        if _levenshtein(lowered_query, str(candidate).lower()) <= 3:
            return str(candidate)
    return None


def _levenshtein(a, b):
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    row = range(len(b) + 1)
    for i, ca in enumerate(a):
        new_row = [i + 1]
        for j, cb in enumerate(b):
            new_row.append(min(row[j + 1] + 1, new_row[j] + 1, row[j] + (ca != cb)))
        row = new_row
    return row[-1]


def try_whatsapp_desktop(app_path, contact_name, message) -> dict:
    event_bus.publish("tool_progress", message="opening WhatsApp...")
    if app_path.startswith("uri:"):
        os.startfile("whatsapp:")  # type: ignore[attr-defined]
    else:
        subprocess.Popen([app_path])
    time.sleep(2.5)

    shot = screenshot()
    if not shot.get("ok"):
        return {"success": False, "error": "screenshot_failed"}
    is_open = _vision_json(
        shot["path"],
        'Is WhatsApp Desktop open and visible? Return JSON only: {"open": true} or {"open": false}',
    ) or {}
    if not is_open.get("open"):
        return {"success": False, "error": "whatsapp_did_not_open"}

    _speak("WhatsApp is open, sir.")
    event_bus.publish("tool_progress", message=f"searching for {contact_name}...")
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.5)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.typewrite(contact_name, interval=0.04)
    time.sleep(1.2)

    shot = screenshot()
    if not shot.get("ok"):
        return {"success": False, "error": "screenshot_failed"}
    contacts = _vision_json(
        shot["path"],
        (
            "List all contact names visible in WhatsApp search results. "
            'Return JSON only: {"contacts": ["name1", "name2"]}'
        ),
    ) or {}
    matched = fuzzy_match(contact_name, contacts.get("contacts", []))

    if not matched:
        first_name = contact_name.split()[0]
        pyautogui.hotkey("ctrl", "a")
        pyautogui.typewrite(first_name, interval=0.04)
        time.sleep(1.2)
        shot = screenshot()
        contacts_retry = _vision_json(
            shot["path"],
            (
                "List contact names in WhatsApp search results. "
                'Return JSON only: {"contacts": ["name1"]}'
            ),
        ) if shot.get("ok") else {}
        matched = fuzzy_match(first_name, (contacts_retry or {}).get("contacts", []))

    if not matched:
        return {"success": False, "error": "contact_not_found"}

    _speak("Found them, sir.")
    event_bus.publish("tool_progress", message=f"found: {matched}")
    shot = screenshot()
    if not shot.get("ok"):
        return {"success": False, "error": "screenshot_failed"}
    coords = _vision_json(
        shot["path"],
        (
            f"Find the contact row for '{matched}' in WhatsApp. "
            'Return JSON only: {"x": N, "y": N}'
        ),
    ) or {}
    if not coords.get("x"):
        return {"success": False, "error": "could_not_locate_contact"}

    event_bus.publish("tool_progress", message="clicking contact...")
    pyautogui.click(coords["x"], coords["y"])
    time.sleep(0.8)
    _speak("Opening the chat, sir.")

    shot = screenshot()
    input_coords = _vision_json(
        shot["path"],
        (
            "Find the message input box at the bottom of WhatsApp chat. "
            'Return JSON only: {"x": N, "y": N}'
        ),
    ) if shot.get("ok") else {}
    if input_coords and input_coords.get("x"):
        pyautogui.click(input_coords["x"], input_coords["y"])
    else:
        pyautogui.hotkey("alt", "tab")

    time.sleep(0.3)
    event_bus.publish("tool_progress", message="sending message...")
    _speak("Sending now, sir.")
    pyperclip.copy(message)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(0.8)

    shot = screenshot()
    sent = _vision_json(
        shot["path"],
        (
            "Is there a newly sent message bubble at the bottom of the WhatsApp chat? "
            'Return JSON only: {"sent": true} or {"sent": false}'
        ),
    ) if shot.get("ok") else {}
    if sent and sent.get("sent"):
        _speak("Sent, sir.")
        return {"success": True, "sent_to": matched, "method": "desktop"}
    return {"success": False, "error": "send_unconfirmed"}


def try_whatsapp_web(contact_name, message) -> dict:
    number = ""
    try:
        state_root = Path.home() / ".imos"
        number = ContactBook(state_root).resolve_contact(contact_name)
    except Exception:
        number = contact_name
    if number:
        digits = "".join(ch for ch in str(number) if ch.isdigit() or ch == "+")
        if digits:
            url = f"https://web.whatsapp.com/send?phone={digits}&text={quote(message)}"
            event_bus.publish("tool_progress", message="opening WhatsApp Web...")
            webbrowser.open(url)
            _speak("Opened WhatsApp Web, sir. Press Enter in the browser to send.")
            return {"success": True, "method": "web", "url": url}
    event_bus.publish("tool_progress", message="opening WhatsApp Web...")
    webbrowser.open("https://web.whatsapp.com")
    _speak(f"Opened WhatsApp Web, sir. Search for {contact_name} manually.")
    return {"success": False, "error": "no_number_saved"}


def send_whatsapp(contact_name: str, message: str) -> dict:
    attempted = []
    app_path = find_whatsapp_desktop()
    if app_path:
        attempted.append("WhatsApp Desktop")
        result = try_whatsapp_desktop(app_path, contact_name, message)
        if result.get("success"):
            result["attempted"] = attempted
            return result
    else:
        event_bus.publish("tool_progress", message="WhatsApp Desktop not found")

    attempted.append("WhatsApp Web")
    result = try_whatsapp_web(contact_name, message)
    if result.get("success"):
        result["attempted"] = attempted
        return result

    _speak(f"Could not reach WhatsApp, sir. Tried {', '.join(attempted)}.")
    return {"success": False, "attempted": attempted, **result}
