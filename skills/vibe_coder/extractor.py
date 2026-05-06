from __future__ import annotations

import glob
import os
import shutil
import subprocess
import time

from core.vision import ask_vision, ask_vision_coordinates
from tools.computer_control import click, screenshot


def click_download_and_save(tool_name: str, project_name: str, output_dir: str) -> dict:
    downloads = os.path.expanduser("~/Downloads")
    before = set(glob.glob(os.path.join(downloads, "*.zip")))
    shot = screenshot()
    if not shot.get("ok"):
        return {"ok": False, "error": "Could not capture screen"}
    coords = ask_vision_coordinates(
        shot["path"],
        "Where is the download or export button? Return x,y pixel coordinates only.",
    )
    if coords:
        click(coords["x"], coords["y"])
    for _ in range(30):
        time.sleep(2)
        after = set(glob.glob(os.path.join(downloads, "*.zip")))
        new_zips = after - before
        if new_zips:
            zip_path = list(new_zips)[0]
            dest = output_dir if os.path.basename(output_dir) == project_name else os.path.join(output_dir, project_name)
            os.makedirs(dest, exist_ok=True)
            shutil.unpack_archive(zip_path, dest)
            os.remove(zip_path)
            return {"ok": True, "path": dest}
    return {"ok": False, "error": "No ZIP downloaded within 60s"}


def copy_code_from_screen(output_dir: str, filename: str = "component.tsx") -> dict:
    try:
        import pyperclip
    except Exception as exc:
        return {"ok": False, "error": f"pyperclip unavailable: {exc}"}
    shot = screenshot()
    if not shot.get("ok"):
        return {"ok": False, "error": "Could not capture screen"}
    coords = ask_vision_coordinates(
        shot["path"],
        "Where is the Copy or Copy Code button? Return x,y pixel coordinates only.",
    )
    if coords:
        click(coords["x"], coords["y"])
        time.sleep(0.5)
        code = pyperclip.paste()
        if code and len(code) > 50:
            os.makedirs(output_dir, exist_ok=True)
            path = os.path.join(output_dir, filename)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(code)
            return {"ok": True, "path": path, "chars": len(code)}
    return {"ok": False, "error": "Could not extract code from screen"}


def clone_if_github_visible() -> dict:
    shot = screenshot()
    if not shot.get("ok"):
        return {"ok": False, "reason": "Could not capture screen"}
    result = ask_vision(
        shot["path"],
        "Is there a GitHub repository URL visible on screen? If yes, return just the URL (https://github.com/...). If no, return NO.",
    )
    if str(result).startswith("https://github.com"):
        url = str(result).strip()
        dest = os.path.join(os.path.expanduser("~/Desktop"), url.split("/")[-1])
        subprocess.run(["git", "clone", url, dest], timeout=120, check=False)
        return {"ok": True, "path": dest, "url": url}
    return {"ok": False, "reason": "No GitHub URL visible"}

