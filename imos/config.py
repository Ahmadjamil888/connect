from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values


IMOS_HOME = Path.home() / ".imos"
CONNECTIONS_PATH = IMOS_HOME / "connections.yaml"
SETTINGS_PATH = IMOS_HOME / "imos_settings.yaml"
PROJECT_ENV_PATH = Path.cwd() / ".env"

DEFAULT_CONNECTIONS = {
    "connections": [],
    "settings": {
        "default_model": "auto",
        "parallel_execution": True,
        "max_concurrent_tasks": 10,
        "result_synthesis_model": "anthropic",
        "log_level": "info",
        "dashboard_port": 8765,
        "enable_payments": False,
        "enable_os_control": True,
    },
}


def _ensure_home() -> None:
    global IMOS_HOME, CONNECTIONS_PATH, SETTINGS_PATH
    try:
        IMOS_HOME.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        IMOS_HOME = Path.cwd() / ".imos"
        CONNECTIONS_PATH = IMOS_HOME / "connections.yaml"
        SETTINGS_PATH = IMOS_HOME / "imos_settings.yaml"
        IMOS_HOME.mkdir(parents=True, exist_ok=True)


def _read_yaml(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return deepcopy(default)
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            merged = deepcopy(default)
            merged.update(loaded)
            return merged
    except Exception:
        pass
    return deepcopy(default)


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    _ensure_home()
    try:
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    except PermissionError:
        global IMOS_HOME, CONNECTIONS_PATH, SETTINGS_PATH
        IMOS_HOME = Path.cwd() / ".imos"
        CONNECTIONS_PATH = IMOS_HOME / "connections.yaml"
        SETTINGS_PATH = IMOS_HOME / "imos_settings.yaml"
        IMOS_HOME.mkdir(parents=True, exist_ok=True)
        fallback = IMOS_HOME / path.name
        fallback.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def ensure_default_files() -> None:
    _ensure_home()
    if not CONNECTIONS_PATH.exists():
        _write_yaml(CONNECTIONS_PATH, DEFAULT_CONNECTIONS)
    if not SETTINGS_PATH.exists():
        _write_yaml(SETTINGS_PATH, {"settings": deepcopy(DEFAULT_CONNECTIONS["settings"])})


def load_connections_config() -> dict[str, Any]:
    ensure_default_files()
    return _read_yaml(CONNECTIONS_PATH, DEFAULT_CONNECTIONS)


def load_global_settings() -> dict[str, Any]:
    ensure_default_files()
    return _read_yaml(SETTINGS_PATH, {"settings": deepcopy(DEFAULT_CONNECTIONS["settings"])})


def load_env_values() -> dict[str, str]:
    env_values = dict(dotenv_values(PROJECT_ENV_PATH)) if PROJECT_ENV_PATH.exists() else {}
    for key, value in os.environ.items():
        env_values[key] = value
    return {str(key): "" if value is None else str(value) for key, value in env_values.items()}


def merged_settings() -> dict[str, Any]:
    connections = load_connections_config()
    global_settings = load_global_settings()
    settings = deepcopy(DEFAULT_CONNECTIONS["settings"])
    settings.update(connections.get("settings", {}))
    settings.update(global_settings.get("settings", {}))
    return settings


def get_adapter_config(name: str) -> dict[str, Any]:
    env_values = load_env_values()
    for entry in load_connections_config().get("connections", []):
        if entry.get("name") == name:
            config = deepcopy(entry)
            config["env"] = env_values
            return config
    return {"name": name, "env": env_values}


def list_configured_adapters() -> list[dict[str, Any]]:
    env_values = load_env_values()
    adapters: list[dict[str, Any]] = []
    for entry in load_connections_config().get("connections", []):
        item = deepcopy(entry)
        item["env"] = env_values
        adapters.append(item)
    return adapters


def save_adapter_config(name: str, config: dict[str, Any]) -> None:
    payload = load_connections_config()
    connections = payload.setdefault("connections", [])
    updated = False
    for index, entry in enumerate(connections):
        if entry.get("name") == name:
            merged = deepcopy(config)
            merged["name"] = name
            connections[index] = merged
            updated = True
            break
    if not updated:
        new_entry = deepcopy(config)
        new_entry["name"] = name
        connections.append(new_entry)
    _write_yaml(CONNECTIONS_PATH, payload)


def remove_adapter_config(name: str) -> None:
    payload = load_connections_config()
    payload["connections"] = [entry for entry in payload.get("connections", []) if entry.get("name") != name]
    _write_yaml(CONNECTIONS_PATH, payload)


def save_settings(settings: dict[str, Any]) -> None:
    _write_yaml(SETTINGS_PATH, {"settings": settings})
