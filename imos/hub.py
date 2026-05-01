from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from config.config import load_config, save_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().upper())
    return value.strip("_") or "VALUE"


def _read_env() -> dict[str, str]:
    data: dict[str, str] = {}
    if not ENV_PATH.exists():
        return data
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _write_env_key(key: str, value: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    updated = False
    new_lines: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


VOICE_PROFILES = [
    {"id": "jarvis", "label": "David / Jarvis"},
    {"id": "friday", "label": "Zira / Friday"},
]


MODEL_CONNECTIONS = [
    {
        "provider": "anthropic",
        "name": "Anthropic",
        "category": "model-cloud",
        "description": "Claude models over Anthropic API.",
        "fields": [
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "model", "label": "Default model", "required": True, "default": "claude-sonnet-4-5"},
        ],
    },
    {
        "provider": "openai",
        "name": "OpenAI",
        "category": "model-cloud",
        "description": "GPT models over OpenAI API.",
        "fields": [
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "model", "label": "Default model", "required": True, "default": "gpt-4o"},
        ],
    },
    {
        "provider": "groq",
        "name": "Groq",
        "category": "model-cloud",
        "description": "Fast OpenAI-compatible inference.",
        "fields": [
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "model", "label": "Default model", "required": True, "default": "llama-3.3-70b-versatile"},
        ],
    },
    {
        "provider": "openrouter",
        "name": "OpenRouter",
        "category": "model-cloud",
        "description": "Multi-provider model gateway.",
        "fields": [
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "model", "label": "Default model", "required": True, "default": "openai/gpt-4o-mini"},
        ],
    },
    {
        "provider": "gemini",
        "name": "Google Gemini",
        "category": "model-cloud",
        "description": "Gemini via Google AI API.",
        "fields": [
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "model", "label": "Default model", "required": True, "default": "gemini-2.0-flash"},
        ],
    },
    {
        "provider": "azure",
        "name": "Azure OpenAI",
        "category": "model-cloud",
        "description": "Azure-hosted OpenAI deployments.",
        "fields": [
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "base_url", "label": "Endpoint URL", "required": True},
            {"key": "model", "label": "Deployment name", "required": True},
            {"key": "api_version", "label": "API version", "default": "2024-02-01"},
        ],
    },
    {
        "provider": "bedrock",
        "name": "AWS Bedrock",
        "category": "model-cloud",
        "description": "Managed models on AWS Bedrock.",
        "fields": [
            {"key": "aws_access_key_id", "label": "Access key ID", "secret": True},
            {"key": "aws_secret_access_key", "label": "Secret access key", "secret": True},
            {"key": "aws_region", "label": "AWS region", "default": "us-east-1"},
            {"key": "model", "label": "Model ID", "required": True, "default": "anthropic.claude-sonnet-4-5-20251101-v1:0"},
        ],
    },
    {
        "provider": "gcp",
        "name": "Google Vertex AI",
        "category": "model-cloud",
        "description": "Vertex-hosted model endpoints.",
        "fields": [
            {"key": "project_id", "label": "Project ID", "required": True},
            {"key": "location", "label": "Region", "default": "us-east5"},
            {"key": "model", "label": "Model name", "required": True, "default": "claude-sonnet-4-5@20251101"},
        ],
    },
    {
        "provider": "nvidia",
        "name": "NVIDIA NIM",
        "category": "model-cloud",
        "description": "NVIDIA-hosted inference.",
        "fields": [
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "model", "label": "Default model", "required": True, "default": "meta/llama-3.1-70b-instruct"},
        ],
    },
    {
        "provider": "huggingface",
        "name": "Hugging Face Router",
        "category": "model-cloud",
        "description": "HF routed model endpoints.",
        "fields": [
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "model", "label": "Model ID", "required": True, "default": "meta-llama/Llama-3.1-8B-Instruct:cerebras"},
        ],
    },
    {
        "provider": "ollama",
        "name": "Ollama",
        "category": "model-local",
        "description": "Local Ollama runtime.",
        "fields": [
            {"key": "base_url", "label": "Endpoint URL", "required": True, "default": "http://localhost:11434"},
            {"key": "model", "label": "Default model", "required": True, "default": "llama3.1"},
        ],
    },
    {
        "provider": "lmstudio",
        "name": "LM Studio",
        "category": "model-local",
        "description": "LM Studio OpenAI-compatible server.",
        "fields": [
            {"key": "base_url", "label": "Endpoint URL", "required": True, "default": "http://localhost:1234/v1"},
            {"key": "model", "label": "Default model", "required": True, "default": "local-model"},
        ],
    },
    {
        "provider": "vllm",
        "name": "vLLM / OpenAI-Compatible",
        "category": "model-local",
        "description": "Any local or hosted OpenAI-compatible endpoint.",
        "fields": [
            {"key": "base_url", "label": "Endpoint URL", "required": True},
            {"key": "api_key", "label": "API key", "secret": True, "default": "local"},
            {"key": "model", "label": "Default model", "required": True},
        ],
    },
    {
        "provider": "custom-api",
        "name": "Custom Model API",
        "category": "model-custom",
        "description": "Generic model provider placeholder for unsupported vendors.",
        "fields": [
            {"key": "base_url", "label": "Endpoint URL", "required": True},
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "model", "label": "Model name", "required": True},
            {"key": "notes", "label": "Notes"},
        ],
    },
]


APP_CONNECTIONS = [
    {
        "provider": "telegram",
        "name": "Telegram Bot",
        "category": "messaging",
        "description": "Bot token plus default chat target.",
        "fields": [
            {"key": "bot_token", "label": "Bot token", "secret": True, "required": True},
            {"key": "chat_id", "label": "Default chat ID"},
        ],
    },
    {
        "provider": "discord",
        "name": "Discord",
        "category": "messaging",
        "description": "Bot token and webhook support.",
        "fields": [
            {"key": "bot_token", "label": "Bot token", "secret": True},
            {"key": "webhook_url", "label": "Webhook URL", "secret": True},
            {"key": "channel_id", "label": "Channel ID"},
        ],
    },
    {
        "provider": "slack",
        "name": "Slack",
        "category": "messaging",
        "description": "Bot token, signing secret, and default channel.",
        "fields": [
            {"key": "bot_token", "label": "Bot token", "secret": True},
            {"key": "signing_secret", "label": "Signing secret", "secret": True},
            {"key": "channel", "label": "Default channel"},
        ],
    },
    {
        "provider": "teams",
        "name": "Microsoft Teams",
        "category": "messaging",
        "description": "Incoming webhook or bot app setup.",
        "fields": [
            {"key": "webhook_url", "label": "Webhook URL", "secret": True},
            {"key": "tenant_id", "label": "Tenant ID"},
        ],
    },
    {
        "provider": "whatsapp-business",
        "name": "WhatsApp Business",
        "category": "messaging",
        "description": "Meta WhatsApp Business API.",
        "fields": [
            {"key": "access_token", "label": "Access token", "secret": True},
            {"key": "phone_number_id", "label": "Phone number ID", "required": True},
            {"key": "verify_token", "label": "Verify token", "secret": True},
        ],
    },
    {
        "provider": "twilio-sms",
        "name": "Twilio SMS",
        "category": "messaging",
        "description": "Programmable SMS and voice workflows.",
        "fields": [
            {"key": "account_sid", "label": "Account SID", "required": True},
            {"key": "auth_token", "label": "Auth token", "secret": True, "required": True},
            {"key": "from_number", "label": "From number"},
        ],
    },
    {
        "provider": "gmail",
        "name": "Gmail",
        "category": "email",
        "description": "SMTP/app password based email sending.",
        "fields": [
            {"key": "email", "label": "Email address", "required": True},
            {"key": "app_password", "label": "App password", "secret": True, "required": True},
            {"key": "smtp_server", "label": "SMTP server", "default": "smtp.gmail.com"},
        ],
    },
    {
        "provider": "outlook",
        "name": "Outlook / Microsoft 365",
        "category": "email",
        "description": "SMTP or Graph-ready base fields.",
        "fields": [
            {"key": "email", "label": "Email address", "required": True},
            {"key": "password", "label": "Password / app password", "secret": True},
            {"key": "smtp_server", "label": "SMTP server", "default": "smtp.office365.com"},
        ],
    },
    {
        "provider": "x",
        "name": "X / Twitter",
        "category": "social",
        "description": "Posting and reading via X API.",
        "fields": [
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "api_secret", "label": "API secret", "secret": True},
            {"key": "access_token", "label": "Access token", "secret": True},
            {"key": "access_token_secret", "label": "Access token secret", "secret": True},
        ],
    },
    {
        "provider": "linkedin",
        "name": "LinkedIn",
        "category": "social",
        "description": "Organization posting and content workflows.",
        "fields": [
            {"key": "client_id", "label": "Client ID"},
            {"key": "client_secret", "label": "Client secret", "secret": True},
            {"key": "access_token", "label": "Access token", "secret": True},
            {"key": "organization_urn", "label": "Organization URN"},
        ],
    },
    {
        "provider": "facebook-pages",
        "name": "Facebook Pages",
        "category": "social",
        "description": "Page publishing and inbox automations.",
        "fields": [
            {"key": "page_access_token", "label": "Page access token", "secret": True, "required": True},
            {"key": "page_id", "label": "Page ID", "required": True},
        ],
    },
    {
        "provider": "instagram-business",
        "name": "Instagram Business",
        "category": "social",
        "description": "Business account posting and insights.",
        "fields": [
            {"key": "access_token", "label": "Access token", "secret": True, "required": True},
            {"key": "ig_user_id", "label": "Instagram user ID", "required": True},
        ],
    },
    {
        "provider": "youtube",
        "name": "YouTube",
        "category": "social",
        "description": "Channel publishing and moderation.",
        "fields": [
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "channel_id", "label": "Channel ID"},
            {"key": "refresh_token", "label": "Refresh token", "secret": True},
        ],
    },
    {
        "provider": "tiktok",
        "name": "TikTok",
        "category": "social",
        "description": "TikTok Business/API setup.",
        "fields": [
            {"key": "client_key", "label": "Client key"},
            {"key": "client_secret", "label": "Client secret", "secret": True},
            {"key": "access_token", "label": "Access token", "secret": True},
        ],
    },
    {
        "provider": "reddit",
        "name": "Reddit",
        "category": "social",
        "description": "Subreddit posting and inbox automation.",
        "fields": [
            {"key": "client_id", "label": "Client ID", "required": True},
            {"key": "client_secret", "label": "Client secret", "secret": True, "required": True},
            {"key": "username", "label": "Username"},
            {"key": "password", "label": "Password", "secret": True},
            {"key": "subreddit", "label": "Default subreddit"},
        ],
    },
    {
        "provider": "github",
        "name": "GitHub",
        "category": "devtools",
        "description": "Repo, PR, and issue automation.",
        "fields": [
            {"key": "token", "label": "Token", "secret": True, "required": True},
            {"key": "repo", "label": "Default repo"},
        ],
    },
    {
        "provider": "notion",
        "name": "Notion",
        "category": "productivity",
        "description": "Pages, databases, and docs workflows.",
        "fields": [
            {"key": "token", "label": "Internal integration token", "secret": True, "required": True},
            {"key": "database_id", "label": "Default database ID"},
        ],
    },
    {
        "provider": "airtable",
        "name": "Airtable",
        "category": "productivity",
        "description": "Table-based data automations.",
        "fields": [
            {"key": "token", "label": "Personal access token", "secret": True, "required": True},
            {"key": "base_id", "label": "Base ID"},
            {"key": "table", "label": "Default table"},
        ],
    },
    {
        "provider": "zapier",
        "name": "Zapier",
        "category": "automation",
        "description": "Send events into Zapier webhooks.",
        "fields": [
            {"key": "webhook_url", "label": "Webhook URL", "secret": True, "required": True},
        ],
    },
    {
        "provider": "make",
        "name": "Make",
        "category": "automation",
        "description": "Trigger Make scenarios via webhook.",
        "fields": [
            {"key": "webhook_url", "label": "Webhook URL", "secret": True, "required": True},
        ],
    },
    {
        "provider": "n8n",
        "name": "n8n",
        "category": "automation",
        "description": "Self-hosted automation workflows.",
        "fields": [
            {"key": "base_url", "label": "Base URL", "required": True},
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "webhook_url", "label": "Webhook URL", "secret": True},
        ],
    },
    {
        "provider": "webhook",
        "name": "Generic Webhook",
        "category": "automation",
        "description": "Universal HTTP output for any app.",
        "fields": [
            {"key": "url", "label": "Webhook URL", "required": True},
            {"key": "method", "label": "HTTP method", "default": "POST"},
            {"key": "auth_header", "label": "Authorization header", "secret": True},
        ],
    },
    {
        "provider": "custom-app",
        "name": "Custom App / API",
        "category": "custom",
        "description": "Fallback connector for any unsupported app.",
        "fields": [
            {"key": "base_url", "label": "Base URL", "required": True},
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "notes", "label": "Notes / integration guide"},
        ],
    },
]


def _catalog() -> list[dict[str, Any]]:
    return [*APP_CONNECTIONS, *MODEL_CONNECTIONS]


def _config_root() -> dict[str, Any]:
    cfg = load_config()
    automation = cfg.get("automation")
    if not isinstance(automation, dict):
        automation = {}
        cfg["automation"] = automation
    if not isinstance(automation.get("connections"), list):
        automation["connections"] = []
    if not isinstance(automation.get("workflows"), list):
        automation["workflows"] = []
    if not isinstance(automation.get("voice"), dict):
        automation["voice"] = {}
    return cfg


def get_voice_settings() -> dict[str, Any]:
    cfg = _config_root()
    voice = cfg["automation"]["voice"]
    return {
        "enabled": bool(voice.get("enabled", True)),
        "voice": str(voice.get("voice", "jarvis")).strip() or "jarvis",
        "rate": int(voice.get("rate", 175) or 175),
        "wake_words": voice.get("wake_words", ["imos", "hey imos"]),
        "profiles": VOICE_PROFILES,
    }


def save_voice_settings(*, enabled: bool, voice: str, rate: int, wake_words: list[str] | None = None) -> dict[str, Any]:
    cfg = _config_root()
    cfg["automation"]["voice"] = {
        "enabled": bool(enabled),
        "voice": voice or "jarvis",
        "rate": int(rate or 175),
        "wake_words": wake_words or ["imos", "hey imos"],
    }
    save_config(cfg)
    return get_voice_settings()


def list_connection_catalog() -> list[dict[str, Any]]:
    return _catalog()


def list_model_catalog() -> list[dict[str, Any]]:
    return MODEL_CONNECTIONS


def _find_catalog_entry(provider: str) -> dict[str, Any] | None:
    for item in _catalog():
        if item["provider"] == provider:
            return item
    return None


def _field_env_key(provider: str, field: dict[str, Any]) -> str:
    return field.get("env_key") or f"IMOS_{_slug(provider)}_{_slug(field['key'])}"


def list_connections() -> list[dict[str, Any]]:
    cfg = _config_root()
    env = _read_env()
    items: list[dict[str, Any]] = []
    for raw in cfg["automation"]["connections"]:
        if not isinstance(raw, dict):
            continue
        provider = str(raw.get("provider", "")).strip()
        entry = _find_catalog_entry(provider)
        if not entry:
            continue
        values = dict(raw.get("values", {}) or {})
        configured = True
        returned_values: dict[str, str] = {}
        for field in entry.get("fields", []):
            key = field["key"]
            if field.get("secret"):
                env_key = _field_env_key(provider, field)
                secret = env.get(env_key, "")
                returned_values[key] = "***" + secret[-4:] if secret else ""
                current = secret
            else:
                current = str(values.get(key, field.get("default", "")) or "")
                returned_values[key] = current
            if field.get("required") and not str(current).strip():
                configured = False
        items.append({
            "id": raw.get("id"),
            "provider": provider,
            "name": raw.get("name") or entry["name"],
            "category": entry["category"],
            "description": entry["description"],
            "fields": entry["fields"],
            "values": returned_values,
            "configured": configured,
        })
    return items


def upsert_connection(payload: dict[str, Any]) -> dict[str, Any]:
    provider = str(payload.get("provider", "")).strip()
    entry = _find_catalog_entry(provider)
    if not entry:
        raise ValueError(f"Unknown provider: {provider}")
    cfg = _config_root()
    values = dict(payload.get("values", {}) or {})
    connection_id = str(payload.get("id", "")).strip() or str(uuid4())

    stored_values: dict[str, str] = {}
    for field in entry.get("fields", []):
        raw_value = str(values.get(field["key"], "")).strip()
        if not raw_value and field.get("default"):
            raw_value = str(field["default"])
        if field.get("secret"):
            if raw_value and not raw_value.startswith("***"):
                _write_env_key(_field_env_key(provider, field), raw_value)
        else:
            stored_values[field["key"]] = raw_value

    items = cfg["automation"]["connections"]
    existing = next((item for item in items if item.get("id") == connection_id), None)
    if existing is None:
        existing = {"id": connection_id}
        items.append(existing)
    existing.update({
        "id": connection_id,
        "provider": provider,
        "name": str(payload.get("name", "")).strip() or entry["name"],
        "values": stored_values,
    })
    save_config(cfg)
    return next(item for item in list_connections() if item["id"] == connection_id)


def delete_connection(connection_id: str) -> None:
    cfg = _config_root()
    cfg["automation"]["connections"] = [
        item for item in cfg["automation"]["connections"]
        if str(item.get("id")) != str(connection_id)
    ]
    cfg["automation"]["workflows"] = [
        item for item in cfg["automation"]["workflows"]
        if item.get("source_connection_id") != connection_id
        and item.get("destination_connection_id") != connection_id
        and item.get("model_connection_id") != connection_id
    ]
    save_config(cfg)


def list_workflows() -> list[dict[str, Any]]:
    cfg = _config_root()
    items: list[dict[str, Any]] = []
    for raw in cfg["automation"]["workflows"]:
        if not isinstance(raw, dict):
            continue
        items.append({
            "id": raw.get("id"),
            "title": raw.get("title", "Untitled workflow"),
            "source_connection_id": raw.get("source_connection_id", ""),
            "model_connection_id": raw.get("model_connection_id", ""),
            "destination_connection_id": raw.get("destination_connection_id", ""),
            "mode": raw.get("mode", "route"),
            "prompt_template": raw.get("prompt_template", ""),
            "enabled": bool(raw.get("enabled", True)),
        })
    return items


def upsert_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    cfg = _config_root()
    items = cfg["automation"]["workflows"]
    workflow_id = str(payload.get("id", "")).strip() or str(uuid4())
    existing = next((item for item in items if item.get("id") == workflow_id), None)
    if existing is None:
        existing = {"id": workflow_id}
        items.append(existing)
    existing.update({
        "id": workflow_id,
        "title": str(payload.get("title", "")).strip() or "Untitled workflow",
        "source_connection_id": str(payload.get("source_connection_id", "")).strip(),
        "model_connection_id": str(payload.get("model_connection_id", "")).strip(),
        "destination_connection_id": str(payload.get("destination_connection_id", "")).strip(),
        "mode": str(payload.get("mode", "route")).strip() or "route",
        "prompt_template": str(payload.get("prompt_template", "")).strip(),
        "enabled": bool(payload.get("enabled", True)),
    })
    save_config(cfg)
    return next(item for item in list_workflows() if item["id"] == workflow_id)
