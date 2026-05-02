from __future__ import annotations

import ctypes
import os
import sys
from typing import Dict

from config.config import load_config, save_config
from imos.config import merged_settings, save_settings

DEFAULT_DASHBOARD_PALETTE = "ember"
DEFAULT_SHELL_PALETTE = "ember"

DASHBOARD_PALETTES: Dict[str, Dict[str, str]] = {
    "ember": {
        "--bg": "#000000",
        "--bg2": "#0a0a0a",
        "--bg3": "#111111",
        "--bg4": "#1a1a1a",
        "--border": "#222222",
        "--border2": "#2a2a2a",
        "--orange": "#ff6b00",
        "--orange-dim": "#cc5500",
        "--orange-glow": "rgba(255,107,0,0.15)",
        "--orange-subtle": "rgba(255,107,0,0.08)",
        "--text": "#ffffff",
        "--text2": "#aaaaaa",
        "--text3": "#666666",
        "--green": "#22c55e",
        "--red": "#ef4444",
        "--blue": "#3b82f6",
    },
    "ocean": {
        "--bg": "#071019",
        "--bg2": "#0c1723",
        "--bg3": "#122233",
        "--bg4": "#173048",
        "--border": "#1e3448",
        "--border2": "#2b4a66",
        "--orange": "#57c7ff",
        "--orange-dim": "#249bd4",
        "--orange-glow": "rgba(87,199,255,0.18)",
        "--orange-subtle": "rgba(87,199,255,0.09)",
        "--text": "#eef7ff",
        "--text2": "#9eb5c7",
        "--text3": "#688198",
        "--green": "#2dd4bf",
        "--red": "#ff6b6b",
        "--blue": "#7dd3fc",
    },
    "forest": {
        "--bg": "#08110b",
        "--bg2": "#0d1710",
        "--bg3": "#142119",
        "--bg4": "#1c2b22",
        "--border": "#25372b",
        "--border2": "#314735",
        "--orange": "#8bd450",
        "--orange-dim": "#6cab37",
        "--orange-glow": "rgba(139,212,80,0.16)",
        "--orange-subtle": "rgba(139,212,80,0.08)",
        "--text": "#f3f8ef",
        "--text2": "#afbaa6",
        "--text3": "#72806b",
        "--green": "#4ade80",
        "--red": "#fb7185",
        "--blue": "#60a5fa",
    },
    "rose": {
        "--bg": "#140a10",
        "--bg2": "#1b0f17",
        "--bg3": "#261520",
        "--bg4": "#311c2a",
        "--border": "#442635",
        "--border2": "#5a3448",
        "--orange": "#ff7aa2",
        "--orange-dim": "#e15f87",
        "--orange-glow": "rgba(255,122,162,0.18)",
        "--orange-subtle": "rgba(255,122,162,0.08)",
        "--text": "#fff4f8",
        "--text2": "#d7afbc",
        "--text3": "#9b7480",
        "--green": "#34d399",
        "--red": "#fb7185",
        "--blue": "#93c5fd",
    },
}

SHELL_PALETTES: Dict[str, Dict[str, str]] = {
    "ember": {
        "accent_ansi": "\033[38;5;208m",
        "muted_ansi": "\033[90m",
        "ok_ansi": "\033[32m",
        "err_ansi": "\033[31m",
        "bold_ansi": "\033[1;37m",
        "shell_bg": "#000000",
        "shell_bg_2": "#0b0b0b",
        "shell_text": "#e2e8f0",
        "shell_muted": "#666666",
        "shell_accent": "#ff6b00",
        "shell_ok": "#22c55e",
        "shell_err": "#ef4444",
    },
    "matrix": {
        "accent_ansi": "\033[92m",
        "muted_ansi": "\033[90m",
        "ok_ansi": "\033[32m",
        "err_ansi": "\033[31m",
        "bold_ansi": "\033[1;97m",
        "shell_bg": "#020b02",
        "shell_bg_2": "#041204",
        "shell_text": "#b7ffbf",
        "shell_muted": "#4f7a57",
        "shell_accent": "#7dff86",
        "shell_ok": "#5efc8d",
        "shell_err": "#ff6b81",
    },
    "ice": {
        "accent_ansi": "\033[96m",
        "muted_ansi": "\033[90m",
        "ok_ansi": "\033[36m",
        "err_ansi": "\033[91m",
        "bold_ansi": "\033[1;97m",
        "shell_bg": "#06111a",
        "shell_bg_2": "#0c1824",
        "shell_text": "#d8f3ff",
        "shell_muted": "#7090a8",
        "shell_accent": "#63d3ff",
        "shell_ok": "#5eead4",
        "shell_err": "#ff7b93",
    },
    "paper": {
        "accent_ansi": "\033[34m",
        "muted_ansi": "\033[90m",
        "ok_ansi": "\033[32m",
        "err_ansi": "\033[31m",
        "bold_ansi": "\033[30;47m",
        "shell_bg": "#f6f2e8",
        "shell_bg_2": "#ebe4d4",
        "shell_text": "#1f2937",
        "shell_muted": "#8a7f6a",
        "shell_accent": "#2563eb",
        "shell_ok": "#15803d",
        "shell_err": "#b91c1c",
    },
}


def _set_nested(cfg: dict, path: str, value) -> None:
    node = cfg
    parts = path.split(".")
    for part in parts[:-1]:
        current = node.get(part)
        if not isinstance(current, dict):
            current = {}
            node[part] = current
        node = current
    node[parts[-1]] = value


def get_ui_config() -> dict:
    cfg = load_config()
    dashboard_cfg = cfg.get("dashboard", {}) if isinstance(cfg.get("dashboard"), dict) else {}
    shell_cfg = cfg.get("shell", {}) if isinstance(cfg.get("shell"), dict) else {}

    dashboard_palette = str(
        dashboard_cfg.get("palette") or dashboard_cfg.get("theme") or DEFAULT_DASHBOARD_PALETTE
    ).strip().lower()
    shell_palette = str(shell_cfg.get("palette") or DEFAULT_SHELL_PALETTE).strip().lower()

    if dashboard_palette not in DASHBOARD_PALETTES:
        dashboard_palette = DEFAULT_DASHBOARD_PALETTE
    if shell_palette not in SHELL_PALETTES:
        shell_palette = DEFAULT_SHELL_PALETTE

    try:
        settings = merged_settings()
        dashboard_from_settings = str(settings.get("dashboard_palette", dashboard_palette)).strip().lower()
        shell_from_settings = str(settings.get("shell_palette", shell_palette)).strip().lower()
        if dashboard_from_settings in DASHBOARD_PALETTES:
            dashboard_palette = dashboard_from_settings
        if shell_from_settings in SHELL_PALETTES:
            shell_palette = shell_from_settings
    except Exception:
        pass

    return {
        "dashboard_palette": dashboard_palette,
        "shell_palette": shell_palette,
        "dashboard_palettes": sorted(DASHBOARD_PALETTES.keys()),
        "shell_palettes": sorted(SHELL_PALETTES.keys()),
    }


def save_ui_config(*, dashboard_palette: str | None = None, shell_palette: str | None = None) -> dict:
    cfg = load_config()
    if dashboard_palette:
        dashboard_palette = dashboard_palette.strip().lower()
        if dashboard_palette not in DASHBOARD_PALETTES:
            raise ValueError(f"Unknown dashboard palette: {dashboard_palette}")
        _set_nested(cfg, "dashboard.palette", dashboard_palette)
        _set_nested(cfg, "dashboard.theme", dashboard_palette)
    if shell_palette:
        shell_palette = shell_palette.strip().lower()
        if shell_palette not in SHELL_PALETTES:
            raise ValueError(f"Unknown shell palette: {shell_palette}")
        _set_nested(cfg, "shell.palette", shell_palette)
    try:
        save_config(cfg)
    except Exception:
        settings = merged_settings()
        if dashboard_palette:
            settings["dashboard_palette"] = dashboard_palette
        if shell_palette:
            settings["shell_palette"] = shell_palette
        save_settings(settings)
    return get_ui_config()


def _enable_windows_vt() -> bool:
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        if handle in (0, -1):
            return False
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
            return False
        enabled = mode.value | 0x0004
        if kernel32.SetConsoleMode(handle, enabled) == 0:
            return False
        return True
    except Exception:
        return False


def setup_terminal_io() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def terminal_supports_ansi() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("WT_SESSION") or os.getenv("ANSICON") or os.getenv("ConEmuANSI") == "ON":
        return True
    stream = getattr(sys, "stdout", None)
    if not stream or not getattr(stream, "isatty", lambda: False)():
        return False
    return _enable_windows_vt()


def get_cli_palette() -> dict[str, str]:
    setup_terminal_io()
    ui_cfg = get_ui_config()
    shell_palette = SHELL_PALETTES[ui_cfg["shell_palette"]]
    if terminal_supports_ansi():
        return {
            "O": shell_palette["accent_ansi"],
            "W": shell_palette["bold_ansi"],
            "G": shell_palette["ok_ansi"],
            "R": shell_palette["err_ansi"],
            "D": shell_palette["muted_ansi"],
            "X": "\033[0m",
        }
    return {"O": "", "W": "", "G": "", "R": "", "D": "", "X": ""}
