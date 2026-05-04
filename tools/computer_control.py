from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


def _get_pyautogui():
    try:
        import pyautogui
    except ModuleNotFoundError as exc:
        raise RuntimeError("computer control unavailable: missing dependency 'pyautogui'") from exc
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
    return pyautogui


def _get_pygetwindow():
    try:
        import pygetwindow
    except ModuleNotFoundError as exc:
        raise RuntimeError("computer control unavailable: missing dependency 'pygetwindow'") from exc
    return pygetwindow


def screenshot(save_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(save_dir) if save_dir else Path(tempfile.gettempdir())
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"computer_control_{int(time.time() * 1000)}.png"
    errors: list[str] = []
    try:
        pyautogui = _get_pyautogui()
        image = pyautogui.screenshot()
        image.save(path)
        return {"ok": True, "path": str(path), "backend": "pyautogui"}
    except Exception as exc:
        errors.append(f"pyautogui: {exc}")
    try:
        from PIL import ImageGrab

        image = ImageGrab.grab(all_screens=True)
        image.save(path)
        return {"ok": True, "path": str(path), "backend": "imagegrab"}
    except Exception as exc:
        errors.append(f"imagegrab: {exc}")
    try:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            monitor = sct.monitors[0]
            shot = sct.grab(monitor)
            image = Image.frombytes("RGB", shot.size, shot.rgb)
            image.save(path)
        return {"ok": True, "path": str(path), "backend": "mss"}
    except Exception as exc:
        errors.append(f"mss: {exc}")
    try:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (1280, 720), color=(0, 0, 0))
        drawer = ImageDraw.Draw(image)
        drawer.text((20, 20), "Screenshot failed", fill=(255, 69, 0))
        drawer.text((20, 60), "; ".join(errors)[:4000], fill=(255, 255, 255))
        image.save(path)
    except Exception:
        pass
    return {"ok": False, "error": "; ".join(errors) or "screen grab failed", "path": str(path)}


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
    searched: list[str] = []
    candidates: list[str] = []
    local_appdata = os.getenv("LOCALAPPDATA", "").strip()
    appdata = os.getenv("APPDATA", "").strip()
    program_files = os.getenv("ProgramFiles", "").strip()
    program_files_x86 = os.getenv("ProgramFiles(x86)", "").strip()
    normalized = name.strip()
    for candidate in [
        normalized,
        f"{normalized}.exe",
        str(Path(local_appdata) / "Programs" / normalized / f"{normalized}.exe") if local_appdata else "",
        str(Path(local_appdata) / "Programs" / normalized.lower() / f"{normalized}.exe") if local_appdata else "",
        str(Path(program_files) / normalized / f"{normalized}.exe") if program_files else "",
        str(Path(program_files_x86) / normalized / f"{normalized}.exe") if program_files_x86 else "",
        str(Path(appdata) / normalized / f"{normalized}.exe") if appdata else "",
    ]:
        if candidate:
            searched.append(candidate)
            candidates.append(candidate)

    for candidate in candidates:
        try:
            proc = subprocess.Popen([candidate], shell=False)
            return {"ok": True, "pid": proc.pid, "launched": candidate, "searched": searched}
        except FileNotFoundError:
            continue
        except Exception:
            continue

    shell_targets = [name, f"shell:AppsFolder\\{name}"]
    for target in shell_targets:
        searched.append(f"start:{target}")
        try:
            os.startfile(target)  # type: ignore[attr-defined]
            return {"ok": True, "launched": target, "searched": searched}
        except Exception:
            continue

    return {"ok": False, "error": f"Could not open {name}", "searched": searched}
