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
        "provider": "deepseek",
        "name": "DeepSeek",
        "category": "model-cloud",
        "description": "DeepSeek chat and coder models.",
        "fields": [
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "model", "label": "Model ID", "required": True, "default": "deepseek-chat"},
        ],
    },
    {
        "provider": "alibaba",
        "name": "Alibaba Cloud / DashScope",
        "category": "model-cloud",
        "description": "Qwen and other Alibaba-hosted models through an OpenAI-compatible endpoint.",
        "fields": [
            {"key": "api_key", "label": "API key", "secret": True},
            {"key": "base_url", "label": "Endpoint URL", "required": True},
            {"key": "model", "label": "Model ID", "required": True, "default": "qwen-plus"},
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

APP_CONNECTIONS.extend(
    [
        {
            "provider": "signal",
            "name": "Signal",
            "category": "messaging",
            "description": "signal-cli or Signal REST bridge automation.",
            "fields": [
                {"key": "phone_number", "label": "Phone number", "required": True},
                {"key": "api_url", "label": "REST API URL"},
                {"key": "api_key", "label": "API key", "secret": True},
            ],
        },
        {
            "provider": "matrix",
            "name": "Matrix / Element",
            "category": "messaging",
            "description": "Matrix room messaging and bot workflows.",
            "fields": [
                {"key": "homeserver", "label": "Homeserver URL", "required": True},
                {"key": "user_id", "label": "User ID", "required": True},
                {"key": "access_token", "label": "Access token", "secret": True},
                {"key": "room_id", "label": "Default room ID"},
            ],
        },
        {
            "provider": "mattermost",
            "name": "Mattermost",
            "category": "messaging",
            "description": "Team posts, channels, and message automations.",
            "fields": [
                {"key": "base_url", "label": "Base URL", "required": True},
                {"key": "token", "label": "Access token", "secret": True, "required": True},
                {"key": "channel_id", "label": "Default channel ID"},
            ],
        },
        {
            "provider": "rocketchat",
            "name": "Rocket.Chat",
            "category": "messaging",
            "description": "Channels, DMs, and webhook-driven ops workflows.",
            "fields": [
                {"key": "base_url", "label": "Base URL", "required": True},
                {"key": "user_id", "label": "User ID"},
                {"key": "auth_token", "label": "Auth token", "secret": True, "required": True},
                {"key": "channel", "label": "Default channel"},
            ],
        },
        {
            "provider": "jira",
            "name": "Jira",
            "category": "productivity",
            "description": "Issue workflows, ticket triage, and sprint automations.",
            "fields": [
                {"key": "server", "label": "Server URL", "required": True},
                {"key": "email", "label": "Email", "required": True},
                {"key": "api_token", "label": "API token", "secret": True, "required": True},
                {"key": "project_key", "label": "Default project key"},
            ],
        },
        {
            "provider": "trello",
            "name": "Trello",
            "category": "productivity",
            "description": "Boards, cards, lists, and lightweight ops flows.",
            "fields": [
                {"key": "api_key", "label": "API key", "secret": True, "required": True},
                {"key": "token", "label": "Token", "secret": True, "required": True},
                {"key": "board_id", "label": "Default board ID"},
            ],
        },
        {
            "provider": "linear",
            "name": "Linear",
            "category": "productivity",
            "description": "Issue routing, release planning, and team triage.",
            "fields": [
                {"key": "api_key", "label": "API key", "secret": True, "required": True},
                {"key": "team_id", "label": "Team ID"},
            ],
        },
        {
            "provider": "asana",
            "name": "Asana",
            "category": "productivity",
            "description": "Projects, tasks, and portfolio automations.",
            "fields": [
                {"key": "access_token", "label": "Access token", "secret": True, "required": True},
                {"key": "workspace_id", "label": "Workspace ID"},
            ],
        },
        {
            "provider": "google-workspace",
            "name": "Google Workspace",
            "category": "productivity",
            "description": "Gmail, Drive, Docs, Sheets, and Calendar automation.",
            "fields": [
                {"key": "client_id", "label": "OAuth client ID"},
                {"key": "client_secret", "label": "OAuth client secret", "secret": True},
                {"key": "refresh_token", "label": "Refresh token", "secret": True},
                {"key": "service_account_json", "label": "Service account JSON path"},
            ],
        },
        {
            "provider": "microsoft365",
            "name": "Microsoft 365",
            "category": "productivity",
            "description": "Outlook, OneDrive, Word, Excel, and SharePoint flows.",
            "fields": [
                {"key": "client_id", "label": "Client ID", "required": True},
                {"key": "client_secret", "label": "Client secret", "secret": True, "required": True},
                {"key": "tenant_id", "label": "Tenant ID", "required": True},
            ],
        },
        {
            "provider": "zoom",
            "name": "Zoom",
            "category": "meetings",
            "description": "Meeting scheduling, recordings, and summaries.",
            "fields": [
                {"key": "client_id", "label": "Client ID", "required": True},
                {"key": "client_secret", "label": "Client secret", "secret": True, "required": True},
                {"key": "account_id", "label": "Account ID", "required": True},
            ],
        },
        {
            "provider": "google-meet",
            "name": "Google Meet",
            "category": "meetings",
            "description": "Meet scheduling via Calendar and Workspace auth.",
            "fields": [
                {"key": "client_id", "label": "OAuth client ID"},
                {"key": "client_secret", "label": "OAuth client secret", "secret": True},
                {"key": "refresh_token", "label": "Refresh token", "secret": True},
            ],
        },
        {
            "provider": "calendly",
            "name": "Calendly",
            "category": "meetings",
            "description": "Scheduling links, event feeds, and booking workflows.",
            "fields": [
                {"key": "api_token", "label": "API token", "secret": True, "required": True},
            ],
        },
        {
            "provider": "stripe",
            "name": "Stripe",
            "category": "payments",
            "description": "Customers, subscriptions, invoices, and payouts.",
            "fields": [
                {"key": "secret_key", "label": "Secret key", "secret": True, "required": True},
                {"key": "webhook_secret", "label": "Webhook secret", "secret": True},
            ],
        },
        {
            "provider": "paypal",
            "name": "PayPal",
            "category": "payments",
            "description": "Orders, captures, payouts, and subscriptions.",
            "fields": [
                {"key": "client_id", "label": "Client ID", "required": True},
                {"key": "client_secret", "label": "Client secret", "secret": True, "required": True},
                {"key": "mode", "label": "Mode", "default": "sandbox"},
            ],
        },
        {
            "provider": "shopify",
            "name": "Shopify",
            "category": "commerce",
            "description": "Storefront orders, products, customers, and fulfillment.",
            "fields": [
                {"key": "shop_domain", "label": "Shop domain", "required": True},
                {"key": "access_token", "label": "Access token", "secret": True, "required": True},
            ],
        },
        {
            "provider": "vercel",
            "name": "Vercel",
            "category": "deployment",
            "description": "Project deployment, env vars, and preview automation.",
            "fields": [
                {"key": "token", "label": "Access token", "secret": True, "required": True},
                {"key": "team_id", "label": "Team ID"},
                {"key": "project_id", "label": "Default project ID"},
            ],
        },
        {
            "provider": "netlify",
            "name": "Netlify",
            "category": "deployment",
            "description": "Site deploys, build hooks, and preview management.",
            "fields": [
                {"key": "token", "label": "Access token", "secret": True, "required": True},
                {"key": "site_id", "label": "Site ID"},
            ],
        },
        {
            "provider": "railway",
            "name": "Railway",
            "category": "deployment",
            "description": "Projects, services, and environment automation.",
            "fields": [
                {"key": "token", "label": "Access token", "secret": True, "required": True},
                {"key": "project_id", "label": "Project ID"},
            ],
        },
        {
            "provider": "render",
            "name": "Render",
            "category": "deployment",
            "description": "Deploy services, jobs, cron, and static sites.",
            "fields": [
                {"key": "api_key", "label": "API key", "secret": True, "required": True},
                {"key": "service_id", "label": "Default service ID"},
            ],
        },
        {
            "provider": "supabase",
            "name": "Supabase",
            "category": "backend",
            "description": "Database, auth, storage, and edge function automation.",
            "fields": [
                {"key": "project_url", "label": "Project URL", "required": True},
                {"key": "service_role_key", "label": "Service role key", "secret": True, "required": True},
            ],
        },
        {
            "provider": "firebase",
            "name": "Firebase",
            "category": "backend",
            "description": "Firestore, Auth, Functions, and hosting automation.",
            "fields": [
                {"key": "project_id", "label": "Project ID", "required": True},
                {"key": "service_account_json", "label": "Service account JSON path", "required": True},
            ],
        },
    ]
)


def _infer_auth(entry: dict[str, Any]) -> dict[str, Any]:
    auth = dict(entry.get("auth", {}) or {})
    fields = entry.get("fields", [])
    keys = {field.get("key", "") for field in fields}
    if not auth.get("type"):
        if "webhook_url" in keys or "url" in keys and len(keys) <= 3:
            auth["type"] = "webhook"
        elif {"client_id", "client_secret"} & keys:
            auth["type"] = "oauth2"
        elif "email" in keys and ("app_password" in keys or "password" in keys):
            auth["type"] = "smtp_or_password"
        elif entry.get("category", "").startswith("model-local"):
            auth["type"] = "local"
        else:
            auth["type"] = "api_key_or_token"
    if "oauth2" in auth["type"] and "grant" not in auth:
        auth["grant"] = "authorization_code_or_refresh_token"
    if auth["type"] == "webhook" and "grant" not in auth:
        auth["grant"] = "signed_url_or_secret_header"
    if "scopes" not in auth:
        auth["scopes"] = []
    if "notes" not in auth:
        auth["notes"] = "Credentials stay local and are stored in the local IMOS configuration."
    return auth


def _with_auth(entry: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(entry)
    enriched["auth"] = _infer_auth(enriched)
    return enriched


def _catalog() -> list[dict[str, Any]]:
    return [_with_auth(item) for item in [*APP_CONNECTIONS, *MODEL_CONNECTIONS]]


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
        and not any(str(step.get("connection_id")) == str(connection_id) for step in item.get("steps", []) if isinstance(step, dict))
    ]
    save_config(cfg)


def _normalize_workflow_steps(payload: dict[str, Any]) -> list[dict[str, Any]]:
    steps = payload.get("steps")
    normalized: list[dict[str, Any]] = []
    if isinstance(steps, list):
        for index, raw in enumerate(steps):
            if not isinstance(raw, dict):
                continue
            connection_id = str(raw.get("connection_id", "")).strip()
            if not connection_id:
                continue
            normalized.append(
                {
                    "id": str(raw.get("id", "")).strip() or str(uuid4()),
                    "kind": str(raw.get("kind", "app")).strip() or "app",
                    "connection_id": connection_id,
                    "action": str(raw.get("action", "auto")).strip() or "auto",
                    "prompt": str(raw.get("prompt", "")).strip(),
                    "order": index,
                }
            )
    if normalized:
        return normalized

    legacy = [
        ("source_connection_id", "source"),
        ("model_connection_id", "model"),
        ("destination_connection_id", "destination"),
    ]
    for order, (key, kind) in enumerate(legacy):
        value = str(payload.get(key, "")).strip()
        if value:
            normalized.append(
                {
                    "id": str(uuid4()),
                    "kind": kind,
                    "connection_id": value,
                    "action": "auto",
                    "prompt": str(payload.get("prompt_template", "")).strip() if kind == "model" else "",
                    "order": order,
                }
            )
    return normalized


def list_workflows() -> list[dict[str, Any]]:
    cfg = _config_root()
    items: list[dict[str, Any]] = []
    for raw in cfg["automation"]["workflows"]:
        if not isinstance(raw, dict):
            continue
        steps = _normalize_workflow_steps(raw)
        source_connection_id = steps[0]["connection_id"] if steps else raw.get("source_connection_id", "")
        model_connection_id = next((step["connection_id"] for step in steps if step.get("kind") == "model"), raw.get("model_connection_id", ""))
        destination_connection_id = steps[-1]["connection_id"] if steps else raw.get("destination_connection_id", "")
        items.append({
            "id": raw.get("id"),
            "title": raw.get("title", "Untitled workflow"),
            "source_connection_id": source_connection_id,
            "model_connection_id": model_connection_id,
            "destination_connection_id": destination_connection_id,
            "mode": raw.get("mode", "route"),
            "prompt_template": raw.get("prompt_template", ""),
            "enabled": bool(raw.get("enabled", True)),
            "steps": steps,
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
    steps = _normalize_workflow_steps(payload)
    existing.update({
        "id": workflow_id,
        "title": str(payload.get("title", "")).strip() or "Untitled workflow",
        "source_connection_id": steps[0]["connection_id"] if steps else str(payload.get("source_connection_id", "")).strip(),
        "model_connection_id": next((step["connection_id"] for step in steps if step.get("kind") == "model"), str(payload.get("model_connection_id", "")).strip()),
        "destination_connection_id": steps[-1]["connection_id"] if steps else str(payload.get("destination_connection_id", "")).strip(),
        "mode": str(payload.get("mode", "route")).strip() or "route",
        "prompt_template": str(payload.get("prompt_template", "")).strip(),
        "enabled": bool(payload.get("enabled", True)),
        "steps": steps,
    })
    save_config(cfg)
    return next(item for item in list_workflows() if item["id"] == workflow_id)
