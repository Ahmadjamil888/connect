from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


DEFAULT_TOOL_PROFILES: Dict[str, List[str]] = {
    "minimal": ["session_status"],
    "coding": ["group:fs", "group:runtime", "group:sessions", "group:memory", "image"],
    "messaging": ["group:messaging", "group:sessions", "session_status"],
}


@dataclass
class AgentToolPolicy:
    profile: str = "coding"
    allow: List[str] = field(default_factory=list)
    deny: List[str] = field(default_factory=list)


@dataclass
class AgentConfigEntry:
    name: str
    tools: AgentToolPolicy = field(default_factory=AgentToolPolicy)


@dataclass
class GatewayConfig:
    host: str = "127.0.0.1"
    port: int = 18789
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 18890
    workspace_root: Path = field(default_factory=lambda: Path.cwd() / ".openclaw" / "workspace")
    config_path: Path = field(default_factory=lambda: Path.cwd() / "openclaw.json")
    provider_default: str = ""
    deployment_mode: str = "local"
    auth_enabled: bool = False
    clerk_publishable_key: str = field(default_factory=lambda: os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "").strip())
    clerk_secret_key: str = field(default_factory=lambda: os.getenv("CLERK_SECRET_KEY", "").strip())
    webhook_bearer_token: str = ""
    tools_allow: List[str] = field(default_factory=list)
    tools_deny: List[str] = field(default_factory=list)
    agents: List[AgentConfigEntry] = field(default_factory=list)
    telegram_bot_token: str = ""
    telegram_default_chat_id: str = ""
    discord_webhooks: Dict[str, str] = field(default_factory=dict)
    slack_webhooks: Dict[str, str] = field(default_factory=dict)
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    whatsapp_account_sid: str = ""
    whatsapp_auth_token: str = ""
    whatsapp_from_number: str = ""

    def agent_policy(self, name: str) -> AgentToolPolicy:
        for agent in self.agents:
            if agent.name == name:
                return agent.tools
        return AgentToolPolicy()


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parse_agent(entry: Dict[str, Any]) -> AgentConfigEntry:
    tools = entry.get("tools", {}) if isinstance(entry, dict) else {}
    policy = AgentToolPolicy(
        profile=str(tools.get("profile", "coding") or "coding"),
        allow=[str(item) for item in tools.get("allow", []) if str(item).strip()],
        deny=[str(item) for item in tools.get("deny", []) if str(item).strip()],
    )
    return AgentConfigEntry(name=str(entry.get("name", "default") or "default"), tools=policy)


def load_gateway_config(path: Optional[Path] = None) -> GatewayConfig:
    resolved = Path(path) if path else Path.cwd() / "openclaw.json"
    data = _read_json(resolved)
    gateway = data.get("gateway", {}) if isinstance(data, dict) else {}
    auth = data.get("auth", {}) if isinstance(data, dict) else {}
    workspace = data.get("workspace", {}) if isinstance(data, dict) else {}
    tools = data.get("tools", {}) if isinstance(data, dict) else {}
    provider = data.get("provider", {}) if isinstance(data, dict) else {}
    agents_data = data.get("agents", {}).get("list", []) if isinstance(data, dict) else []
    workspace_root = Path(workspace.get("root", Path.cwd() / ".openclaw" / "workspace"))
    return GatewayConfig(
        host=str(gateway.get("host", "127.0.0.1")),
        port=int(gateway.get("port", 18789)),
        dashboard_host=str(gateway.get("dashboard_host", gateway.get("host", "127.0.0.1"))),
        dashboard_port=int(gateway.get("dashboard_port", 18890)),
        workspace_root=workspace_root,
        config_path=resolved,
        provider_default=str(provider.get("default", "")).strip().lower(),
        deployment_mode=str(gateway.get("deployment_mode", "local") or "local").strip().lower(),
        auth_enabled=bool(auth.get("enabled", False)),
        clerk_publishable_key=os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "").strip(),
        clerk_secret_key=os.getenv("CLERK_SECRET_KEY", "").strip(),
        webhook_bearer_token=str(auth.get("webhook_bearer_token", "")).strip(),
        tools_allow=[str(item) for item in tools.get("allow", []) if str(item).strip()],
        tools_deny=[str(item) for item in tools.get("deny", []) if str(item).strip()],
        agents=[_parse_agent(item) for item in agents_data if isinstance(item, dict)],
        telegram_bot_token=str((data.get("messaging", {}) if isinstance(data, dict) else {}).get("telegram_bot_token", "")).strip(),
        telegram_default_chat_id=str((data.get("messaging", {}) if isinstance(data, dict) else {}).get("telegram_default_chat_id", "")).strip(),
        discord_webhooks={
            str(key): str(value)
            for key, value in ((data.get("messaging", {}) if isinstance(data, dict) else {}).get("discord_webhooks", {}) or {}).items()
            if str(key).strip() and str(value).strip()
        },
        slack_webhooks={
            str(key): str(value)
            for key, value in ((data.get("messaging", {}) if isinstance(data, dict) else {}).get("slack_webhooks", {}) or {}).items()
            if str(key).strip() and str(value).strip()
        },
        slack_bot_token=str((data.get("messaging", {}) if isinstance(data, dict) else {}).get("slack_bot_token", "")).strip(),
        slack_signing_secret=str((data.get("messaging", {}) if isinstance(data, dict) else {}).get("slack_signing_secret", "")).strip(),
        whatsapp_account_sid=str((data.get("messaging", {}) if isinstance(data, dict) else {}).get("whatsapp_account_sid", "")).strip(),
        whatsapp_auth_token=str((data.get("messaging", {}) if isinstance(data, dict) else {}).get("whatsapp_auth_token", "")).strip(),
        whatsapp_from_number=str((data.get("messaging", {}) if isinstance(data, dict) else {}).get("whatsapp_from_number", "")).strip(),
    )


def _expand_profile_entries(entries: List[str], known_names: Set[str], group_map: Dict[str, Set[str]]) -> Set[str]:
    expanded: Set[str] = set()
    for entry in entries:
        if entry.startswith("group:"):
            expanded.update(group_map.get(entry.split(":", 1)[1], set()))
        elif entry == "image":
            for name in known_names:
                if "image" in name:
                    expanded.add(name)
        elif entry == "*":
            expanded.update(known_names)
        elif entry in known_names:
            expanded.add(entry)
    return expanded


def resolve_allowed_tool_names(
    profile: str,
    config_allow: List[str],
    config_deny: List[str],
    policy_allow: List[str],
    policy_deny: List[str],
    known_names: Set[str],
    group_map: Dict[str, Set[str]],
) -> Set[str]:
    profile_entries = DEFAULT_TOOL_PROFILES.get(profile, DEFAULT_TOOL_PROFILES["coding"])
    allowed = _expand_profile_entries(profile_entries, known_names, group_map)
    allowed.update(_expand_profile_entries(config_allow, known_names, group_map))
    allowed.update(_expand_profile_entries(policy_allow, known_names, group_map))
    denied = _expand_profile_entries(config_deny, known_names, group_map)
    denied.update(_expand_profile_entries(policy_deny, known_names, group_map))
    return {name for name in allowed if name not in denied}
