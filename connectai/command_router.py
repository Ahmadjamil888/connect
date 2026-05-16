from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from typing import Any, Callable, Dict, Optional


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

    def _normalize_natural_command(self, value: str) -> str:
        lowered = value.lower()
        if lowered in {"take a screenshot", "take screenshot", "screenshot", "see screen", "see my screen"}:
            return "screenshot"
        if lowered.startswith("use lovable to "):
            return "vibe lovable " + value[len("use lovable to "):].strip()
        if lowered.startswith("use bolt to "):
            return "vibe bolt " + value[len("use bolt to "):].strip()
        if lowered.startswith("use v0 to "):
            return "vibe v0 " + value[len("use v0 to "):].strip()
        if " on lovable" in lowered and lowered.startswith("build "):
            return "vibe lovable " + value[6 : lowered.rfind(" on lovable")].strip()
        if " on bolt" in lowered and lowered.startswith("build "):
            return "vibe bolt " + value[6 : lowered.rfind(" on bolt")].strip()
        if " on v0" in lowered and lowered.startswith("build "):
            return "vibe v0 " + value[6 : lowered.rfind(" on v0")].strip()
        if lowered in {"migrate to local", "download the project"}:
            return "vibe extract"
        if lowered in {"shut down", "shutdown"}:
            return "shutdown"
        if lowered == "sleep pc":
            return "sleep"
        if lowered == "lock pc":
            return "lock"
        if lowered.startswith(("open ", "launch ", "start ")):
            return "open " + self._normalize_open_target(value)
        if lowered.startswith("click "):
            return "click " + value[6:].strip()
        if lowered.startswith("type "):
            return "type " + value[5:].strip()
        if lowered.startswith("message "):
            return "message " + value[8:].strip()
        if lowered.startswith("whatsapp "):
            return "whatsapp " + value[9:].strip()
        if lowered.startswith("create a folder "):
            return "create folder " + value[16:].strip()
        return value

    def _normalize_open_target(self, value: str) -> str:
        text = (value or "").strip()
        lowered = text.lower()
        for prefix in ("open ", "launch ", "start "):
            if lowered.startswith(prefix):
                text = text[len(prefix):].strip()
                lowered = text.lower()
                break
        for article in ("the ", "a ", "an "):
            if lowered.startswith(article):
                text = text[len(article):].strip()
                lowered = text.lower()
                break
        alias_map = {
            "terminal": "cmd",
            "console": "cmd",
            "files": "explorer",
            "file explorer": "explorer",
            "browser": "edge",
            "web": "edge",
            "internet": "edge",
            "mail": "outlook",
            "outlook": "outlook",
        }
        if lowered in {"browser", "web", "internet"}:
            chrome_candidates = [
                "chrome.exe",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]
            if any(shutil.which(item) or (os.path.isabs(item) and os.path.exists(item)) for item in chrome_candidates):
                return "chrome"
            return "edge"
        return alias_map.get(lowered, text)

    def route(self, text: str) -> CommandResult:
        value = (text or "").strip()
        if not value:
            return CommandResult(handled=True, output="")
        value = self._normalize_natural_command(value)

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
            "gmail": "/gmail",
            "outreach": "/outreach",
            "whatsapp": "/whatsapp",
            "telegram": "/telegram",
            "v0": "/v0",
            "lovable": "/lovable",
            "bolt": "/bolt",
            "publish": "/publish",
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


_GLOBAL_ROUTE_HANDLER: Callable[[str], Any] | None = None


def set_global_route_handler(handler: Callable[[str], Any] | None) -> None:
    global _GLOBAL_ROUTE_HANDLER
    _GLOBAL_ROUTE_HANDLER = handler


def route(text: str) -> Any:
    if _GLOBAL_ROUTE_HANDLER is None:
        return {"ok": False, "error": "No route handler configured"}
    return _GLOBAL_ROUTE_HANDLER(text)


def _extract_prefixed_payload(text: str, prefixes: tuple[str, ...]) -> str:
    lowered = text.lower()
    for prefix in prefixes:
        if lowered.startswith(prefix):
            return text[len(prefix):].strip()
    return ""


def _parse_whatsapp_message(text: str) -> tuple[str, str, str] | None:
    raw = str(text or "").strip()
    lowered = raw.lower()
    channel = "whatsapp"
    if lowered.endswith(" using whatsapp"):
        raw = raw[: -len(" using whatsapp")].strip()
        lowered = raw.lower()
    prefixes = ("message ", "tell ", "whatsapp ", "send ", "text ")
    prefix = next((item for item in prefixes if lowered.startswith(item)), None)
    if prefix is None:
        return None
    body = raw[len(prefix):].strip()
    body_lower = body.lower()
    if prefix == "send " and " a message saying " in body_lower:
        split_at = body_lower.find(" a message saying ")
        return body[:split_at].strip(), body[split_at + len(" a message saying "):].strip(), channel
    special_markers = (
        (" that i ", lambda original, index: ("that i", original[index + len(" that "):].strip())),
        (" that ", lambda original, index: ("that", original[index + len(" that "):].strip())),
        (" saying ", lambda original, index: ("saying", original[index + len(" saying "):].strip())),
        (":", lambda original, index: (":", original[index + 1:].strip())),
    )
    for marker, extractor in special_markers:
        idx = body_lower.find(marker)
        if idx != -1:
            contact = body[:idx].strip()
            _label, message = extractor(body, idx)
            return contact, message, channel
    words = body.split()
    if not words:
        return None
    split_index = None
    for index, token in enumerate(words):
        token_clean = token.strip()
        if index == 0:
            continue
        if token_clean == "I":
            split_index = index
            break
        if token_clean and token_clean[0].islower():
            split_index = index
            break
    if split_index is None:
        split_index = min(2, max(1, len(words) - 1))
    contact = " ".join(words[:split_index]).strip()
    message = " ".join(words[split_index:]).strip()
    if not contact or not message:
        return None
    return contact, message, channel


def universal_route(
    text: str,
    *,
    run_skill: Callable[[str, dict[str, Any], str], CommandResult],
    run_direct: Callable[[str, str, Callable[[], dict[str, Any]]], CommandResult],
    run_command: Callable[[str], CommandResult],
    active_vibe_tool: Callable[[], str],
    active_vibe_project: Callable[[], str],
) -> CommandResult | None:
    lowered = (text or "").strip().lower()
    if not lowered:
        return None

    ai_prefixes = {
        "chatgpt": ("chat with chatgpt about ", "ask chatgpt ", "open chatgpt and ask "),
        "gemini": ("use gemini to ", "ask gemini "),
        "claude": ("open claude and ", "ask claude ", "use claude to "),
        "perplexity": ("ask perplexity ", "use perplexity to "),
        "lovable": ("use lovable to ",),
        "bolt": ("use bolt to ",),
        "v0": ("use v0 to ",),
        "grok": ("ask grok ", "use grok to "),
        "copilot": ("ask copilot ", "use copilot to "),
    }
    for tool_name, prefixes in ai_prefixes.items():
        payload = _extract_prefixed_payload(text, prefixes)
        if payload:
            return run_skill(
                "vibe_coder" if tool_name in {"lovable", "bolt", "v0"} and any(term in payload.lower() for term in ("build", "create", "make")) else "universal_runtime",
                (
                    {"action": "orchestrate", "prompt": payload, "preferred_tool": tool_name}
                    if tool_name in {"lovable", "bolt", "v0"} and any(term in payload.lower() for term in ("build", "create", "make"))
                    else {"action": "ai_tool", "tool": tool_name, "prompt": payload}
                ),
                f"{tool_name}({payload})",
            )

    if lowered.startswith("build ") and " on lovable" in lowered:
        payload = text[6: lowered.rfind(" on lovable")].strip()
        return run_skill("vibe_coder", {"action": "orchestrate", "prompt": payload, "preferred_tool": "lovable"}, f"lovable({payload})")
    if lowered.startswith("build ") and " on bolt" in lowered:
        payload = text[6: lowered.rfind(" on bolt")].strip()
        return run_skill("vibe_coder", {"action": "orchestrate", "prompt": payload, "preferred_tool": "bolt"}, f"bolt({payload})")
    if lowered.startswith("build ") and " on v0" in lowered:
        payload = text[6: lowered.rfind(" on v0")].strip()
        return run_skill("vibe_coder", {"action": "orchestrate", "prompt": payload, "preferred_tool": "v0"}, f"v0({payload})")

    build_terms = ("build", "create", "make")
    build_targets = ("website", "web app", "webapp", "landing page", "homepage", "react", "next.js", "nextjs", "app")
    if any(term in lowered for term in build_terms) and any(term in lowered for term in build_targets):
        return run_skill("vibe_coder", {"action": "orchestrate", "prompt": text}, f"vibe({text[:80]})")

    if lowered.startswith("open my ") and lowered.endswith(" project"):
        name = text[8:-8].strip()
        return run_skill("vibe_coder", {"action": "continue", "project_name": name, "messages": ["continue"]}, f"continue_project({name})")
    if lowered in {"deploy it", "publish it", "go live"} and active_vibe_tool():
        return run_skill("vibe_coder", {"action": "publish"}, "vibe_publish")
    if lowered.startswith("publish to ") or lowered.startswith("deploy to "):
        target = text.split(" to ", 1)[1].strip().lower()
        return run_skill("vibe_coder", {"action": "publish", "tool": target}, f"vibe_publish({target})")
    if lowered == "push to github" and active_vibe_tool():
        return run_skill("vibe_coder", {"action": "continue", "messages": ["Push this project to GitHub."]}, "vibe_github")
    if lowered in {"migrate to local", "download the project"}:
        return run_skill("vibe_coder", {"action": "extract", "project_name": active_vibe_project() or "project"}, "vibe_extract")
    if lowered.startswith("tell it to ") and active_vibe_tool():
        payload = text[len("tell it to "):].strip()
        return run_skill("vibe_coder", {"action": "continue", "messages": [payload]}, f"vibe_followup({payload})")
    if active_vibe_tool() and lowered.startswith(("make it ", "add ", "change ")):
        return run_skill("vibe_coder", {"action": "continue", "messages": [text]}, f"vibe_followup({text})")

    if lowered.startswith("whatsapp "):
        parsed = _parse_whatsapp_message(text)
        if parsed is not None:
            contact, message, _channel = parsed
            return run_skill("universal_runtime", {"action": "message", "platform": "whatsapp", "contact": contact, "message": message}, f"whatsapp({contact})")
    if lowered.startswith("telegram "):
        body = text[9:].strip()
        parts = body.split(" ", 1)
        if len(parts) == 2:
            contact, message = parts
            return run_skill("universal_runtime", {"action": "message", "platform": "telegram", "contact": contact, "message": message}, f"telegram({contact})")
    if lowered.startswith("dm ") and " on instagram " in lowered:
        split_at = lowered.rfind(" on instagram ")
        contact = text[3:split_at].strip()
        message = text[split_at + len(" on instagram "):].strip()
        return run_skill("universal_runtime", {"action": "message", "platform": "instagram", "contact": contact, "message": message}, f"instagram({contact})")
    parsed_message = _parse_whatsapp_message(text)
    if parsed_message is not None:
        contact, message, channel = parsed_message
        return run_skill("universal_runtime", {"action": "message", "platform": channel, "contact": contact, "message": message}, f"message({contact})")
    if lowered.startswith("send ") and " on " in lowered:
        body = text[5:].strip()
        if " saying " in body.lower():
            split_at = body.lower().rfind(" saying ")
            contact = body[:split_at].strip()
            message = body[split_at + 8:].strip()
            return run_skill("universal_runtime", {"action": "message", "platform": "whatsapp", "contact": contact, "message": message}, f"message({contact})")
        split_at = body.lower().rfind(" on ")
        left = body[:split_at].strip()
        platform = body[split_at + 4:].strip()
        parts = left.split(" ", 1)
        if len(parts) == 2:
            contact, message = parts
            return run_skill("universal_runtime", {"action": "message", "platform": platform, "contact": contact, "message": message}, f"{platform}({contact})")

    if lowered.startswith("tweet ") or lowered.startswith("post on twitter"):
        payload = text[6:].strip() if lowered.startswith("tweet ") else text.split(":", 1)[-1].strip()
        return run_skill("universal_runtime", {"action": "post", "platform": "twitter", "text": payload}, f"tweet({payload[:40]})")
    if lowered.startswith("post on instagram "):
        payload = text[len("post on instagram "):].strip()
        return run_skill("universal_runtime", {"action": "post", "platform": "instagram", "text": payload}, f"instagram_post({payload[:40]})")
    if lowered.startswith("post on linkedin "):
        payload = text[len("post on linkedin "):].strip()
        return run_skill("universal_runtime", {"action": "post", "platform": "linkedin", "text": payload}, f"linkedin_post({payload[:40]})")

    if lowered.startswith("search for ") and lowered.endswith(" on google"):
        query = text[len("search for "): lowered.rfind(" on google")].strip()
        return run_skill("universal_runtime", {"action": "browser_open", "url": f"https://google.com/search?q={quote(query)}"}, f"google({query})")
    if lowered.startswith("go to "):
        target = text[6:].strip()
        url = target if "://" in target else f"https://{target}"
        return run_skill("universal_runtime", {"action": "browser_open", "url": url}, f"go_to({url})")
    if lowered.startswith("open http://") or lowered.startswith("open https://"):
        url = text[5:].strip()
        return run_skill("universal_runtime", {"action": "browser_open", "url": url}, f"open_url({url})")
    if lowered in {"scroll down", "go back", "close tab"}:
        action = {"scroll down": "browser_scroll", "go back": "browser_back", "close tab": "browser_close_tab"}[lowered]
        return run_skill("universal_runtime", {"action": action}, action)

    if lowered in {"take a screenshot", "screenshot", "see screen"}:
        return run_command("screenshot")
    if lowered in {"shutdown", "shut down"}:
        return run_command("shutdown")
    if lowered == "restart":
        return run_command("restart")
    if lowered in {"sleep", "sleep pc"}:
        return run_command("sleep")
    if lowered in {"lock", "lock pc"}:
        return run_command("lock")
    if lowered.startswith(("open ", "launch ", "start ")):
        return run_command("open " + text.split(" ", 1)[1].strip())
    if lowered.startswith("create folder "):
        return run_command(text)

    if lowered.startswith("ask ") or lowered.startswith("use "):
        return CommandResult(True, "IMOS understood this as an AI-tool request, but the target tool was unclear. Specify the tool name, for example: ask chatgpt ..., use gemini to ..., or ask claude ...")
    return None
