from __future__ import annotations

import os
import webbrowser
from pathlib import Path

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["play_music", "search_youtube", "open_maps", "open_website", "download_youtube"]},
        "query": {"type": "string"},
        "location": {"type": "string"},
        "url": {"type": "string"},
        "folder": {"type": "string"},
        "output_dir": {"type": "string"},
    },
    "required": ["action"],
}


def run(inputs, **_kwargs):
    action = str(inputs.get("action", "")).strip().lower()
    if action == "play_music":
        folder = Path(str(inputs.get("folder", str(Path.home() / "Music"))))
        if not folder.exists():
            return {"ok": False, "error": f"Music folder not found: {folder}"}
        files = [item for item in folder.iterdir() if item.suffix.lower() in {".mp3", ".wav", ".m4a"}]
        if not files:
            return {"ok": False, "error": "No music files found."}
        os.startfile(str(files[0]))  # type: ignore[attr-defined]
        return {"ok": True, "file": str(files[0])}
    if action == "search_youtube":
        query = str(inputs.get("query", "")).strip()
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        webbrowser.open(url)
        return {"ok": True, "url": url}
    if action == "open_maps":
        location = str(inputs.get("location", "")).strip()
        url = f"https://www.google.com/maps/search/{location.replace(' ', '+')}"
        webbrowser.open(url)
        return {"ok": True, "url": url}
    if action == "open_website":
        url = str(inputs.get("url", "")).strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
        return {"ok": True, "url": url}
    if action == "download_youtube":
        try:
            import yt_dlp
        except ModuleNotFoundError as exc:
            raise RuntimeError("download unavailable: missing dependency 'yt-dlp'") from exc
        output_dir = Path(str(inputs.get("output_dir", str(Path.home() / "Downloads"))))
        output_dir.mkdir(parents=True, exist_ok=True)
        opts = {"format": "best", "outtmpl": str(output_dir / "%(title)s.%(ext)s"), "quiet": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(str(inputs.get("url", "")).strip(), download=True)
        return {"ok": True, "title": info.get("title", ""), "output_dir": str(output_dir)}
    return {"ok": False, "error": f"Unknown action: {action}"}
