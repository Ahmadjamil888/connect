from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional


@dataclass
class CommandResult:
    handled: bool
    output: str = ""
    should_exit: bool = False
    updated_model_config: Optional[dict] = None
    updated_workspace: Optional[str] = None


class CommandRouter:
    def __init__(
        self,
        handlers: Dict[str, Callable[[str], CommandResult]],
        *,
        natural_dispatcher: Callable[[str], CommandResult | None] | None = None,
        routing_rules=None,
    ):
        self.handlers = handlers
        self.natural_dispatcher = natural_dispatcher
        self.routing_rules = routing_rules

    def route(self, text: str) -> CommandResult:
        value = (text or "").strip()
        if not value:
            return CommandResult(handled=True, output="")

        direct_map = {
            "help": "/help",
            "clear": "/clear",
            "exit": "/exit",
            "quit": "/exit",
            "dashboard": "/dashboard",
            "login": "/login",
            "logout": "/logout",
            "models": "/models",
            "model": "/model",
            "provider": "/model",
            "workspace": "/workspace",
            "setup": "/setup",
            "skills": "/skills",
            "sessions": "/sessions",
            "session": "/session",
            "tasks": "/tasks",
            "processes": "/processes",
            "audit": "/audit",
            "git": "/git status",
            "mcp": "/mcp",
            "claude-code": "/claude-code",
            "openai": "/openai",
            "codex": "/codex",
            "cursor": "/cursor",
            "ide": "/ide",
            "vscode": "/vscode",
            "windsurf": "/windsurf",
            "aider": "/aider",
            "continue": "/continue",
            "gemini": "/gemini",
            "email": "/email",
            "whatsapp": "/whatsapp",
            "telegram": "/telegram",
            "v0": "/v0",
            "lovable": "/lovable",
            "bolt": "/bolt",
            "doctor": "/doctor",
            "route": "/route",
            "terminal": "/terminal",
            "workflows": "/workflows",
            "pickmodel": "/pickmodel",
            "consent": "/consent",
            "contact": "/contact",
            "listen": "/listen",
            "voice": "/voice",
            "autostart": "/autostart",
        }
        lowered = value.lower()
        if lowered in direct_map:
            value = direct_map[lowered]
        elif lowered in {"connect dashboard", "open dashboard"}:
            value = "/dashboard"
        elif lowered in {"connect login", "login connect"}:
            value = "/login"
        elif lowered in {"connect logout", "logout connect"}:
            value = "/logout"
        elif lowered in {"take a screenshot", "what's on screen", "whats on screen"}:
            value = "screenshot" if lowered == "take a screenshot" else value
        elif lowered.startswith("use provider "):
            value = "/use " + value.split(" ", 2)[2]
        elif lowered.startswith("set provider "):
            value = "/use " + value.split(" ", 2)[2]
        elif lowered.startswith("use model "):
            value = "/setmodel " + value.split(" ", 2)[2]
        elif lowered.startswith("set model "):
            value = "/setmodel " + value.split(" ", 2)[2]
        elif lowered.startswith("new model "):
            value = "/setmodel " + value.split(" ", 2)[2]
        elif lowered.startswith("run workflow "):
            value = "/runflow " + value.split(" ", 2)[2]
        elif lowered.startswith("memory search "):
            value = "/memory " + value.split(" ", 2)[2]
        elif lowered.startswith("config get "):
            value = "/config get " + value.split(" ", 2)[2]
        elif lowered.startswith("config set "):
            value = "/config set " + value.split(" ", 2)[2]

        if not value.startswith("/"):
            if self.natural_dispatcher is not None:
                routed = self.natural_dispatcher(value)
                if routed is not None:
                    return routed
            return CommandResult(handled=False)

        command = value.split()[0].lower()
        handler = self.handlers.get(command)
        if not handler:
            return CommandResult(handled=True, output=f"Unknown command: {command}")
        return handler(value)
