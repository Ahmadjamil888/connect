from __future__ import annotations

import os
import glob
import shutil
import subprocess
import time
import io
import contextlib
from pathlib import Path
from typing import Any


def get_whatsapp_paths() -> list[str]:
    candidates: list[str] = []
    store_pattern = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\WhatsApp.exe")
    candidates.append(store_pattern)
    wa_glob = glob.glob(os.path.expandvars(r"C:\Program Files\WindowsApps\WhatsApp*\WhatsApp.exe"))
    candidates.extend(wa_glob)
    candidates += [
        os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%APPDATA%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\WhatsApp\WhatsApp.exe"),
    ]
    candidates.append("whatsapp://")
    return candidates


def expand_glob_paths(paths: list[str]) -> list[str]:
    result: list[str] = []
    for path in paths:
        if "*" in path:
            result.extend(sorted(glob.glob(path), reverse=True))
        else:
            result.append(path)
    return result


def _get_pyautogui():
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import pyautogui
    except ModuleNotFoundError as exc:
        raise RuntimeError("computer control unavailable: missing dependency 'pyautogui'") from exc
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
    try:
        x, y = pyautogui.position()
        sw, sh = pyautogui.size()
        corners = {(0, 0), (0, sh - 1), (sw - 1, 0), (sw - 1, sh - 1)}
        if (x, y) in corners:
            pyautogui.FAILSAFE = False
            pyautogui.moveTo(min(100, sw - 1), min(100, sh - 1), duration=0.05)
            pyautogui.FAILSAFE = True
    except Exception:
        pass
    return pyautogui


def _get_pygetwindow():
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import pygetwindow
    except ModuleNotFoundError as exc:
        raise RuntimeError("computer control unavailable: missing dependency 'pygetwindow'") from exc
    return pygetwindow


def screenshot(filename: str | Path | None = None) -> dict[str, Any]:
    desktop_root = Path.home() / "Desktop" / "imos_screenshots"
    save_dir = desktop_root
    provided = Path(filename) if filename is not None else None
    if provided is not None:
        try:
            if provided.exists() and provided.is_dir():
                save_dir = provided
                filename = None
            elif not provided.suffix:
                save_dir = provided
                filename = None
        except Exception:
            if not provided.suffix:
                save_dir = provided
                filename = None
    save_dir.mkdir(parents=True, exist_ok=True)
    if not filename:
        filename = f"screenshot_{int(time.time())}.png"
    save_path = save_dir / Path(str(filename)).name
    try:
        pyautogui = _get_pyautogui()
        image = pyautogui.screenshot()
        image.save(save_path)
        if save_path.exists() and save_path.stat().st_size < 10 * 1024:
            return {"ok": False, "error": "Screenshot file too small.", "path": str(save_path)}
        try:
            from PIL import Image, ImageStat

            img = Image.open(save_path)
            if ImageStat.Stat(img).mean and sum(ImageStat.Stat(img).mean) / len(ImageStat.Stat(img).mean) < 5:
                return {
                    "ok": False,
                    "error": "Screenshot appears black. Screen may be locked or display off.",
                    "path": str(save_path),
                }
        except Exception:
            pass
        return {"ok": True, "path": str(save_path)}
    except ImportError:
        return {"ok": False, "error": "pyautogui not installed. Run: pip install pyautogui pillow"}
    try:
        from PIL import ImageGrab

        image = ImageGrab.grab()
        image.save(save_path)
        return {"ok": True, "path": str(save_path), "method": "PIL"}
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "tip": "Try running IMOS as Administrator if access denied persists.",
        }


def type_text(text: str) -> dict[str, Any]:
    pyautogui = _get_pyautogui()
    pyautogui.write(text, interval=0.02)
    return {"ok": True, "typed": len(text)}


def click(x: int, y: int) -> dict[str, Any]:
    pyautogui = _get_pyautogui()
    pyautogui.click(x, y)
    return {"ok": True, "x": x, "y": y}


def hover(x: int, y: int) -> dict[str, Any]:
    pyautogui = _get_pyautogui()
    pyautogui.moveTo(x, y)
    return {"ok": True, "x": x, "y": y}


def press_key(key: str) -> dict[str, Any]:
    pyautogui = _get_pyautogui()
    parts = [part.strip().lower() for part in key.replace("+", " ").split() if part.strip()]
    if not parts:
        return {"ok": False, "error": "No key provided."}
    if len(parts) == 1:
        pyautogui.press(parts[0])
    else:
        pyautogui.hotkey(*parts)
    return {"ok": True, "key": key}


def scroll(x: int | None, y: int | None, amount: int) -> dict[str, Any]:
    pyautogui = _get_pyautogui()
    if x is not None and y is not None:
        pyautogui.moveTo(x, y)
    pyautogui.scroll(amount)
    return {"ok": True, "x": x, "y": y, "amount": amount}


def find_on_screen(image_path: str) -> dict[str, Any]:
    pyautogui = _get_pyautogui()
    location = pyautogui.locateCenterOnScreen(image_path)
    if location is None:
        return {"ok": False, "error": f"Element not found: {image_path}"}
    return {"ok": True, "x": int(location.x), "y": int(location.y), "image_path": image_path}


def click_element(image_path: str) -> dict[str, Any]:
    located = find_on_screen(image_path)
    if not located.get("ok"):
        return located
    return click(int(located["x"]), int(located["y"]))


def focus_window(title: str) -> dict[str, Any]:
    pygetwindow = _get_pygetwindow()
    matches = [window for window in pygetwindow.getAllWindows() if title.lower() in (window.title or "").lower()]
    if not matches:
        return {"ok": False, "error": f"Window not found: {title}"}
    window = matches[0]
    try:
        window.restore()
    except Exception:
        pass
    window.activate()
    return {"ok": True, "title": window.title}


def open_app(name: str) -> dict[str, Any]:
    try:
        from core.events import event_bus

        event_bus.publish("tool_progress", message=f"Opening {name}...")
    except Exception:
        pass
    app_name = str(name or "").strip()
    name = app_name.lower()
    creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    app_map = {
        "edge": [
            "msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "chrome": [
            "chrome.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "firefox": [
            "firefox.exe",
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
        ],
        "notepad": ["notepad.exe"],
        "explorer": ["explorer.exe"],
        "calculator": ["calc.exe"],
        "cmd": ["cmd.exe"],
        "powershell": ["powershell.exe"],
        "whatsapp": get_whatsapp_paths(),
        "whatsapp://": ["whatsapp://"],
        "spotify": [
            os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe"),
        ],
        "telegram": [
            os.path.expandvars(r"%APPDATA%\Telegram Desktop\Telegram.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Telegram Desktop\Telegram.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Telegram Desktop\Telegram.exe"),
        ],
        "discord": expand_glob_paths([
            os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-*\Discord.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Discord\Discord.exe"),
        ]),
        "zoom": [
            os.path.expandvars(r"%APPDATA%\Zoom\bin\Zoom.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Zoom\Zoom.exe"),
        ],
        "teams": [
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Teams\current\Teams.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\MSTeams.exe"),
        ],
        "slack": [os.path.expandvars(r"%LOCALAPPDATA%\slack\slack.exe")],
        "vscode": [
            "code.exe",
            "code",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        ],
        "cursor": [os.path.expandvars(r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe")],
        "windsurf": [os.path.expandvars(r"%LOCALAPPDATA%\Programs\windsurf\Windsurf.exe")],
        "excel": [
            os.path.expandvars(r"%PROGRAMFILES%\Microsoft Office\root\Office16\EXCEL.EXE"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\EXCEL.EXE"),
        ],
        "word": [
            os.path.expandvars(r"%PROGRAMFILES%\Microsoft Office\root\Office16\WINWORD.EXE"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\WINWORD.EXE"),
        ],
        "paint": ["mspaint.exe"],
        "wordpad": ["wordpad.exe"],
        "snipping": ["SnippingTool.exe", "SnipSketch.exe"],
        "vlc": [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ],
        "task manager": ["taskmgr.exe"],
        "settings": ["ms-settings:"],
        "store": ["ms-windows-store:"],
    }
    searched = app_map.get(name, [app_name])
    candidates = searched if name in app_map else [app_name, f"{app_name}.exe"]
    for candidate in candidates:
        try:
            if candidate.endswith("://") or candidate.startswith("ms-"):
                try:
                    os.startfile(candidate)  # type: ignore[attr-defined]
                    try:
                        from core.events import event_bus

                        event_bus.publish("tool_progress", message=f"Launched {candidate}")
                    except Exception:
                        pass
                    return {"ok": True, "launched": candidate, "method": "protocol"}
                except Exception:
                    continue
            if os.path.isabs(candidate) or candidate.startswith("%"):
                expanded = os.path.expandvars(candidate)
                if os.path.exists(expanded):
                    subprocess.Popen([expanded], creationflags=creationflags)
                    try:
                        from core.events import event_bus

                        event_bus.publish("tool_progress", message=f"Launched {expanded}")
                    except Exception:
                        pass
                    return {"ok": True, "launched": expanded}
                continue
            if shutil.which(candidate):
                subprocess.Popen([candidate], creationflags=creationflags)
                try:
                    from core.events import event_bus

                    event_bus.publish("tool_progress", message=f"Launched {candidate}")
                except Exception:
                    pass
                return {"ok": True, "launched": candidate}
        except Exception:
            continue
    return {
        "ok": False,
        "error": f"{app_name} not found.",
        "searched": [str(path) for path in searched[:5]],
        "tip": f"Is {app_name} installed? If it is a Microsoft Store app, try: imos> open whatsapp:// ",
    }
