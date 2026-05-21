"""IMOS service catalog — all integrations plus user-defined services."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

IMOS_HOME = Path.home() / ".imos"
CUSTOM_SERVICES_PATH = IMOS_HOME / "custom_services.json"

# Runtime & control surfaces (always listed)
RUNTIME_SERVICES: list[dict[str, str]] = [
    {"id": "browser", "label": "Playwright Browser", "category": "runtime", "detail": "navigate · click · type · drag · read · screenshot"},
    {"id": "desktop", "label": "Desktop Control", "category": "runtime", "detail": "click · type · drag · hotkey · apps"},
    {"id": "filesystem", "label": "Filesystem", "category": "runtime", "detail": "read · write · rewrite · delete"},
    {"id": "shell", "label": "Shell", "category": "runtime", "detail": "run_shell · terminals"},
    {"id": "dashboard", "label": "Operator Dashboard", "category": "runtime", "detail": "http://localhost:7070"},
    {"id": "sessions", "label": "Sessions", "category": "runtime", "detail": str(IMOS_HOME / "sessions")},
    {"id": "memory", "label": "Memory Log", "category": "runtime", "detail": str(IMOS_HOME / "memory.json")},
    {"id": "mcp", "label": "MCP Server", "category": "runtime", "detail": "Cursor / IDE bridge"},
]

IDE_AGENTS: list[dict[str, str]] = [
    {"id": "cursor", "label": "Cursor", "category": "ide", "detail": "IDE + Agent", "bin": "cursor"},
    {"id": "vscode", "label": "VS Code", "category": "ide", "detail": "Editor", "bin": "code"},
    {"id": "claude_code", "label": "Claude Code", "category": "ide", "detail": "CLI agent", "bin": "claude"},
    {"id": "codex", "label": "OpenAI Codex", "category": "ide", "detail": "CLI agent", "bin": "codex"},
    {"id": "aider", "label": "Aider", "category": "ide", "detail": "CLI pair programmer", "bin": "aider"},
    {"id": "windsurf", "label": "Windsurf", "category": "ide", "detail": "IDE", "bin": "windsurf"},
]

BUILD_PLATFORMS: list[dict[str, str]] = [
    {"id": "lovable", "label": "Lovable", "category": "build", "detail": "lovable.dev UI builder"},
    {"id": "bolt", "label": "Bolt", "category": "build", "detail": "bolt.new"},
    {"id": "v0", "label": "v0", "category": "build", "detail": "v0.dev"},
    {"id": "replit", "label": "Replit", "category": "build", "detail": "replit.com"},
    {"id": "vercel", "label": "Vercel", "category": "deploy", "detail": "vercel CLI", "bin": "vercel"},
    {"id": "netlify", "label": "Netlify", "category": "deploy", "detail": "netlify CLI", "bin": "netlify"},
    {"id": "github", "label": "GitHub", "category": "deploy", "detail": "git + gh CLI", "bin": "gh"},
]

# Extra model providers (beyond model_manager.PROVIDER_TYPES) for catalog display
EXTRA_MODEL_PROVIDERS: list[dict[str, str]] = [
    {"id": "vllm", "label": "vLLM", "category": "model", "provider_type": "custom"},
    {"id": "custom-api", "label": "Custom Model API", "category": "model", "provider_type": "custom"},
]


def _load_custom_services() -> list[dict[str, Any]]:
    if not CUSTOM_SERVICES_PATH.exists():
        return []
    try:
        data = json.loads(CUSTOM_SERVICES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_custom_service(entry: dict[str, Any]) -> dict[str, Any]:
    IMOS_HOME.mkdir(parents=True, exist_ok=True)
    rows = _load_custom_services()
    service_id = str(entry.get("id") or entry.get("label", "custom")).strip().lower().replace(" ", "-")
    normalized = {
        "id": service_id,
        "label": str(entry.get("label", service_id)).strip(),
        "category": str(entry.get("category", "custom")).strip(),
        "detail": str(entry.get("detail", "")).strip(),
        "url": str(entry.get("url", "")).strip(),
        "user_added": True,
    }
    rows = [r for r in rows if r.get("id") != service_id]
    rows.append(normalized)
    CUSTOM_SERVICES_PATH.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return normalized


def _binary_available(name: str | None) -> bool:
    if not name:
        return False
    return bool(shutil.which(name))


def _env_configured(*keys: str) -> bool:
    for key in keys:
        if os.getenv(key, "").strip():
            return True
    return False


def _detect_catalog_entry(entry: dict[str, Any]) -> bool:
    provider = str(entry.get("provider", entry.get("id", ""))).strip().lower()
    category = str(entry.get("category", "")).strip().lower()
    if category.startswith("model"):
        from config.config import is_provider_payload_configured
        from core import model_manager

        for row in model_manager.load_providers():
            if row.get("type") == provider or row.get("id", "").startswith(provider):
                return is_provider_payload_configured(row)
        env_map = {
            "anthropic": ("ANTHROPIC_API_KEY",),
            "openai": ("OPENAI_API_KEY",),
            "groq": ("GROQ_API_KEY",),
            "gemini": ("GOOGLE_GEMINI_API_KEY", "GOOGLE_AI_API_KEY"),
            "openrouter": ("OPENROUTER_API_KEY",),
            "huggingface": ("HUGGINGFACE_API_KEY",),
            "deepseek": ("DEEPSEEK_API_KEY",),
            "alibaba": ("ALIBABA_API_KEY",),
            "nvidia": ("NVIDIA_API_KEY",),
            "together": ("TOGETHER_API_KEY",),
            "mistral": ("MISTRAL_API_KEY",),
            "cohere": ("COHERE_API_KEY",),
            "ollama": (),
            "lmstudio": (),
            "azure": ("AZURE_OPENAI_API_KEY",),
        }
        if provider in {"ollama", "lmstudio", "vllm", "custom-api", "custom"}:
            return True
        keys = env_map.get(provider, ())
        return _env_configured(*keys) if keys else False
    return False


def list_all_services(*, include_catalog: bool = True) -> list[dict[str, Any]]:
    """Full service list for dashboard and /services."""
    from core import model_manager

    services: list[dict[str, Any]] = []

    def push(
        service_id: str,
        label: str,
        category: str,
        available: bool,
        detail: str = "",
        *,
        configurable: bool = False,
        provider_type: str = "",
        user_added: bool = False,
    ) -> None:
        services.append(
            {
                "id": service_id,
                "label": label,
                "category": category,
                "available": available,
                "detail": detail,
                "configurable": configurable,
                "provider_type": provider_type,
                "user_added": user_added,
            }
        )

    for row in RUNTIME_SERVICES:
        push(row["id"], row["label"], row["category"], True, row["detail"])

    for row in IDE_AGENTS:
        push(row["id"], row["label"], row["category"], _binary_available(row.get("bin")), row["detail"])

    for row in BUILD_PLATFORMS:
        avail = _binary_available(row.get("bin")) if row.get("bin") else True
        push(row["id"], row["label"], row["category"], avail, row["detail"])

    for ptype, meta in model_manager.PROVIDER_TYPES.items():
        configured = any(
            r.get("type") == ptype and r.get("enabled", True)
            for r in model_manager.load_providers()
        )
        push(
            f"model-{ptype}",
            meta["name"],
            "model",
            configured or _detect_catalog_entry({"provider": ptype, "category": "model-cloud"}),
            f"Add via /model add · type {ptype}",
            configurable=True,
            provider_type=ptype,
        )

    default = model_manager.get_default()
    if default and not default.get("no_provider_configured"):
        push(
            "active-model",
            f"Active: {default.get('name', default.get('type'))}",
            "model",
            True,
            str(default.get("model", "")),
            provider_type=str(default.get("type", "")),
        )

    for row in EXTRA_MODEL_PROVIDERS:
        push(
            row["id"],
            row["label"],
            "model",
            False,
            "Use /model add with any model name",
            configurable=True,
            provider_type=row.get("provider_type", "custom"),
        )

    if include_catalog:
        try:
            from imos.hub import list_connection_catalog

            for entry in list_connection_catalog():
                provider = str(entry.get("provider", "")).strip()
                push(
                    provider,
                    str(entry.get("name", provider)),
                    str(entry.get("category", "integration")),
                    _detect_catalog_entry(entry),
                    str(entry.get("description", ""))[:120],
                    configurable=True,
                )
        except Exception:
            pass

    for custom in _load_custom_services():
        push(
            str(custom.get("id", "custom")),
            str(custom.get("label", "Custom")),
            str(custom.get("category", "custom")),
            True,
            str(custom.get("detail", "")),
            user_added=True,
        )

    # De-dupe by id (catalog may overlap model-*)
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in services:
        sid = item["id"]
        if sid in seen:
            continue
        seen.add(sid)
        unique.append(item)
    return unique


def list_provider_types() -> list[dict[str, Any]]:
    from core import model_manager

    rows = []
    for ptype, meta in model_manager.PROVIDER_TYPES.items():
        rows.append(
            {
                "type": ptype,
                "name": meta["name"],
                "requires_key": meta.get("requires_key", True),
                "base_url": meta.get("base_url", ""),
            }
        )
    rows.append({"type": "vllm", "name": "vLLM / OpenAI-compatible", "requires_key": False, "base_url": ""})
    return rows
