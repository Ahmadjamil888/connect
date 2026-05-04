from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_assistant import build_gateway
from config.config import load_config, resolve_runtime_state_root, save_config
from core.voice import VoiceManager
from service.status import ServiceStatusStore
from setup.autostart import safe_autostart_status
from setup.install_service import ensure_chime


def _make_icon(active: bool):
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    color = (34, 197, 94, 255) if active else (249, 115, 22, 255)
    draw.ellipse((8, 8, 56, 56), fill=color)
    draw.text((22, 18), "I", fill=(255, 255, 255, 255))
    return image


def main() -> int:
    cfg = load_config()
    workspace = cfg.get("workspace", str(PROJECT_ROOT))
    state_root = resolve_runtime_state_root(workspace)
    status_store = ServiceStatusStore(state_root / "service" / "status.json")
    chime = ensure_chime(PROJECT_ROOT / "audio")

    cfg.setdefault("listen", {})
    cfg["listen"]["enabled"] = True
    cfg["listen"]["persist"] = True
    cfg.setdefault("mcp", {})
    cfg["mcp"]["enabled"] = True
    cfg["mcp"].setdefault("host", "127.0.0.1")
    cfg["mcp"].setdefault("port", 8765)
    save_config(cfg)

    gateway, _cli_channel, _skills = build_gateway(workspace)
    listener = getattr(gateway, "listener_service", None)
    dashboard = getattr(gateway, "dashboard_service", None)
    voice = VoiceManager(state_root / "voice")
    if listener is not None:
        listener.speaker = voice
        listener.chime_path = chime
        listener.start(persist=True)

    def _snapshot(*, tray: bool) -> dict[str, Any]:
        listener_status = listener.status() if listener is not None else {"active": False}
        dashboard_status = dashboard.status() if dashboard is not None else {"running": False, "url": "http://127.0.0.1:8766"}
        voice_status = voice.status()
        return {
            "running": True,
            "tray": tray,
            "dashboard": dashboard_status,
            "listener": listener_status,
            "voice": voice_status,
            "autostart": safe_autostart_status(PROJECT_ROOT),
            "updated_at": time.time(),
        }

    status_store.write(_snapshot(tray=False))

    def open_dashboard(_icon=None, _item=None):
        if dashboard is not None:
            webbrowser.open(dashboard.status().get("url", "http://127.0.0.1:8766") + "/")

    def open_terminal(_icon=None, _item=None):
        subprocess.Popen([sys.executable, str(PROJECT_ROOT / "ai_assistant.py")], cwd=str(PROJECT_ROOT))

    def stop_listening(_icon=None, _item=None):
        if listener is not None:
            listener.stop()
        status_store.write(_snapshot(tray=True))

    def exit_imos(icon=None, _item=None):
        if listener is not None:
            listener.stop()
        if dashboard is not None:
            dashboard.stop()
        status_store.write({"running": False, "tray": False, "updated_at": time.time()})
        if icon is not None:
            icon.stop()

    def heartbeat(tray: bool) -> None:
        while True:
            status_store.write(_snapshot(tray=tray))
            time.sleep(2.0)

    try:
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem("Open Dashboard", open_dashboard),
            pystray.MenuItem("Open Terminal", open_terminal),
            pystray.MenuItem("Stop Listening", stop_listening),
            pystray.MenuItem("Exit IMOS", exit_imos),
        )
        icon = pystray.Icon("IMOS", _make_icon(bool(listener and listener.status().get("active"))), "IMOS", menu)

        def pulse() -> None:
            while True:
                active = bool(listener and listener.status().get("active"))
                icon.icon = _make_icon(active)
                time.sleep(2.0)

        threading.Thread(target=heartbeat, args=(True,), daemon=True, name="imos-service-heartbeat").start()
        threading.Thread(target=pulse, daemon=True, name="imos-service-pulse").start()
        icon.run()
    except Exception:
        threading.Thread(target=heartbeat, args=(False,), daemon=True, name="imos-service-heartbeat").start()
        while True:
            time.sleep(5.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
