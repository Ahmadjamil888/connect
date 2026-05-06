import json
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml
from core import model_manager

CONFIG_DIR = Path.home() / ".connectai"
CONFIG_PATH = CONFIG_DIR / "config.yaml"
LEGACY_CONFIG_PATH = CONFIG_DIR / "config.json"


def _fallback_paths() -> tuple[Path, Path, Path]:
    base = Path.cwd() / ".connectai"
    return base, base / "config.yaml", base / "config.json"

PROVIDER_DEFAULTS = {
    "anthropic": {
        "model": "claude-sonnet-4-5",
        "api_key": "",
    },
    "groq": {
        "model": "llama-3.3-70b-versatile",
        "api_key": "",
        "base_url": "https://api.groq.com/openai/v1",
    },
    "openai": {
        "model": "gpt-4o",
        "api_key": "",
    },
    "openrouter": {
        "model": "openai/gpt-4o-mini",
        "api_key": "",
        "base_url": "https://openrouter.ai/api/v1",
    },
    "gemini": {
        "model": "gemini-2.0-flash",
        "api_key": "",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    },
    "huggingface": {
        "model": "meta-llama/Llama-3.1-8B-Instruct:cerebras",
        "api_key": "",
        "base_url": "https://router.huggingface.co/v1",
    },
    "ollama": {
        "model": "llama3.1",
        "base_url": "http://localhost:11434",
        "api_key": "ollama",
    },
    "azure": {
        "model": "gpt-4o",
        "api_key": "",
        "base_url": "",
        "api_version": "2024-02-01",
    },
    "bedrock": {
        "model": "anthropic.claude-sonnet-4-5-20251101-v1:0",
        "aws_access_key_id": "",
        "aws_secret_access_key": "",
        "aws_region": "us-east-1",
    },
    "nvidia": {
        "model": "meta/llama-3.1-70b-instruct",
        "api_key": "",
        "base_url": "https://integrate.api.nvidia.com/v1",
    },
    "gcp": {
        "model": "claude-sonnet-4-5@20251101",
        "api_key": "",
        "project_id": "",
        "location": "us-east5",
    },
}


def _read_env_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            current_key, value = line.split("=", 1)
            if current_key.strip() == key:
                return value.strip().strip('"').strip("'")
    except Exception:
        return ""
    return ""


def _env_value(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
    candidates = [
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / "connect frontend" / ".env",
    ]
    for candidate in candidates:
        for key in keys:
            value = _read_env_value(candidate, key)
            if value:
                return value
    return ""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def load_config() -> dict[str, Any]:
    global CONFIG_DIR, CONFIG_PATH, LEGACY_CONFIG_PATH
    cfg = _read_yaml(CONFIG_PATH)
    if cfg:
        return cfg
    legacy = _read_json(LEGACY_CONFIG_PATH)
    if legacy:
        save_config(legacy)
        return legacy
    fallback_dir, fallback_yaml, fallback_json = _fallback_paths()
    if fallback_yaml.exists() or fallback_json.exists():
        CONFIG_DIR, CONFIG_PATH, LEGACY_CONFIG_PATH = fallback_dir, fallback_yaml, fallback_json
        cfg = _read_yaml(CONFIG_PATH)
        if cfg:
            return cfg
        legacy = _read_json(LEGACY_CONFIG_PATH)
        if legacy:
            save_config(legacy)
            return legacy
    return {}


def save_config(cfg: dict[str, Any]):
    global CONFIG_DIR, CONFIG_PATH, LEGACY_CONFIG_PATH
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            yaml.safe_dump(cfg, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
    except PermissionError:
        CONFIG_DIR, CONFIG_PATH, LEGACY_CONFIG_PATH = _fallback_paths()
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            yaml.safe_dump(cfg, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )


def _writable_root(path: Path) -> Path | None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return path
    except Exception:
        return None


def resolve_runtime_state_root(workspace: str | Path | None = None) -> Path:
    cfg = load_config()
    existing = str(cfg.get("runtime_state_root", "")).strip()
    if existing:
        resolved = _writable_root(Path(existing))
        if resolved is not None:
            return resolved

    workspace_root = Path(workspace) if workspace else Path(cfg.get("workspace", str(Path.home() / "imos_workspace")))
    candidates = [
        workspace_root / ".connectai",
        Path(os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "connectai",
        Path(tempfile.gettempdir()) / "connectai",
    ]
    for candidate in candidates:
        resolved = _writable_root(candidate)
        if resolved is not None:
            cfg["runtime_state_root"] = str(resolved)
            save_config(cfg)
            return resolved

    fallback = Path.cwd() / ".connectai"
    fallback.mkdir(parents=True, exist_ok=True)
    cfg["runtime_state_root"] = str(fallback)
    save_config(cfg)
    return fallback


def _env_default_model() -> dict[str, Any]:
    migrated_default = model_manager.get_default()
    if migrated_default:
        return dict(migrated_default)
    provider = os.getenv("AI_PROVIDER", "").strip().lower()
    if not provider:
        return dict(model_manager.get_default())
    defaults = dict(PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["anthropic"]))
    defaults["provider"] = provider
    defaults["type"] = provider
    key_map = {
        "anthropic": _env_value("ANTHROPIC_API_KEY"),
        "groq": _env_value("GROQ_API_KEY"),
        "openai": _env_value("OPENAI_API_KEY"),
        "openrouter": _env_value("OPENROUTER_API_KEY"),
        "gemini": _env_value("GOOGLE_AI_API_KEY", "GOOGLE_GEMINI_API_KEY"),
        "huggingface": _env_value("HF_TOKEN", "HUGGINGFACE_API_KEY"),
        "nvidia": _env_value("NVIDIA_API_KEY"),
    }
    if provider in key_map:
        defaults["api_key"] = key_map[provider]
    return defaults


def get_model_config() -> dict[str, Any]:
    migrated_default = model_manager.get_default()
    if migrated_default:
        return dict(migrated_default)
    cfg = load_config()
    model = cfg.get("model", {})
    if model and model.get("provider"):
        provider = str(model["provider"]).strip().lower()
        defaults = dict(PROVIDER_DEFAULTS.get(provider, {}))
        defaults.update(model)
        defaults["provider"] = provider
        defaults["type"] = str(defaults.get("type") or provider).strip().lower()
        if provider == "anthropic" and not str(defaults.get("api_key", "")).strip():
            defaults["api_key"] = _env_value("ANTHROPIC_API_KEY")
        elif provider == "groq" and not str(defaults.get("api_key", "")).strip():
            defaults["api_key"] = _env_value("GROQ_API_KEY")
        elif provider == "openai" and not str(defaults.get("api_key", "")).strip():
            defaults["api_key"] = _env_value("OPENAI_API_KEY")
        elif provider == "openrouter" and not str(defaults.get("api_key", "")).strip():
            defaults["api_key"] = _env_value("OPENROUTER_API_KEY")
        elif provider == "gemini" and not str(defaults.get("api_key", "")).strip():
            defaults["api_key"] = _env_value("GOOGLE_AI_API_KEY", "GOOGLE_GEMINI_API_KEY")
        elif provider == "huggingface" and not str(defaults.get("api_key", "")).strip():
            defaults["api_key"] = _env_value("HF_TOKEN", "HUGGINGFACE_API_KEY")
        elif provider == "nvidia" and not str(defaults.get("api_key", "")).strip():
            defaults["api_key"] = _env_value("NVIDIA_API_KEY")
        elif provider == "gcp" and not str(defaults.get("project_id", "")).strip():
            defaults["project_id"] = _env_value("GOOGLE_CLOUD_PROJECT", "GCP_PROJECT_ID")
        return defaults
    return _env_default_model()


def save_model_config(model_cfg: dict[str, Any]):
    cfg = load_config()
    cfg["model"] = model_cfg
    save_config(cfg)


def get_tokens() -> dict[str, Any]:
    return load_config().get("tokens", {})


def list_providers():
    configured = [item["id"] for item in model_manager.load_providers()]
    if configured:
        return configured
    return list(PROVIDER_DEFAULTS.keys())


def get_provider_defaults(provider: str) -> dict[str, Any]:
    provider_row = next((item for item in model_manager.load_providers() if item["id"] == provider or item["type"] == provider), None)
    if provider_row is not None:
        return dict(provider_row)
    return dict(PROVIDER_DEFAULTS.get(provider, {}))


def _require_api_key(provider: str, api_key: str):
    if not api_key.strip():
        raise ValueError(f"{provider} API key is empty. Run /setup to configure it.")


def get_client(model_config: dict[str, Any]):
    effective = dict(model_manager.get_default() or {})
    effective.update(model_config or {})
    provider = str(effective.get("type") or effective.get("provider") or "").strip().lower()
    if not provider and effective.get("model"):
        provider = model_manager.infer_provider_type(str(effective.get("model", "")))
    if not provider:
        raise model_manager.ProviderConfigurationError(model_manager.unknown_provider_message(str(effective.get("model", ""))))
    if provider == "unconfigured" or effective.get("no_provider_configured"):
        raise model_manager.ProviderConfigurationError("No AI provider configured. Run /model add to set one up.")
    effective["provider"] = provider
    effective["type"] = provider
    api_key = str(model_config.get("api_key", "")).strip()
    if not api_key:
        api_key = str(effective.get("api_key", "")).strip()
    model_config = effective

    if provider == "anthropic":
        import anthropic

        _require_api_key("Anthropic", api_key)
        return anthropic.Anthropic(api_key=api_key)

    if provider == "groq":
        import openai

        _require_api_key("Groq", api_key)
        return openai.OpenAI(
            api_key=api_key,
            base_url=model_config.get("base_url", PROVIDER_DEFAULTS["groq"]["base_url"]),
        )

    if provider == "openai":
        import openai

        _require_api_key("OpenAI", api_key)
        kwargs = {"api_key": api_key}
        if model_config.get("base_url"):
            kwargs["base_url"] = model_config.get("base_url")
        return openai.OpenAI(**kwargs)

    if provider == "openrouter":
        import openai

        _require_api_key("OpenRouter", api_key)
        return openai.OpenAI(
            api_key=api_key,
            base_url=model_config.get("base_url", PROVIDER_DEFAULTS["openrouter"]["base_url"]),
        )

    if provider == "gemini":
        import openai

        _require_api_key("Gemini", api_key)
        return openai.OpenAI(
            api_key=api_key,
            base_url=model_config.get("base_url", PROVIDER_DEFAULTS["gemini"]["base_url"]),
        )

    if provider == "huggingface":
        import openai

        _require_api_key("Hugging Face", api_key)
        return openai.OpenAI(
            api_key=api_key,
            base_url=model_config.get("base_url", PROVIDER_DEFAULTS["huggingface"]["base_url"]),
        )

    if provider == "ollama":
        import openai

        base = model_config.get("base_url", PROVIDER_DEFAULTS["ollama"]["base_url"])
        base_url = str(base).rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        return openai.OpenAI(api_key="ollama", base_url=base_url)

    if provider == "lmstudio":
        import openai

        base = model_config.get("base_url", "http://localhost:1234/v1")
        base_url = str(base).rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        return openai.OpenAI(api_key="lmstudio", base_url=base_url)

    if provider == "together":
        import openai

        _require_api_key("Together", api_key)
        return openai.OpenAI(api_key=api_key, base_url=model_config.get("base_url", "https://api.together.xyz/v1"))

    if provider == "mistral":
        import openai

        _require_api_key("Mistral", api_key)
        return openai.OpenAI(api_key=api_key, base_url=model_config.get("base_url", "https://api.mistral.ai/v1"))

    if provider == "cohere":
        import openai

        _require_api_key("Cohere", api_key)
        return openai.OpenAI(api_key=api_key, base_url=model_config.get("base_url", "https://api.cohere.com/v1"))

    if provider == "custom":
        import openai

        custom_base = str(model_config.get("base_url", "")).strip()
        if not custom_base:
            raise ValueError("Custom provider base_url is empty.")
        return openai.OpenAI(api_key=api_key or "custom", base_url=custom_base)

    if provider == "azure":
        import openai

        _require_api_key("Azure", api_key)
        return openai.AzureOpenAI(
            api_key=api_key,
            azure_endpoint=str(model_config.get("base_url", "")),
            api_version=str(model_config.get("api_version", "2024-02-01")),
        )

    if provider == "nvidia":
        import openai

        _require_api_key("NVIDIA", api_key)
        return openai.OpenAI(
            api_key=api_key,
            base_url=model_config.get("base_url", PROVIDER_DEFAULTS["nvidia"]["base_url"]),
        )

    if provider == "bedrock":
        import boto3

        return boto3.client(
            "bedrock-runtime",
            region_name=model_config.get("aws_region", "us-east-1"),
            aws_access_key_id=model_config.get("aws_access_key_id"),
            aws_secret_access_key=model_config.get("aws_secret_access_key"),
        )

    if provider == "gcp":
        import anthropic

        return anthropic.AnthropicVertex(
            project_id=model_config["project_id"],
            region=model_config.get("location", "us-east5"),
        )

    raise ValueError(f"Unknown provider: {provider}")


def is_configured() -> bool:
    try:
        cfg = get_model_config()
        provider = cfg.get("provider") or cfg.get("type", "")
        if not provider:
            return False
        if provider in {"anthropic", "groq", "openai", "openrouter", "gemini", "huggingface", "nvidia", "together", "mistral", "cohere"}:
            return bool(str(cfg.get("api_key", "")).strip())
        if provider in {"ollama", "lmstudio"}:
            return True
        if provider == "custom":
            return bool(str(cfg.get("base_url", "")).strip())
        if provider == "azure":
            return bool(str(cfg.get("api_key", "")).strip() and str(cfg.get("base_url", "")).strip())
        if provider == "bedrock":
            return bool(str(cfg.get("aws_access_key_id", "")).strip())
        if provider == "gcp":
            return bool(str(cfg.get("project_id", "")).strip())
        return False
    except Exception:
        return False
