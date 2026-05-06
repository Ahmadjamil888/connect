from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "providers.json"

PROVIDER_TYPES: dict[str, dict[str, Any]] = {
    "groq": {"name": "Groq", "base_url": "https://api.groq.com/openai/v1", "requires_key": True},
    "anthropic": {"name": "Anthropic", "base_url": "", "requires_key": True},
    "openai": {"name": "OpenAI", "base_url": "https://api.openai.com/v1", "requires_key": True},
    "gemini": {"name": "Google Gemini", "base_url": "", "requires_key": True},
    "openrouter": {"name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "requires_key": True},
    "ollama": {"name": "Ollama", "base_url": "http://localhost:11434/v1", "requires_key": False},
    "lmstudio": {"name": "LM Studio", "base_url": "http://localhost:1234/v1", "requires_key": False},
    "together": {"name": "Together AI", "base_url": "https://api.together.xyz/v1", "requires_key": True},
    "mistral": {"name": "Mistral", "base_url": "https://api.mistral.ai/v1", "requires_key": True},
    "cohere": {"name": "Cohere", "base_url": "https://api.cohere.com/v1", "requires_key": True},
    "custom": {"name": "Custom", "base_url": "", "requires_key": False},
}

ENV_PROVIDER_SPECS = [
    {
        "env_provider": "groq",
        "id": "groq-main",
        "name": "Groq",
        "type": "groq",
        "key_env": "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
        "default_model": "llama-3.3-70b-versatile",
    },
    {
        "env_provider": "anthropic",
        "id": "anthropic-main",
        "name": "Anthropic",
        "type": "anthropic",
        "key_env": "ANTHROPIC_API_KEY",
        "model_env": "ANTHROPIC_MODEL",
        "default_model": "claude-sonnet-4-5",
    },
    {
        "env_provider": "openai",
        "id": "openai-main",
        "name": "OpenAI",
        "type": "openai",
        "key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "default_model": "gpt-4o",
    },
    {
        "env_provider": "gemini",
        "id": "gemini-main",
        "name": "Google Gemini",
        "type": "gemini",
        "key_env": "GOOGLE_GEMINI_API_KEY",
        "model_env": "GOOGLE_GEMINI_MODEL",
        "default_model": "gemini-2.0-flash",
    },
    {
        "env_provider": "openrouter",
        "id": "openrouter-main",
        "name": "OpenRouter",
        "type": "openrouter",
        "key_env": "OPENROUTER_API_KEY",
        "model_env": "OPENROUTER_MODEL",
        "default_model": "openai/gpt-4o-mini",
    },
    {
        "env_provider": "ollama",
        "id": "ollama-local",
        "name": "Ollama",
        "type": "ollama",
        "key_env": "",
        "model_env": "OLLAMA_MODEL",
        "default_model": "llama3",
    },
]


class ProviderConfigurationError(ValueError):
    pass


def unknown_provider_message(model_name: str) -> str:
    model = str(model_name or "").strip() or "unknown"
    return f"Provider type unknown for model {model}. Run /model add to configure a provider."


def infer_provider_type(model_name: str) -> str:
    model = str(model_name or "").strip().lower()
    if not model:
        return ""
    if model.startswith(("llama-", "gemma-", "mixtral-")):
        return "groq"
    if model.startswith(("gpt-", "o1-", "o3-")) or model in {"o1", "o3"}:
        return "openai"
    if model.startswith("claude-"):
        return "anthropic"
    if model.startswith("gemini-"):
        return "gemini"
    return ""


def _ensure_dir() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _env_file_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".env"


def _read_env_file() -> dict[str, str]:
    path = _env_file_path()
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _env_value(*keys: str) -> str:
    env_file = _read_env_file()
    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
        value = env_file.get(key, "").strip()
        if value:
            return value
    return ""


def _normalize_provider(provider: dict[str, Any], *, index: int = 0) -> dict[str, Any]:
    model_name = str(provider.get("model", "") or "").strip()
    provider_type = str(provider.get("type") or provider.get("provider") or "").strip().lower()
    if provider_type in {"", "unassigned", "none", "null"}:
        provider_type = infer_provider_type(model_name)
    defaults = PROVIDER_TYPES.get(provider_type, PROVIDER_TYPES["custom"])
    normalized = {
        "id": str(provider.get("id") or f"{provider_type}-{index + 1}").strip(),
        "name": str(provider.get("name") or defaults["name"]).strip() or defaults["name"],
        "type": provider_type,
        "provider": provider_type,
        "api_key": str(provider.get("api_key", "") or "").strip(),
        "base_url": str(provider.get("base_url", defaults.get("base_url", "")) or "").strip(),
        "model": model_name,
        "enabled": bool(provider.get("enabled", True)),
        "is_default": bool(provider.get("is_default", False)),
    }
    if provider_type == "ollama" and not normalized["api_key"]:
        normalized["api_key"] = "ollama"
    if provider_type == "lmstudio" and not normalized["api_key"]:
        normalized["api_key"] = "lmstudio"
    return normalized


def load_providers() -> list[dict[str, Any]]:
    _ensure_dir()
    if not CONFIG_PATH.exists():
        migrated = migrate_env_to_providers()
        if migrated:
            return migrated
        return []
    try:
        rows = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(rows, list):
        return []
    providers = [_normalize_provider(row, index=index) for index, row in enumerate(rows) if isinstance(row, dict)]
    if providers and not any(item.get("is_default") for item in providers):
        providers[0]["is_default"] = True
        save_providers(providers)
    return providers


def save_providers(providers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _ensure_dir()
    normalized = [_normalize_provider(item, index=index) for index, item in enumerate(providers)]
    enabled = [item for item in normalized if item.get("enabled", True)]
    default_id = next((item["id"] for item in normalized if item.get("is_default")), "")
    if not default_id and enabled:
        default_id = enabled[0]["id"]
    for item in normalized:
        item["is_default"] = bool(default_id and item["id"] == default_id)
    CONFIG_PATH.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return normalized


def _provider_from_env() -> dict[str, Any]:
    env_provider = _env_value("AI_PROVIDER").strip().lower()
    if not env_provider:
        return _unconfigured_provider()
    spec = next((item for item in ENV_PROVIDER_SPECS if item["env_provider"] == env_provider), None)
    if spec is None:
        model_name = _env_value("GROQ_MODEL", "OPENAI_MODEL", "ANTHROPIC_MODEL", "GOOGLE_GEMINI_MODEL")
        inferred = infer_provider_type(model_name)
        if not inferred:
            return _unconfigured_provider()
        env_provider = inferred
        spec = next((item for item in ENV_PROVIDER_SPECS if item["env_provider"] == env_provider), None)
        if spec is None:
            return _unconfigured_provider()
    api_key = _env_value(spec["key_env"]) if spec["key_env"] else ""
    model_name = _env_value(spec["model_env"]) or spec["default_model"]
    return _normalize_provider(
        {
            "id": spec["id"],
            "name": spec["name"],
            "type": spec["type"],
            "api_key": api_key,
            "base_url": PROVIDER_TYPES[spec["type"]]["base_url"],
            "model": model_name,
            "enabled": bool(api_key or spec["type"] in {"ollama", "lmstudio"}),
            "is_default": True,
        }
    )


def _unconfigured_provider() -> dict[str, Any]:
    return {
        "id": "unconfigured",
        "name": "Unconfigured",
        "type": "unconfigured",
        "provider": "unconfigured",
        "api_key": "",
        "base_url": "",
        "model": "",
        "enabled": False,
        "is_default": True,
        "no_provider_configured": True,
        "error": "No provider configured. Run: /model add",
    }


def get_default() -> dict[str, Any]:
    providers = load_providers()
    for item in providers:
        if item.get("enabled", True) and item.get("is_default"):
            return item
    for item in providers:
        if item.get("enabled", True):
            return item
    env_provider = _provider_from_env()
    if not env_provider.get("no_provider_configured"):
        return env_provider
    return _unconfigured_provider()


def add_provider(data: dict[str, Any]) -> dict[str, Any]:
    providers = load_providers()
    provider = _normalize_provider(data, index=len(providers))
    providers = [item for item in providers if item["id"] != provider["id"]]
    if provider.get("is_default") or not providers:
        for item in providers:
            item["is_default"] = False
        provider["is_default"] = True
    providers.append(provider)
    save_providers(providers)
    return provider


def update_provider(provider_id: str, data: dict[str, Any]) -> dict[str, Any]:
    providers = load_providers()
    updated: dict[str, Any] | None = None
    for index, item in enumerate(providers):
        if item["id"] != provider_id:
            continue
        merged = dict(item)
        merged.update(data)
        merged["id"] = provider_id
        updated = _normalize_provider(merged, index=index)
        providers[index] = updated
        break
    if updated is None:
        raise KeyError(provider_id)
    if updated.get("is_default"):
        for item in providers:
            item["is_default"] = item["id"] == provider_id
    save_providers(providers)
    return updated


def remove_provider(provider_id: str) -> bool:
    providers = load_providers()
    filtered = [item for item in providers if item["id"] != provider_id]
    if len(filtered) == len(providers):
        return False
    save_providers(filtered)
    return True


def set_default(provider_id: str) -> dict[str, Any]:
    providers = load_providers()
    found: dict[str, Any] | None = None
    for item in providers:
        item["is_default"] = item["id"] == provider_id
        if item["is_default"]:
            found = item
    if found is None:
        raise KeyError(provider_id)
    save_providers(providers)
    return found


def _openai_client(provider: dict[str, Any]):
    import openai

    provider_type = provider["type"]
    api_key = provider.get("api_key", "") or provider_type
    base_url = provider.get("base_url", "")
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return openai.OpenAI(**kwargs)


def _provider_by_id(provider_id: str) -> dict[str, Any]:
    for item in load_providers():
        if item["id"] == provider_id:
            return item
    raise KeyError(provider_id)


def test_provider(provider_id: str) -> dict[str, Any]:
    provider = _provider_by_id(provider_id)
    started = time.perf_counter()
    try:
        provider_type = provider["type"]
        if provider_type == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=provider["api_key"])
            client.messages.create(
                model=provider["model"] or "claude-sonnet-4-5",
                max_tokens=4,
                messages=[{"role": "user", "content": "ping"}],
            )
        elif provider_type == "gemini":
            import google.generativeai as genai

            genai.configure(api_key=provider["api_key"])
            model = genai.GenerativeModel(provider["model"] or "gemini-2.0-flash")
            model.generate_content("ping")
        elif provider_type == "cohere":
            import cohere

            client = cohere.ClientV2(api_key=provider["api_key"])
            client.models.list(page_size=1)
        else:
            client = _openai_client(provider)
            if provider_type in {"ollama", "lmstudio"}:
                client.models.list()
            else:
                client.chat.completions.create(
                    model=provider["model"],
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=4,
                )
        latency = int((time.perf_counter() - started) * 1000)
        return {"ok": True, "latency": latency, "error": ""}
    except Exception as exc:
        latency = int((time.perf_counter() - started) * 1000)
        return {"ok": False, "latency": latency, "error": str(exc)}


def list_models(provider_id: str) -> list[str]:
    provider = _provider_by_id(provider_id)
    provider_type = provider["type"]
    if provider_type == "ollama":
        base_url = provider.get("base_url", PROVIDER_TYPES["ollama"]["base_url"]).rstrip("/")
        api_base = base_url[:-3] if base_url.endswith("/v1") else base_url
        response = httpx.get(urljoin(api_base + "/", "api/tags"), timeout=10.0)
        response.raise_for_status()
        payload = response.json()
        return sorted(str(item.get("name", "")).strip() for item in payload.get("models", []) if item.get("name"))
    if provider_type == "gemini":
        import google.generativeai as genai

        genai.configure(api_key=provider["api_key"])
        models = genai.list_models()
        return sorted(
            item.name.replace("models/", "")
            for item in models
            if "generateContent" in getattr(item, "supported_generation_methods", [])
        )
    if provider_type == "anthropic":
        client = _openai_client(
            {
                "type": "custom",
                "api_key": provider["api_key"],
                "base_url": "https://api.anthropic.com/v1/",
            }
        )
        try:
            response = client.models.list()
            rows = getattr(response, "data", []) or []
            return sorted(str(getattr(item, "id", "")).strip() for item in rows if getattr(item, "id", ""))
        except Exception:
            return [provider.get("model", "")] if provider.get("model") else []
    client = _openai_client(provider)
    response = client.models.list()
    rows = getattr(response, "data", []) or []
    return sorted(str(getattr(item, "id", "")).strip() for item in rows if getattr(item, "id", ""))


def migrate_env_to_providers() -> list[dict[str, Any]]:
    if CONFIG_PATH.exists():
        return load_providers()
    env_provider = _env_value("AI_PROVIDER").strip().lower()
    if not env_provider:
        return []
    providers: list[dict[str, Any]] = []
    for spec in ENV_PROVIDER_SPECS:
        api_key = _env_value(spec["key_env"]) if spec["key_env"] else ""
        model = _env_value(spec["model_env"]) or spec["default_model"]
        provider = {
            "id": spec["id"],
            "name": spec["name"],
            "type": spec["type"],
            "api_key": api_key,
            "base_url": PROVIDER_TYPES[spec["type"]]["base_url"],
            "model": model,
            "enabled": bool(api_key or spec["type"] in {"ollama", "lmstudio"}),
            "is_default": spec["env_provider"] == env_provider,
        }
        if provider["enabled"] or provider["is_default"]:
            providers.append(provider)
    if not providers:
        return []
    saved = save_providers(providers)
    return saved
