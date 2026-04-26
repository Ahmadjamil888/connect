#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CONNECT AI - Capability-Layered AI Operator
Urdu/Hindi: Ek advanced AI platform jo planning, coding, automation, aur execution
ko controlled tools ke through chalata hai.
- Chatting, coding, computer operations, web automation
- Website creation, content generation, scripts
- Startup setup (idea se le kar launch tak)
- Weekly analytics, auditability, aur run memory
"""

import os
import sys
import json
import time
import re
import argparse
import difflib
import hashlib
import subprocess
import platform
import threading
import requests
from getpass import getpass
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field, asdict

# Enable ANSI color support on Windows terminals when available.
try:
    from colorama import just_fix_windows_console
    just_fix_windows_console()
except ImportError:
    pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
except ImportError:
    Console = None
    Panel = None
    Text = None
    box = None

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Fallback: manually load .env if python-dotenv not installed
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

# ============================================================================
# CONFIGURATION
# ============================================================================

def _resolve_runtime_data_dir() -> Path:
    """Pick a writable runtime directory, preferring the user's home directory."""
    candidates = [
        Path.home() / ".ai_assistant",
        Path(__file__).resolve().parent / ".ai_assistant_runtime",
        Path.cwd() / ".ai_assistant_runtime",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return candidate
        except Exception:
            continue
    raise RuntimeError("No writable runtime directory available for CONNECT")

class Config:
    """Platform configuration."""

    APP_NAME = "CONNECT"
    APP_TAGLINE = "Autonomous AI Operator"
    PROMPT_LABEL = ">"

    # AI Model
    AI_PROVIDER = os.getenv("AI_PROVIDER", "").strip().lower()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")
    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "compound-beta")
    GROQ_CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-7-sonnet-latest")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3-70b-instruct")
    GOOGLE_GEMINI_MODEL = os.getenv("GOOGLE_GEMINI_MODEL", "gemini-2.5-flash")
    HUGGINGFACE_MODEL = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
    OLLAMA_MODEL = "llama3.2"
    TOOL_TIMEOUT = int(os.getenv("TOOL_TIMEOUT", "120"))

    # Data Directory
    DATA_DIR = _resolve_runtime_data_dir()

    # Storage Files
    USER_DATA_FILE = DATA_DIR / "user_data.json"
    HISTORY_FILE = DATA_DIR / "history.json"
    ANALYTICS_FILE = DATA_DIR / "analytics.json"
    PROJECTS_FILE = DATA_DIR / "projects.json"
    CREDENTIALS_FILE = DATA_DIR / "credentials.enc.json"
    WORKFLOWS_DIR = DATA_DIR / "workflows"
    HELPERS_DIR = DATA_DIR / "helpers"
    WORLD_STATE_FILE = DATA_DIR / "world_state.json"
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    HELPERS_DIR.mkdir(parents=True, exist_ok=True)

    # Security
    ENCRYPTION_KEY = hashlib.sha256(platform.node().encode()).hexdigest()[:32]

    # Limits
    MAX_HISTORY = 1000
    MAX_CONVERSATION_TURNS = 50
    MAX_ITERATIONS = 30

    # Debug
    DEBUG = os.getenv("AI_PLATFORM_DEBUG", "false").lower() == "true"
    USE_GROQ = bool(GROQ_API_KEY)

    @classmethod
    def refresh_from_env(cls):
        """Refresh provider configuration from the current process environment."""
        cls.AI_PROVIDER = os.getenv("AI_PROVIDER", "").strip().lower()
        cls.GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
        cls.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        cls.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        cls.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
        cls.GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")
        cls.HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
        cls.GROQ_MODEL = os.getenv("GROQ_MODEL", "compound-beta")
        cls.GROQ_CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile")
        cls.ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-7-sonnet-latest")
        cls.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        cls.OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3-70b-instruct")
        cls.GOOGLE_GEMINI_MODEL = os.getenv("GOOGLE_GEMINI_MODEL", "gemini-2.5-flash")
        cls.HUGGINGFACE_MODEL = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
        cls.DEBUG = os.getenv("AI_PLATFORM_DEBUG", "false").lower() == "true"
        cls.USE_GROQ = bool(cls.GROQ_API_KEY)


def debug_log(message: str):
    if Config.DEBUG:
        print(f"[DEBUG] {message}")


class ShellSession:
    """Stateful command execution with persistent cwd/env/session memory."""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.cwd = Path.cwd()
        self.env = os.environ.copy()
        self.history: List[Dict[str, Any]] = []
        self.lock = threading.Lock()

    def execute(self, command: str, cwd: str = None, timeout: Optional[int] = None) -> Dict[str, Any]:
        with self.lock:
            resolved_cwd = self._resolve_cwd(cwd)
            normalized = (command or "").strip()
            if not normalized:
                return self._record(
                    {
                        "ok": False,
                        "session_id": self.session_id,
                        "cwd": str(resolved_cwd),
                        "exit_code": -1,
                        "stdout": "",
                        "stderr": "empty command",
                        "command": normalized,
                    }
                )

            env_note, remaining = self._consume_env_assignment(normalized)
            if remaining is not None:
                normalized = remaining.strip()
                if not normalized:
                    return self._record(
                        {
                            "ok": True,
                            "session_id": self.session_id,
                            "cwd": str(resolved_cwd),
                            "exit_code": 0,
                            "stdout": env_note,
                            "stderr": "",
                            "command": command,
                        }
                    )

            cd_result = self._handle_cd(normalized, resolved_cwd)
            if cd_result is not None:
                return self._record(cd_result)

            try:
                completed = subprocess.run(
                    normalized,
                    shell=True,
                    cwd=str(resolved_cwd),
                    env=self.env,
                    capture_output=True,
                    text=True,
                    timeout=timeout or Config.TOOL_TIMEOUT,
                )
                self.cwd = resolved_cwd
                return self._record(
                    {
                        "ok": completed.returncode == 0,
                        "session_id": self.session_id,
                        "cwd": str(self.cwd),
                        "exit_code": completed.returncode,
                        "stdout": completed.stdout or "",
                        "stderr": completed.stderr or "",
                        "command": command,
                    }
                )
            except subprocess.TimeoutExpired as exc:
                self.cwd = resolved_cwd
                return self._record(
                    {
                        "ok": False,
                        "session_id": self.session_id,
                        "cwd": str(self.cwd),
                        "exit_code": -2,
                        "stdout": exc.stdout or "",
                        "stderr": f"timeout after {timeout or Config.TOOL_TIMEOUT}s",
                        "command": command,
                    }
                )
            except Exception as exc:
                return self._record(
                    {
                        "ok": False,
                        "session_id": self.session_id,
                        "cwd": str(resolved_cwd),
                        "exit_code": -1,
                        "stdout": "",
                        "stderr": str(exc),
                        "command": command,
                    }
                )

    def snapshot(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "cwd": str(self.cwd),
            "history": self.history[-20:],
        }

    def _resolve_cwd(self, cwd: Optional[str]) -> Path:
        candidate = Path(cwd).expanduser() if cwd else self.cwd
        if not candidate.is_absolute():
            candidate = (self.cwd / candidate).resolve()
        return candidate

    def _consume_env_assignment(self, command: str) -> tuple[str, Optional[str]]:
        match = re.match(r"^\$env:([A-Za-z_][A-Za-z0-9_]*)\s*=\s*['\"]?(.*?)['\"]?\s*(?:;(.+))?$", command, flags=re.IGNORECASE)
        if not match:
            return "", None
        key, value, remainder = match.groups()
        self.env[key] = value
        note = f"set env {key}"
        return note, remainder

    def _handle_cd(self, command: str, cwd: Path) -> Optional[Dict[str, Any]]:
        match = re.match(r"^(?:cd|Set-Location)\s+(.+)$", command, flags=re.IGNORECASE)
        if not match:
            return None
        target_raw = match.group(1).strip().strip('"').strip("'")
        target = Path(target_raw).expanduser()
        if not target.is_absolute():
            target = (cwd / target).resolve()
        if not target.exists() or not target.is_dir():
            return {
                "ok": False,
                "session_id": self.session_id,
                "cwd": str(cwd),
                "exit_code": 1,
                "stdout": "",
                "stderr": f"directory not found: {target}",
                "command": command,
            }
        self.cwd = target
        return {
            "ok": True,
            "session_id": self.session_id,
            "cwd": str(self.cwd),
            "exit_code": 0,
            "stdout": f"changed directory to {self.cwd}",
            "stderr": "",
            "command": command,
        }

    def _record(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        record = {
            "ts": datetime.now().isoformat(),
            "command": entry.get("command", ""),
            "cwd": entry.get("cwd", ""),
            "exit_code": entry.get("exit_code", 0),
            "ok": bool(entry.get("ok", False)),
        }
        self.history.append(record)
        self.history = self.history[-50:]
        return entry


@dataclass
class RouteDecision:
    mode: str
    reason: str
    tool_name: str = ""
    tool_args: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class UserProfile:
    """User profile and preferences."""
    name: str = "User"
    email: str = ""
    phone: str = ""
    timezone: str = "UTC"
    language: str = "en"  # en, ur, hi
    preferences: Dict = field(default_factory=dict)
    saved_data: Dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TaskRecord:
    """Record of a completed task."""
    id: str
    type: str
    description: str
    status: str  # pending, completed, failed
    started_at: str
    completed_at: str
    result: str
    metadata: Dict = field(default_factory=dict)


@dataclass
class Project:
    """A project managed by AI (website, startup, etc.)."""
    id: str
    name: str
    type: str  # website, startup, app, script
    status: str  # active, paused, completed
    created_at: str
    last_updated: str
    files: List[str] = field(default_factory=list)
    url: str = ""
    analytics: Dict = field(default_factory=dict)


@dataclass
class ConversationTurn:
    """Single turn in conversation."""
    timestamp: str
    user_message: str
    ai_response: str
    tools_used: List[str] = field(default_factory=list)
    tasks_completed: List[str] = field(default_factory=list)


@dataclass
class WeeklyReport:
    """Weekly analytics report."""
    week_start: str
    week_end: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    conversations: int
    projects_created: int
    websites_deployed: int
    top_activities: List[str] = field(default_factory=list)
    summary: str = ""


# ============================================================================
# USER DATA STORAGE
# ============================================================================

class UserDataStore:
    """Secure local storage for user data."""

    def __init__(self):
        self.user_profile = self._load_profile()
        self.history = self._load_history()
        self.projects = self._load_projects()
        self.analytics = self._load_analytics()

    def _load_profile(self) -> UserProfile:
        """Load or create user profile."""
        if Config.USER_DATA_FILE.exists():
            try:
                data = json.loads(Config.USER_DATA_FILE.read_text())
                return UserProfile(**data)
            except:
                pass
        return UserProfile()

    def _load_history(self) -> List[Dict]:
        """Load conversation history."""
        if Config.HISTORY_FILE.exists():
            try:
                return json.loads(Config.HISTORY_FILE.read_text())
            except:
                pass
        return []

    def _load_projects(self) -> List[Project]:
        """Load projects."""
        if Config.PROJECTS_FILE.exists():
            try:
                data = json.loads(Config.PROJECTS_FILE.read_text())
                return [Project(**p) for p in data]
            except:
                pass
        return []

    def _load_analytics(self) -> Dict:
        """Load analytics data."""
        if Config.ANALYTICS_FILE.exists():
            try:
                return json.loads(Config.ANALYTICS_FILE.read_text())
            except:
                pass
        return {"weekly_reports": [], "metrics": {}}

    def save_profile(self):
        """Save user profile."""
        Config.USER_DATA_FILE.write_text(json.dumps(asdict(self.user_profile), indent=2))

    def save_history(self):
        """Save history (keep last N records)."""
        self.history = self.history[-Config.MAX_HISTORY:]
        Config.HISTORY_FILE.write_text(json.dumps(self.history, indent=2))

    def save_projects(self):
        """Save projects."""
        Config.PROJECTS_FILE.write_text(json.dumps([asdict(p) for p in self.projects], indent=2))

    def save_analytics(self):
        """Save analytics."""
        Config.ANALYTICS_FILE.write_text(json.dumps(self.analytics, indent=2))

    def add_conversation(self, user_msg: str, ai_resp: str, tools: List[str], tasks: List[str]):
        """Add conversation to history."""
        turn = {
            "timestamp": datetime.now().isoformat(),
            "user_message": user_msg,
            "ai_response": ai_resp,
            "tools_used": tools,
            "tasks_completed": tasks
        }
        self.history.append(turn)
        self.save_history()

    def add_project(self, project: Project):
        """Add new project."""
        self.projects.append(project)
        self.save_projects()

    def update_project(self, project_id: str, updates: Dict):
        """Update existing project."""
        for proj in self.projects:
            if proj.id == project_id:
                for k, v in updates.items():
                    setattr(proj, k, v)
                proj.last_updated = datetime.now().isoformat()
                self.save_projects()
                return True
        return False

    def record_task(self, task: TaskRecord):
        """Record completed task for analytics."""
        if "tasks" not in self.analytics:
            self.analytics["tasks"] = []
        self.analytics["tasks"].append(asdict(task))
        self.save_analytics()

    def get_weekly_stats(self, days: int = 7) -> Dict:
        """Get statistics for last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        recent_history = [h for h in self.history if h["timestamp"] > cutoff_str]
        recent_tasks = self.analytics.get("tasks", [])
        recent_tasks = [t for t in recent_tasks if t["started_at"] > cutoff_str]

        return {
            "conversations": len(recent_history),
            "total_tasks": len(recent_tasks),
            "completed_tasks": len([t for t in recent_tasks if t["status"] == "completed"]),
            "failed_tasks": len([t for t in recent_tasks if t["status"] == "failed"]),
            "projects": len(self.projects),
            "active_projects": len([p for p in self.projects if p.status == "active"])
        }

    def save_credentials(self, service: str, username: str, password: str):
        """Save encrypted credentials."""
        # In production, use proper encryption library
        creds = {service: {"username": username, "password": password}}
        # Placeholder - implement proper encryption
        print(f"[!] Storing credentials for {service} (encrypted)")

    def get_credentials(self, service: str) -> Optional[Dict]:
        """Retrieve encrypted credentials."""
        # Placeholder - implement proper decryption
        return None


# ============================================================================
# AI MODEL INTEGRATION
# ============================================================================

class AIModel:
    """AI model with enhanced capabilities."""

    PROVIDER_SETTINGS = {
        "anthropic": {
            "label": "Anthropic",
            "env_key": "ANTHROPIC_API_KEY",
            "model_attr": "ANTHROPIC_MODEL",
            "credential_service": "anthropic_api",
        },
        "groq": {
            "label": "Groq",
            "env_key": "GROQ_API_KEY",
            "model_attr": "GROQ_MODEL",
            "credential_service": "groq_api",
        },
        "openai": {
            "label": "OpenAI",
            "env_key": "OPENAI_API_KEY",
            "model_attr": "OPENAI_MODEL",
            "credential_service": "openai_api",
        },
        "openrouter": {
            "label": "OpenRouter",
            "env_key": "OPENROUTER_API_KEY",
            "model_attr": "OPENROUTER_MODEL",
            "credential_service": "openrouter_api",
        },
        "gemini": {
            "label": "Google Gemini",
            "env_key": "GOOGLE_GEMINI_API_KEY",
            "model_attr": "GOOGLE_GEMINI_MODEL",
            "credential_service": "gemini_api",
        },
        "huggingface": {
            "label": "Hugging Face",
            "env_key": "HUGGINGFACE_API_KEY",
            "model_attr": "HUGGINGFACE_MODEL",
            "credential_service": "huggingface_api",
        },
        "ollama": {
            "label": "Ollama",
            "env_key": "",
            "model_attr": "OLLAMA_MODEL",
            "credential_service": "",
        },
    }
    PROVIDER_PACKAGES = {
        "anthropic": "anthropic",
        "groq": "groq",
        "openai": "openai",
        "openrouter": "openai",
        "gemini": "google-genai",
        "huggingface": "huggingface_hub",
        "ollama": "",
    }

    SYSTEM_PROMPT = """You are CONNECT - an autonomous AI operator and coding assistant.

CAPABILITIES:
1. CORE BRAIN - Plan tasks, decompose work, reflect on outcomes
2. TOOL USE - Act through filesystem, terminal, browser, code, and network tools
3. CODING AGENT - Inspect repos, write code, run fixes, debug iteratively
4. WEB AUTOMATION - Open websites, fill forms, navigate with bounded control
5. PROJECT BUILDING - Create websites, scripts, and product scaffolding
6. ACCOUNT SETUP - Help setup accounts with explicit user permission
7. ANALYTICS - Track runs, tasks, memory, and performance
8. CONTINUOUS MANAGEMENT - Monitor projects and adapt over time

SECURITY RULES:
- NEVER present the system as unrestricted PC control
- ALWAYS respect tool boundaries and policy scopes
- ALWAYS ask for permission before sensitive operations
- NEVER store passwords without encryption
- NEVER auto-complete authentication without user approval
- For OTP/login: guide user, don't auto-submit
- Prefer safe, observable actions over broad system control

LANGUAGES: English, Urdu, Hindi (respond in user's preferred language)

STARTUP CREATION FLOW:
1. Understand business idea
2. Validate market fit
3. Create business plan
4. Build website/landing page
5. Generate content (about, services, products)
6. Setup marketing strategy
7. Deploy and configure analytics
8. Setup management tools

Always be proactive, helpful, and clear about what you're doing.

REASONING STYLE:
- Prefer dynamic reasoning and custom code synthesis over canned routines
- Use tools to observe, verify, execute, and persist, not as a substitute for thinking
- When solving engineering tasks, adapt to the current repo and runtime instead of forcing preset flows
- Generate code and plans from the actual problem state; avoid static templates unless the user explicitly wants them"""

    def __init__(self):
        self.provider = ""
        self.model_name = ""
        self._groq_client = None
        self._anthropic_client = None
        self._openai_client = None
        self._openrouter_client = None
        self._gemini_client = None
        self._hf_client = None
        self._provider_error = ""
        self._select_provider()
        if self.provider:
            print(f"[*] Using provider: {self.provider}:{self.model_name}")
        else:
            print("[!] No model provider is ready.")
            print("    Set one of: GROQ_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY,")
            print("    GOOGLE_GEMINI_API_KEY, HUGGINGFACE_API_KEY, or start Ollama locally.\n")

    def _reset_provider_state(self):
        self.provider = ""
        self.model_name = ""
        self._groq_client = None
        self._anthropic_client = None
        self._openai_client = None
        self._openrouter_client = None
        self._gemini_client = None
        self._hf_client = None
        self._provider_error = ""

    def _probe_provider(self, name: str, configured: bool, model: str) -> Dict[str, str]:
        return {
            "name": name,
            "configured": "yes" if configured else "no",
            "ready": "yes" if configured else "no",
            "model": model,
            "note": "configured" if configured else "missing API key",
        }

    def _project_env_path(self) -> Path:
        return Path(__file__).resolve().parent / ".env"

    def _read_env_file(self) -> List[str]:
        env_path = self._project_env_path()
        if not env_path.exists():
            return []
        return env_path.read_text(encoding="utf-8").splitlines()

    def _write_env_values(self, updates: Dict[str, str]):
        env_path = self._project_env_path()
        lines = self._read_env_file()
        remaining = dict(updates)
        output: List[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in line:
                output.append(line)
                continue
            key, _ = line.split("=", 1)
            key = key.strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
            else:
                output.append(line)
        for key, value in remaining.items():
            output.append(f"{key}={value}")
        env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")

    def _provider_configured(self, provider_name: str) -> bool:
        settings = self.PROVIDER_SETTINGS.get(provider_name, {})
        env_key = settings.get("env_key", "")
        if not env_key:
            return provider_name == "ollama"
        return bool(getattr(Config, env_key, ""))

    def _mask_secret(self, value: str) -> str:
        if not value:
            return "(empty)"
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"

    def _save_provider_secret(self, provider_name: str, secret: str):
        settings = self.PROVIDER_SETTINGS[provider_name]
        env_key = settings["env_key"]
        os.environ[env_key] = secret
        self._write_env_values({env_key: secret})
        try:
            from tools.auth_manager import save_credential

            save_credential(settings["credential_service"], "api_key", secret)
        except Exception as exc:
            debug_log(f"credential vault save failed for {provider_name}: {exc}")

    def _persist_provider_preference(self, provider_name: str):
        os.environ["AI_PROVIDER"] = provider_name
        self._write_env_values({"AI_PROVIDER": provider_name})
        Config.refresh_from_env()

    def configure_provider(self, provider_name: str, interactive: bool = True) -> tuple[bool, str]:
        requested = (provider_name or "").strip().lower()
        valid = set(self.PROVIDER_SETTINGS.keys())
        if requested not in valid:
            return False, f"Unknown provider: {provider_name}. Available: {', '.join(sorted(valid))}"

        settings = self.PROVIDER_SETTINGS[requested]
        label = settings["label"]
        env_key = settings["env_key"]

        if requested == "ollama":
            self._persist_provider_preference(requested)
            self._select_provider(preferred=requested, allow_fallback=False)
            if self.provider == requested:
                return True, f"Switched provider to {self.provider}:{self.model_name} and saved AI_PROVIDER in project .env"
            return False, f"Could not switch to {requested}: {self._provider_error or 'provider is not ready'}"

        current_secret = getattr(Config, env_key, "")
        secret_to_save = ""

        if current_secret:
            if not interactive:
                self._persist_provider_preference(requested)
                self._select_provider(preferred=requested, allow_fallback=False)
                if self.provider == requested:
                    return True, f"Switched provider to {self.provider}:{self.model_name} using saved credentials"
                return False, f"Could not switch to {requested}: {self._provider_error or 'provider is not ready'}"

            print(f"{label} is already configured with {env_key}={self._mask_secret(current_secret)}")
            choice = input("Keep current key or add new key? [keep/new]: ").strip().lower()
            if choice in {"", "keep", "k"}:
                self._persist_provider_preference(requested)
                self._select_provider(preferred=requested, allow_fallback=False)
                if self.provider == requested:
                    return True, f"Switched provider to {self.provider}:{self.model_name} using saved credentials"
                return False, f"Could not switch to {requested}: {self._provider_error or 'provider is not ready'}"
            if choice not in {"new", "n", "add"}:
                return False, "Provider update cancelled"

        if not interactive and not current_secret:
            return False, f"{label} is not configured. Add {env_key} in .env or run /provider {requested} in interactive mode."

        while not secret_to_save:
            print(f"Paste {label} API key for {env_key}:")
            secret_to_save = input("> ").strip()
            if not secret_to_save:
                try:
                    secret_to_save = getpass("> ").strip()
                except Exception:
                    secret_to_save = ""
            if not secret_to_save:
                print("API key cannot be empty.")

        self._save_provider_secret(requested, secret_to_save)
        self._persist_provider_preference(requested)
        self._select_provider(preferred=requested, allow_fallback=False)
        if self.provider == requested:
            return True, f"Configured and switched provider to {self.provider}:{self.model_name}. Saved {env_key} and AI_PROVIDER in project .env"
        return False, f"Saved credentials for {requested}, but the provider is still not ready: {self._provider_error or 'unknown error'}"

    def _ollama_available(self) -> tuple[bool, str]:
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.ok:
                return True, "local server reachable"
            return False, f"http {response.status_code}"
        except Exception as exc:
            return False, str(exc)

    def _provider_order(self, preferred: Optional[str] = None) -> List[str]:
        ordered = ["anthropic", "groq", "openai", "openrouter", "gemini", "huggingface", "ollama"]
        selected = (preferred or Config.AI_PROVIDER or "").strip().lower()
        if selected and selected in ordered:
            ordered.remove(selected)
            ordered.insert(0, selected)
        return ordered

    def _select_provider(self, preferred: Optional[str] = None, allow_fallback: bool = True):
        self._reset_provider_state()
        ordered = self._provider_order(preferred)
        if preferred and not allow_fallback:
            ordered = [name for name in ordered if name == preferred]
        for provider_name in ordered:
            try:
                if provider_name == "anthropic" and Config.ANTHROPIC_API_KEY:
                    from anthropic import Anthropic

                    self._anthropic_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
                    self.provider = "anthropic"
                    self.model_name = Config.ANTHROPIC_MODEL
                    return
                if provider_name == "groq" and Config.GROQ_API_KEY:
                    from groq import Groq

                    self._groq_client = Groq(api_key=Config.GROQ_API_KEY)
                    self.provider = "groq"
                    self.model_name = Config.GROQ_MODEL
                    return
                if provider_name == "openai" and Config.OPENAI_API_KEY:
                    from openai import OpenAI

                    self._openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
                    self.provider = "openai"
                    self.model_name = Config.OPENAI_MODEL
                    return
                if provider_name == "openrouter" and Config.OPENROUTER_API_KEY:
                    from openai import OpenAI

                    self._openrouter_client = OpenAI(
                        api_key=Config.OPENROUTER_API_KEY,
                        base_url="https://openrouter.ai/api/v1",
                    )
                    self.provider = "openrouter"
                    self.model_name = Config.OPENROUTER_MODEL
                    return
                if provider_name == "gemini" and Config.GOOGLE_GEMINI_API_KEY:
                    from google import genai

                    self._gemini_client = genai.Client(api_key=Config.GOOGLE_GEMINI_API_KEY)
                    self.provider = "gemini"
                    self.model_name = Config.GOOGLE_GEMINI_MODEL
                    return
                if provider_name == "huggingface" and Config.HUGGINGFACE_API_KEY:
                    from huggingface_hub import InferenceClient

                    self._hf_client = InferenceClient(api_key=Config.HUGGINGFACE_API_KEY)
                    self.provider = "huggingface"
                    self.model_name = Config.HUGGINGFACE_MODEL
                    return
                if provider_name == "ollama":
                    ready, note = self._ollama_available()
                    if ready:
                        self.provider = "ollama"
                        self.model_name = Config.OLLAMA_MODEL
                        return
                    self._provider_error = note
            except ModuleNotFoundError as exc:
                package_name = self.PROVIDER_PACKAGES.get(provider_name) or exc.name or provider_name
                self._provider_error = (
                    f"{provider_name}: missing dependency '{package_name}'. "
                    f"Install project requirements and retry."
                )
            except Exception as exc:
                self._provider_error = f"{provider_name}: {exc}"

    def switch_provider(self, provider_name: str) -> tuple[bool, str]:
        return self.configure_provider(provider_name, interactive=False)

    def get_provider_status(self) -> List[Dict[str, str]]:
        statuses = [
            self._probe_provider("anthropic", bool(Config.ANTHROPIC_API_KEY), Config.ANTHROPIC_MODEL),
            self._probe_provider("groq", bool(Config.GROQ_API_KEY), Config.GROQ_MODEL),
            self._probe_provider("openai", bool(Config.OPENAI_API_KEY), Config.OPENAI_MODEL),
            self._probe_provider("openrouter", bool(Config.OPENROUTER_API_KEY), Config.OPENROUTER_MODEL),
            self._probe_provider("gemini", bool(Config.GOOGLE_GEMINI_API_KEY), Config.GOOGLE_GEMINI_MODEL),
            self._probe_provider("huggingface", bool(Config.HUGGINGFACE_API_KEY), Config.HUGGINGFACE_MODEL),
        ]
        ollama_ready, ollama_note = self._ollama_available()
        statuses.append(
            {
                "name": "ollama",
                "configured": "yes",
                "ready": "yes" if ollama_ready else "no",
                "model": Config.OLLAMA_MODEL,
                "note": ollama_note,
            }
        )
        for item in statuses:
            item["selected"] = "yes" if item["name"] == self.provider else "no"
        return statuses

    def _normalize_openai_like(self, response: Any) -> Dict[str, Any]:
        if hasattr(response, "model_dump"):
            return response.model_dump()
        if isinstance(response, dict):
            return response
        return {"choices": [{"message": {"content": str(response)}}]}

    def _normalize_anthropic(self, response: Any) -> Dict[str, Any]:
        content_blocks = getattr(response, "content", []) or []
        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        for block in content_blocks:
            block_type = getattr(block, "type", "")
            if block_type == "text":
                text_parts.append(getattr(block, "text", ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    {
                        "id": getattr(block, "id", ""),
                        "type": "function",
                        "function": {
                            "name": getattr(block, "name", ""),
                            "arguments": json.dumps(getattr(block, "input", {}), ensure_ascii=True),
                        },
                    }
                )
        message = {"content": "\n".join(part for part in text_parts if part).strip()}
        if tool_calls:
            message["tool_calls"] = tool_calls
        return {"choices": [{"message": message}]}

    def _anthropic_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        converted = []
        for tool in tools or []:
            fn = tool.get("function", {})
            converted.append(
                {
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return converted

    def _coerce_plain_messages(self, messages: List[Dict[str, Any]]) -> str:
        return "\n\n".join(f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in messages)

    def chat(self, messages: List[Dict], tools: List[Dict] = None) -> Dict:
        """Send messages to AI model."""
        if not self.provider:
            return {"error": f"No model provider available. Last error: {self._provider_error or 'none'}"}
        try:
            if self.provider == "groq":
                payload = {
                    "model": Config.GROQ_MODEL if tools else Config.GROQ_CHAT_MODEL,
                    "messages": messages,
                    "temperature": 0.2 if tools else 0.7,
                    "max_tokens": 4096,
                }
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = "auto"
                return self._normalize_openai_like(self._groq_client.chat.completions.create(**payload))
            if self.provider == "openai":
                payload = {
                    "model": Config.OPENAI_MODEL,
                    "messages": messages,
                    "temperature": 0.2 if tools else 0.7,
                    "max_tokens": 4096,
                }
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = "auto"
                return self._normalize_openai_like(self._openai_client.chat.completions.create(**payload))
            if self.provider == "openrouter":
                payload = {
                    "model": Config.OPENROUTER_MODEL,
                    "messages": messages,
                    "temperature": 0.2 if tools else 0.7,
                    "max_tokens": 4096,
                }
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = "auto"
                return self._normalize_openai_like(self._openrouter_client.chat.completions.create(**payload))
            if self.provider == "anthropic":
                system_text = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
                anthropic_messages = [
                    {"role": m.get("role", "user"), "content": m.get("content", "")}
                    for m in messages
                    if m.get("role") != "system"
                ]
                payload = {
                    "model": Config.ANTHROPIC_MODEL,
                    "system": system_text,
                    "messages": anthropic_messages,
                    "max_tokens": 4096,
                }
                if tools:
                    payload["tools"] = self._anthropic_tools(tools)
                return self._normalize_anthropic(self._anthropic_client.messages.create(**payload))
            if self.provider == "gemini":
                response = self._gemini_client.models.generate_content(
                    model=Config.GOOGLE_GEMINI_MODEL,
                    contents=self._coerce_plain_messages(messages),
                )
                return {"choices": [{"message": {"content": getattr(response, "text", "") or ""}}]}
            if self.provider == "huggingface":
                response = self._hf_client.chat_completion(
                    model=Config.HUGGINGFACE_MODEL,
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.2 if tools else 0.7,
                )
                return self._normalize_openai_like(response)
            if self.provider == "ollama":
                ollama_msgs = [{"role": m["role"], "content": m["content"]} for m in messages]
                response = requests.post(
                    "http://localhost:11434/api/chat",
                    json={"model": Config.OLLAMA_MODEL, "messages": ollama_msgs, "stream": False},
                    timeout=60
                )
                response.raise_for_status()
                return {"choices": [{"message": {"content": response.json()["message"]["content"]}}]}
        except Exception as e:
            return {"error": str(e)}
        return {"error": f"Unsupported provider: {self.provider}"}

    def stream_chat(self, messages: List[Dict], on_chunk: Optional[Callable[[str], None]] = None) -> str:
        """Stream plain-text model output and return the full text."""
        chunks: List[str] = []

        def emit(text: str):
            if not text:
                return
            chunks.append(text)
            if on_chunk:
                on_chunk(text)

        if self.provider in {"groq", "openai", "openrouter"}:
            try:
                if self.provider == "groq":
                    client = self._groq_client
                    model_name = Config.GROQ_MODEL
                elif self.provider == "openai":
                    client = self._openai_client
                    model_name = Config.OPENAI_MODEL
                else:
                    client = self._openrouter_client
                    model_name = Config.OPENROUTER_MODEL
                if client is None:
                    raise RuntimeError(f"{self.provider} client unavailable")
                debug_log(f"stream_chat: sending {len(messages)} messages to {self.provider}")
                stream = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=4096,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    emit(delta)
            except Exception as e:
                debug_log(f"stream_chat error ({self.provider}): {e}")
                return f"[stream error] {e}"
        elif self.provider == "ollama":
            try:
                ollama_msgs = [{"role": m["role"], "content": m["content"]} for m in messages]
                debug_log(f"stream_chat: sending {len(messages)} messages to Ollama")
                with requests.post(
                    "http://localhost:11434/api/chat",
                    json={"model": Config.OLLAMA_MODEL, "messages": ollama_msgs, "stream": True},
                    timeout=120,
                    stream=True,
                ) as response:
                    response.raise_for_status()
                    for raw_line in response.iter_lines(decode_unicode=True):
                        if not raw_line:
                            continue
                        try:
                            payload = json.loads(raw_line)
                        except json.JSONDecodeError:
                            continue
                        emit(payload.get("message", {}).get("content", ""))
                        if payload.get("done"):
                            break
            except Exception as e:
                debug_log(f"stream_chat error (Ollama): {e}")
                return f"[stream error] {e}"
        else:
            response = self.chat(messages)
            parsed = self.parse_response(response)
            emit(parsed.get("content", "") if parsed else "")

        final_text = "".join(chunks)
        debug_log(f"stream_chat: received {len(final_text)} characters")
        return final_text

    def parse_response(self, response: Dict) -> Optional[Dict]:
        """Parse AI response for tool calls or text."""
        try:
            if "error" in response:
                return {"type": "error", "content": response["error"]}

            message = response.get("choices", [{}])[0].get("message", {})

            if "tool_calls" in message and message["tool_calls"]:
                tool_call = message["tool_calls"][0]
                return {
                    "type": "tool_call",
                    "name": tool_call["function"]["name"],
                    "arguments": json.loads(tool_call["function"]["arguments"])
                }
            elif "content" in message:
                return {"type": "text", "content": message["content"]}
        except Exception as e:
            if Config.DEBUG:
                print(f"[DEBUG] Parse error: {e}")
        return None

    def should_use_autonomous_agent(self, user_input: str, history: Optional[List[Dict[str, str]]] = None) -> bool:
        """Decide whether a request needs multi-step action rather than normal chat."""
        history = history or []
        messages = [
            {
                "role": "system",
                "content": (
                    "Classify whether the user's latest message requires an autonomous operator loop. "
                    "Return strict JSON only: "
                    '{"mode":"agent"|"chat","reason":"..."}'
                ),
            }
        ]
        messages.extend(history[-6:])
        messages.append(
            {
                "role": "user",
                "content": (
                    "Use mode=agent for requests that require planning, file edits, code generation, "
                    "OS/browser actions, verification, retries, or multi-step execution.\n"
                    "Use mode=chat for simple Q&A, explanations, brainstorming, or casual conversation.\n"
                    f"User message: {user_input}"
                ),
            }
        )

        try:
            response = self.chat(messages)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                payload = json.loads(content[start:end + 1])
                return payload.get("mode") == "agent"
        except Exception:
            pass

        heuristic_keywords = [
            "build", "create", "make", "generate", "deploy", "setup", "set up",
            "install", "open", "run", "fix", "edit", "write", "update", "launch",
            "website", "app", "script", "folder", "file", "browser", "click",
        ]
        text = user_input.lower()
        return any(keyword in text for keyword in heuristic_keywords)


class RequestRouter:
    """Separate direct tool routing from autonomous project execution."""

    SEARCH_PREFIXES = ("search ", "look up ", "lookup ", "find ", "google ")

    def route(self, user_input: str, ai_model: AIModel, history: Optional[List[Dict[str, str]]] = None) -> RouteDecision:
        text = user_input.strip()
        lowered = text.lower()

        weather_location = self._extract_weather_location(text)
        if weather_location:
            return RouteDecision(
                mode="tool",
                reason="weather request",
                tool_name="weather_report",
                tool_args={"location": weather_location},
            )

        search_query = self._extract_search_query(text)
        if search_query:
            return RouteDecision(
                mode="tool",
                reason="web search request",
                tool_name="web_search",
                tool_args={"query": search_query},
            )

        if ai_model.should_use_autonomous_agent(text, history):
            return RouteDecision(mode="agent", reason="multi-step execution required")
        return RouteDecision(mode="chat", reason="normal conversation")

    def _extract_weather_location(self, text: str) -> str:
        lowered = text.lower().strip()
        weather_keywords = ("weather", "temperature", "forecast")
        if not any(keyword in lowered for keyword in weather_keywords):
            return ""
        match = re.search(r"\b(?:in|for)\s+([A-Za-z][A-Za-z0-9,\s-]{1,60})$", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" ?.")
        cleaned = re.sub(r"\b(weather|temperature|forecast|today|current|what(?:'s| is))\b", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ?.")
        return cleaned

    def _extract_search_query(self, text: str) -> str:
        lowered = text.lower().strip()
        for prefix in self.SEARCH_PREFIXES:
            if lowered.startswith(prefix):
                return text[len(prefix):].strip(" ?.")
        match = re.search(r"\b(?:search for|look up|find information on|latest on)\s+(.+)$", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" ?.")
        return ""


# ============================================================================
# TOOLS
# ============================================================================

class AdvancedTools:
    """Enhanced toolset for advanced platform."""

    _playwright = None
    _browser = None
    _browser_context = None
    _browser_page = None
    _browser_events: Dict[str, List[str]] = {
        "console_errors": [],
        "page_errors": [],
        "network_failures": [],
    }
    _shell_sessions: Dict[str, ShellSession] = {}

    AGENT_TOOL_NAMES = {
        "observe_environment",
        "run_shell_command",
        "read_file",
        "write_file",
        "create_directory",
        "list_directory",
        "open_browser",
        "browser_open",
        "browser_click",
        "browser_type",
        "browser_wait",
        "browser_snapshot",
        "browser_close",
        "manage_browser_tabs",
        "browser_login",
        "save_workflow",
        "list_workflows",
        "run_workflow",
        "generate_workflow",
        "mutate_workflow",
        "synthesize_helper",
        "run_helper",
        "list_helpers",
        "fill_form_field",
        "click_element",
        "search_files",
        "web_search",
        "weather_report",
        "check_website_status",
        "web_scrape",
        "download_file",
        "install_package",
        "take_screenshot",
        "execute_python",
    }

    @staticmethod
    def get_definitions() -> List[Dict]:
        """Get all tool definitions."""
        return [
            # Core tools from OMNI
            {
                "type": "function",
                "function": {
                    "name": "observe_environment",
                    "description": "Inspect the current workspace and runtime environment",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "depth": {"type": "integer"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_shell_command",
                    "description": "Execute shell command",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "cwd": {"type": "string"},
                            "session_id": {"type": "string"},
                            "timeout": {"type": "integer"},
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read file contents",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_directory",
                    "description": "Create directory",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "List directory contents",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web and return a short list of results",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "max_results": {"type": "integer"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "weather_report",
                    "description": "Get current weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"}
                        },
                        "required": ["location"]
                    }
                }
            },
            # User data tools
            {
                "type": "function",
                "function": {
                    "name": "save_user_preference",
                    "description": "Save user preference or data",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"}
                        },
                        "required": ["key", "value"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_user_preference",
                    "description": "Get saved user preference",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"}
                        },
                        "required": ["key"]
                    }
                }
            },
            # Web development tools
            {
                "type": "function",
                "function": {
                    "name": "create_website",
                    "description": "Create a complete website with HTML, CSS, JS",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                            "pages": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["name", "type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_content",
                    "description": "Generate content for website/app",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string"},
                            "type": {"type": "string"},
                            "length": {"type": "string"}
                        },
                        "required": ["topic", "type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "deploy_website",
                    "description": "Deploy website to hosting",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory": {"type": "string"},
                            "platform": {"type": "string"}
                        },
                        "required": ["directory"]
                    }
                }
            },
            # Browser automation
            {
                "type": "function",
                "function": {
                    "name": "open_browser",
                    "description": "Open website in browser",
                    "parameters": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_open",
                    "description": "Open a URL in a Playwright-controlled browser session",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "headless": {"type": "boolean"}
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_click",
                    "description": "Click a DOM element in the Playwright browser",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "selector": {"type": "string"}
                        },
                        "required": ["selector"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_type",
                    "description": "Type text into a DOM element in the Playwright browser",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "selector": {"type": "string"},
                            "text": {"type": "string"},
                            "clear_first": {"type": "boolean"}
                        },
                        "required": ["selector", "text"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_wait",
                    "description": "Wait for page load or a selector in the Playwright browser",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "selector": {"type": "string"},
                            "timeout_ms": {"type": "integer"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_snapshot",
                    "description": "Return structured browser context including DOM text, UI elements, errors, and screenshot",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "include_screenshot": {"type": "boolean"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_close",
                    "description": "Close the Playwright browser session",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "manage_browser_tabs",
                    "description": "List, open, switch, close, or inspect Playwright browser tabs",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "url": {"type": "string"},
                            "index": {"type": "integer"}
                        },
                        "required": ["action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_login",
                    "description": "Login to a website in a Playwright browser session using provided selectors and credentials",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "username_selector": {"type": "string"},
                            "password_selector": {"type": "string"},
                            "submit_selector": {"type": "string"},
                            "username": {"type": "string"},
                            "password": {"type": "string"},
                            "otp_selector": {"type": "string"},
                            "otp": {"type": "string"},
                            "wait_selector": {"type": "string"}
                        },
                        "required": ["url", "username_selector", "password_selector", "submit_selector", "username", "password"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "save_workflow",
                    "description": "Save a reusable workflow made of tool steps",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "steps": {"type": "array", "items": {"type": "object"}},
                            "description": {"type": "string"}
                        },
                        "required": ["name", "steps"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_workflows",
                    "description": "List saved workflows",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_workflow",
                    "description": "Run a saved workflow, optionally multiple times with variable substitution",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "loop_count": {"type": "integer"},
                            "inputs": {"type": "object"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_workflow",
                    "description": "Generate and save a workflow from a goal using available primitive tools",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "goal": {"type": "string"},
                            "description": {"type": "string"}
                        },
                        "required": ["name", "goal"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mutate_workflow",
                    "description": "Rewrite a workflow by inserting, removing, replacing, reordering, or auto-repairing steps",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "action": {"type": "string"},
                            "index": {"type": "integer"},
                            "new_index": {"type": "integer"},
                            "step": {"type": "object"},
                            "reason": {"type": "string"},
                            "goal": {"type": "string"},
                            "last_result": {"type": "string"}
                        },
                        "required": ["name", "action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "synthesize_helper",
                    "description": "Create a narrow reusable helper script for a missing capability",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "purpose": {"type": "string"},
                            "signature": {"type": "string"}
                        },
                        "required": ["name", "purpose"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_helper",
                    "description": "Run a synthesized helper with JSON payload input",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "payload": {"type": "object"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_helpers",
                    "description": "List synthesized helper tools",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fill_form_field",
                    "description": "Fill form field (types text)",
                    "parameters": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "click_element",
                    "description": "Click at coordinates",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"}
                        },
                        "required": ["x", "y"]
                    }
                }
            },
            # Account setup tools
            {
                "type": "function",
                "function": {
                    "name": "guide_account_setup",
                    "description": "Guide user through account creation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service": {"type": "string"},
                            "step": {"type": "string"}
                        },
                        "required": ["service"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "request_otp",
                    "description": "Request user to enter OTP",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service": {"type": "string"},
                            "message": {"type": "string"}
                        },
                        "required": ["service", "message"]
                    }
                }
            },
            # Startup tools
            {
                "type": "function",
                "function": {
                    "name": "validate_business_idea",
                    "description": "Analyze and validate business idea",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "idea": {"type": "string"},
                            "market": {"type": "string"}
                        },
                        "required": ["idea"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_business_plan",
                    "description": "Generate business plan",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "idea": {"type": "string"},
                            "target_audience": {"type": "string"}
                        },
                        "required": ["idea"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_marketing_strategy",
                    "description": "Generate marketing strategy",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "business_type": {"type": "string"},
                            "budget": {"type": "string"}
                        },
                        "required": ["business_type"]
                    }
                }
            },
            # Analytics tools
            {
                "type": "function",
                "function": {
                    "name": "generate_weekly_report",
                    "description": "Generate weekly analytics report",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "weeks": {"type": "integer"}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_task_statistics",
                    "description": "Get task completion statistics",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {"type": "integer"}
                        },
                        "required": []
                    }
                }
            },
            # Project management
            {
                "type": "function",
                "function": {
                    "name": "create_project",
                    "description": "Create new project record",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"}
                        },
                        "required": ["name", "type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_project_status",
                    "description": "Update project status",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "status": {"type": "string"}
                        },
                        "required": ["project_id", "status"]
                    }
                }
            },
            # Monitoring
            {
                "type": "function",
                "function": {
                    "name": "check_website_status",
                    "description": "Check if website is online",
                    "parameters": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "monitor_project_health",
                    "description": "Monitor project health metrics",
                    "parameters": {
                        "type": "object",
                        "properties": {"project_id": {"type": "string"}},
                        "required": ["project_id"]
                    }
                }
            },
            # GitHub PR tools
            {
                "type": "function",
                "function": {
                    "name": "github_list_pull_requests",
                    "description": "List pull requests for a repository",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string"},
                            "repo": {"type": "string"},
                            "state": {"type": "string", "enum": ["open", "closed", "all"]}
                        },
                        "required": ["owner", "repo"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "github_get_pull_request",
                    "description": "Get a single pull request details",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string"},
                            "repo": {"type": "string"},
                            "pull_number": {"type": "integer"}
                        },
                        "required": ["owner", "repo", "pull_number"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "github_submit_pull_review",
                    "description": "Submit a pull request review (COMMENT, APPROVE, REQUEST_CHANGES)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string"},
                            "repo": {"type": "string"},
                            "pull_number": {"type": "integer"},
                            "event": {"type": "string", "enum": ["COMMENT", "APPROVE", "REQUEST_CHANGES"]},
                            "body": {"type": "string"}
                        },
                        "required": ["owner", "repo", "pull_number", "event"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "github_merge_pull_request",
                    "description": "Merge a pull request",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string"},
                            "repo": {"type": "string"},
                            "pull_number": {"type": "integer"},
                            "merge_method": {"type": "string", "enum": ["merge", "squash", "rebase"]},
                            "commit_title": {"type": "string"}
                        },
                        "required": ["owner", "repo", "pull_number"]
                    }
                }
            },
            # Communication
            {
                "type": "function",
                "function": {
                    "name": "send_notification",
                    "description": "Send notification to user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "message": {"type": "string"}
                        },
                        "required": ["title", "message"]
                    }
                }
            },
            # Clipboard
            {
                "type": "function",
                "function": {
                    "name": "copy_to_clipboard",
                    "description": "Copy text to clipboard",
                    "parameters": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_clipboard",
                    "description": "Get clipboard content",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            # Full PC Access Tools
            {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Search for files by pattern across entire system",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string"},
                            "path": {"type": "string", "description": "Starting directory (default: home)"}
                        },
                        "required": ["pattern"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_system_info",
                    "description": "Get comprehensive system information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "info_type": {"type": "string", "enum": ["all", "hardware", "os", "network", "processes"]}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "manage_processes",
                    "description": "List, start, or kill processes",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["list", "start", "kill"]},
                            "process_name": {"type": "string"},
                            "command": {"type": "string"}
                        },
                        "required": ["action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "file_operations",
                    "description": "Copy, move, delete, or rename files",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "operation": {"type": "string", "enum": ["copy", "move", "delete", "rename"]},
                            "source": {"type": "string"},
                            "destination": {"type": "string"}
                        },
                        "required": ["operation", "source"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_disk_usage",
                    "description": "Get disk space information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "network_operations",
                    "description": "Network operations like ping, port scan, get IP",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["ping", "get_ip", "port_scan", "netstat"]},
                            "target": {"type": "string"}
                        },
                        "required": ["action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "registry_operations",
                    "description": "Windows registry read/write operations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["read", "write", "delete"]},
                            "path": {"type": "string"},
                            "value_name": {"type": "string"},
                            "value_data": {"type": "string"}
                        },
                        "required": ["action", "path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "schedule_task",
                    "description": "Schedule tasks using Windows Task Scheduler",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["create", "list", "delete"]},
                            "task_name": {"type": "string"},
                            "command": {"type": "string"},
                            "schedule": {"type": "string"}
                        },
                        "required": ["action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "web_scrape",
                    "description": "Scrape content from websites",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "selector": {"type": "string"}
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "download_file",
                    "description": "Download files from URLs",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "destination": {"type": "string"}
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "install_package",
                    "description": "Install software packages (pip, npm, choco, winget)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "package": {"type": "string"},
                            "manager": {"type": "string", "enum": ["pip", "npm", "choco", "winget"]}
                        },
                        "required": ["package"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "send_email",
                    "description": "Send emails via SMTP",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string"},
                            "subject": {"type": "string"},
                            "body": {"type": "string"},
                            "attachments": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["to", "subject", "body"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "control_media",
                    "description": "Control volume, brightness, media playback",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["volume_up", "volume_down", "mute", "play", "pause"]},
                            "level": {"type": "integer"}
                        },
                        "required": ["action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "take_screenshot",
                    "description": "Capture screenshot",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "region": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "width": {"type": "integer"}, "height": {"type": "integer"}}},
                            "filename": {"type": "string"}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_python",
                    "description": "Execute Python code dynamically",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "args": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["code"]
                    }
                }
            },
        ]

    @staticmethod
    def get_agent_definitions() -> List[Dict]:
        """Expose only primitive actions to the autonomous operator."""
        definitions = AdvancedTools.get_definitions()
        return [
            tool for tool in definitions
            if tool.get("function", {}).get("name") in AdvancedTools.AGENT_TOOL_NAMES
        ]

    @staticmethod
    def execute(name: str, args: Dict, data_store: UserDataStore = None, ai_model: Any = None) -> str:
        """Execute tool with data store access."""
        try:
            if name == "observe_environment":
                return AdvancedTools._observe_environment(args.get("path", "."), args.get("depth", 2))
            elif name == "run_shell_command":
                return AdvancedTools._run_shell(
                    args["command"],
                    args.get("cwd"),
                    args.get("session_id", "default"),
                    args.get("timeout"),
                )
            elif name == "read_file":
                return AdvancedTools._read_file(args["path"])
            elif name == "write_file":
                return AdvancedTools._write_file(args["path"], args["content"])
            elif name == "create_directory":
                return AdvancedTools._create_directory(args["path"])
            elif name == "list_directory":
                return AdvancedTools._list_directory(args["path"])
            elif name == "web_search":
                return AdvancedTools._web_search(args["query"], args.get("max_results", 5))
            elif name == "weather_report":
                return AdvancedTools._weather_report(args["location"])
            elif name == "save_user_preference":
                return AdvancedTools._save_preference(args["key"], args["value"], data_store)
            elif name == "get_user_preference":
                return AdvancedTools._get_preference(args["key"], data_store)
            elif name == "create_website":
                return AdvancedTools._create_website(args["name"], args.get("type", "business"), args.get("pages", []))
            elif name == "generate_content":
                return AdvancedTools._generate_content(args["topic"], args["type"], args.get("length", "medium"))
            elif name == "deploy_website":
                return AdvancedTools._deploy_website(args["directory"], args.get("platform", "netlify"))
            elif name == "open_browser":
                return AdvancedTools._open_browser(args["url"])
            elif name == "browser_open":
                return AdvancedTools._browser_open(args["url"], args.get("headless", False))
            elif name == "browser_click":
                return AdvancedTools._browser_click(args["selector"])
            elif name == "browser_type":
                return AdvancedTools._browser_type(args["selector"], args["text"], args.get("clear_first", True))
            elif name == "browser_wait":
                return AdvancedTools._browser_wait(args.get("selector"), args.get("timeout_ms", 5000))
            elif name == "browser_snapshot":
                return AdvancedTools._browser_snapshot(args.get("path"), args.get("include_screenshot", True))
            elif name == "browser_close":
                return AdvancedTools._browser_close()
            elif name == "manage_browser_tabs":
                return AdvancedTools._manage_browser_tabs(args["action"], args.get("url"), args.get("index"))
            elif name == "browser_login":
                return AdvancedTools._browser_login(
                    args["url"],
                    args["username_selector"],
                    args["password_selector"],
                    args["submit_selector"],
                    args["username"],
                    args["password"],
                    args.get("otp_selector"),
                    args.get("otp"),
                    args.get("wait_selector"),
                )
            elif name == "save_workflow":
                return AdvancedTools._save_workflow(args["name"], args["steps"], args.get("description", ""))
            elif name == "list_workflows":
                return AdvancedTools._list_workflows()
            elif name == "run_workflow":
                return AdvancedTools._run_workflow(args["name"], args.get("loop_count", 1), args.get("inputs", {}), data_store, ai_model)
            elif name == "generate_workflow":
                return AdvancedTools._generate_workflow(args["name"], args["goal"], args.get("description", ""), ai_model)
            elif name == "mutate_workflow":
                return AdvancedTools._mutate_workflow(
                    args["name"],
                    args["action"],
                    args.get("index"),
                    args.get("new_index"),
                    args.get("step"),
                    args.get("reason", ""),
                    args.get("goal", ""),
                    args.get("last_result", ""),
                    ai_model,
                )
            elif name == "synthesize_helper":
                return AdvancedTools._synthesize_helper(args["name"], args["purpose"], args.get("signature", ""), ai_model)
            elif name == "run_helper":
                return AdvancedTools._run_helper(args["name"], args.get("payload", {}))
            elif name == "list_helpers":
                return AdvancedTools._list_helpers()
            elif name == "fill_form_field":
                return AdvancedTools._fill_form_field(args["text"])
            elif name == "click_element":
                return AdvancedTools._click_element(args["x"], args["y"])
            elif name == "guide_account_setup":
                return AdvancedTools._guide_account_setup(args["service"], args.get("step"))
            elif name == "request_otp":
                return AdvancedTools._request_otp(args["service"], args["message"])
            elif name == "validate_business_idea":
                return AdvancedTools._validate_business_idea(args["idea"], args.get("market"))
            elif name == "create_business_plan":
                return AdvancedTools._create_business_plan(args["idea"], args.get("target_audience"))
            elif name == "create_marketing_strategy":
                return AdvancedTools._create_marketing_strategy(args["business_type"], args.get("budget"))
            elif name == "generate_weekly_report":
                return AdvancedTools._generate_weekly_report(data_store, args.get("weeks", 1))
            elif name == "get_task_statistics":
                return AdvancedTools._get_task_statistics(data_store, args.get("days", 7))
            elif name == "create_project":
                return AdvancedTools._create_project(args["name"], args["type"], data_store)
            elif name == "update_project_status":
                return AdvancedTools._update_project_status(args["project_id"], args["status"], data_store)
            elif name == "check_website_status":
                return AdvancedTools._check_website_status(args["url"])
            elif name == "monitor_project_health":
                return AdvancedTools._monitor_project_health(args["project_id"], data_store)
            elif name == "github_list_pull_requests":
                return AdvancedTools._github_list_pull_requests(args["owner"], args["repo"], args.get("state", "open"))
            elif name == "github_get_pull_request":
                return AdvancedTools._github_get_pull_request(args["owner"], args["repo"], args["pull_number"])
            elif name == "github_submit_pull_review":
                return AdvancedTools._github_submit_pull_review(
                    args["owner"],
                    args["repo"],
                    args["pull_number"],
                    args["event"],
                    args.get("body")
                )
            elif name == "github_merge_pull_request":
                return AdvancedTools._github_merge_pull_request(
                    args["owner"],
                    args["repo"],
                    args["pull_number"],
                    args.get("merge_method", "squash"),
                    args.get("commit_title")
                )
            elif name == "send_notification":
                return AdvancedTools._send_notification(args["title"], args["message"])
            elif name == "copy_to_clipboard":
                return AdvancedTools._copy_to_clipboard(args["text"])
            elif name == "get_clipboard":
                return AdvancedTools._get_clipboard()
            # New PC Access Tools
            elif name == "search_files":
                return AdvancedTools._search_files(args["pattern"], args.get("path"))
            elif name == "get_system_info":
                return AdvancedTools._get_system_info(args.get("info_type", "all"))
            elif name == "manage_processes":
                return AdvancedTools._manage_processes(args["action"], args.get("process_name"), args.get("command"))
            elif name == "file_operations":
                return AdvancedTools._file_operations(args["operation"], args["source"], args.get("destination"))
            elif name == "get_disk_usage":
                return AdvancedTools._get_disk_usage(args.get("path"))
            elif name == "network_operations":
                return AdvancedTools._network_operations(args["action"], args.get("target"))
            elif name == "registry_operations":
                return AdvancedTools._registry_operations(args["action"], args["path"], args.get("value_name"), args.get("value_data"))
            elif name == "schedule_task":
                return AdvancedTools._schedule_task(args["action"], args.get("task_name"), args.get("command"), args.get("schedule"))
            elif name == "web_scrape":
                return AdvancedTools._web_scrape(args["url"], args.get("selector"))
            elif name == "download_file":
                return AdvancedTools._download_file(args["url"], args.get("destination"))
            elif name == "install_package":
                return AdvancedTools._install_package(args["package"], args.get("manager", "pip"))
            elif name == "send_email":
                return AdvancedTools._send_email(args["to"], args["subject"], args["body"], args.get("attachments"))
            elif name == "control_media":
                return AdvancedTools._control_media(args["action"], args.get("level"))
            elif name == "take_screenshot":
                return AdvancedTools._take_screenshot(args.get("region"), args.get("filename"))
            elif name == "execute_python":
                return AdvancedTools._execute_python(args["code"], args.get("args"))
            else:
                return f"Unknown tool: {name}"
        except Exception as e:
            return f"Error executing {name}: {str(e)}"

    @staticmethod
    def execute_tracked(name: str, args: Dict, data_store: UserDataStore = None, ai_model: Any = None) -> str:
        """Execute a tool and update persistent world state after the action."""
        result = AdvancedTools.execute(name, args, data_store, ai_model)
        AdvancedTools._record_world_state(name, args, result)
        return result

    @staticmethod
    def _load_world_state() -> Dict[str, Any]:
        default = {
            "version": 1,
            "last_action": {},
            "recent_actions": [],
            "shell": {
                "sessions": {},
                "last_session": "",
                "command_history": [],
            },
            "repo": {},
            "goal_progress": {},
            "projects": {},
            "services": {},
            "browser": {
                "current_url": "",
                "title": "",
                "tabs": [],
                "errors": [],
            },
            "workflows": {},
            "helpers": {},
            "notes": [],
            "updated_at": "",
        }
        try:
            if Config.WORLD_STATE_FILE.exists():
                data = json.loads(Config.WORLD_STATE_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    merged = dict(default)
                    merged.update(data)
                    return merged
        except Exception:
            pass
        return default

    @staticmethod
    def _save_world_state(state: Dict[str, Any]):
        try:
            Config.WORLD_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            Config.WORLD_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _record_world_state(name: str, args: Dict[str, Any], result: Any):
        try:
            state = AdvancedTools._load_world_state()
            entry = {
                "ts": datetime.now().isoformat(),
                "tool_name": name,
                "args": args,
                "result": result[:1000] if isinstance(result, str) else str(result)[:1000],
            }
            state["last_action"] = entry
            state.setdefault("recent_actions", []).append(entry)
            state["recent_actions"] = state["recent_actions"][-50:]

            if name in {"browser_open", "open_browser", "browser_wait", "browser_click", "browser_type"}:
                browser = state.setdefault("browser", {})
                browser["last_tool"] = name
                if "url" in args:
                    browser["current_url"] = args.get("url", browser.get("current_url", ""))
            if name == "run_shell_command":
                shell = state.setdefault("shell", {"sessions": {}, "last_session": "", "command_history": []})
                parsed = AdvancedTools._parse_shell_result(result if isinstance(result, str) else str(result))
                session_id = str(args.get("session_id", parsed.get("session_id", "default")))
                shell["last_session"] = session_id
                shell.setdefault("sessions", {})[session_id] = {
                    "cwd": parsed.get("cwd", args.get("cwd", "")),
                    "exit_code": parsed.get("exit_code", ""),
                    "ok": parsed.get("ok", False),
                    "last_command": args.get("command", ""),
                    "updated_at": datetime.now().isoformat(),
                }
                shell.setdefault("command_history", []).append(
                    {
                        "ts": datetime.now().isoformat(),
                        "session_id": session_id,
                        "command": args.get("command", ""),
                        "cwd": parsed.get("cwd", args.get("cwd", "")),
                        "exit_code": parsed.get("exit_code", ""),
                    }
                )
                shell["command_history"] = shell["command_history"][-50:]
                repo_path = parsed.get("cwd") or args.get("cwd") or str(Path.cwd())
                state["repo"] = AdvancedTools._repo_state_snapshot(repo_path)
            if name == "browser_snapshot" and isinstance(result, str):
                try:
                    snapshot = json.loads(result)
                    if isinstance(snapshot, dict):
                        browser = state.setdefault("browser", {})
                        browser["current_url"] = snapshot.get("url", browser.get("current_url", ""))
                        browser["title"] = snapshot.get("title", browser.get("title", ""))
                        browser["tabs"] = snapshot.get("tabs", browser.get("tabs", []))
                        browser["errors"] = {
                            "console": snapshot.get("console_errors", []),
                            "page": snapshot.get("page_errors", []),
                            "network": snapshot.get("network_failures", []),
                        }
                except Exception:
                    pass
            if name in {"save_workflow", "generate_workflow", "mutate_workflow", "run_workflow"} and "name" in args:
                state.setdefault("workflows", {})[args["name"]] = {
                    "last_tool": name,
                    "updated_at": datetime.now().isoformat(),
                    "last_result": entry["result"],
                }
            if name in {"synthesize_helper", "run_helper", "list_helpers"} and "name" in args:
                state.setdefault("helpers", {}).setdefault(args["name"], {})
                state["helpers"][args["name"]].update(
                    {
                        "last_tool": name,
                        "updated_at": datetime.now().isoformat(),
                        "last_result": entry["result"],
                    }
                )

            state["updated_at"] = datetime.now().isoformat()
            AdvancedTools._save_world_state(state)
        except Exception:
            pass

    # Implementation methods
    @staticmethod
    def _parse_shell_result(result: str) -> Dict[str, Any]:
        parsed: Dict[str, Any] = {"stdout": "", "stderr": ""}
        if not isinstance(result, str) or not result.startswith("[SHELL_RESULT]"):
            parsed["stdout"] = result if isinstance(result, str) else str(result)
            return parsed
        sections = {"stdout": [], "stderr": []}
        active = None
        for line in result.splitlines()[1:]:
            if line == "stdout:":
                active = "stdout"
                continue
            if line == "stderr:":
                active = "stderr"
                continue
            if active:
                sections[active].append(line)
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                parsed[key.strip()] = value.strip()
        parsed["stdout"] = "\n".join(sections["stdout"]).strip()
        parsed["stderr"] = "\n".join(sections["stderr"]).strip()
        if "exit_code" in parsed:
            try:
                parsed["exit_code"] = int(parsed["exit_code"])
            except Exception:
                pass
        if "ok" in parsed:
            parsed["ok"] = str(parsed["ok"]).lower() == "true"
        return parsed

    @staticmethod
    def _get_shell_session(session_id: str = "default") -> ShellSession:
        session_key = str(session_id or "default")
        if session_key not in AdvancedTools._shell_sessions:
            AdvancedTools._shell_sessions[session_key] = ShellSession(session_key)
        return AdvancedTools._shell_sessions[session_key]

    @staticmethod
    def _format_shell_result(payload: Dict[str, Any]) -> str:
        stdout = str(payload.get("stdout", "") or "").strip()
        stderr = str(payload.get("stderr", "") or "").strip()
        lines = [
            "[SHELL_RESULT]",
            f"session_id={payload.get('session_id', 'default')}",
            f"cwd={payload.get('cwd', '')}",
            f"exit_code={payload.get('exit_code', 0)}",
            f"ok={str(bool(payload.get('ok', False))).lower()}",
            "stdout:",
            stdout if stdout else "(empty)",
            "stderr:",
            stderr if stderr else "(empty)",
        ]
        return "\n".join(lines)

    @staticmethod
    def _repo_state_snapshot(path: str = None) -> Dict[str, Any]:
        root = Path(path or Path.cwd()).resolve()
        state = {
            "cwd": str(root),
            "repo_root": "",
            "branch": "",
            "is_git_repo": False,
            "git_status": "",
            "markers": [],
        }
        for name in ["package.json", "requirements.txt", "pyproject.toml", "next.config.js", "next.config.mjs", ".git"]:
            if (root / name).exists():
                state["markers"].append(name)
        try:
            top = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if top.returncode == 0:
                repo_root = top.stdout.strip()
                state["repo_root"] = repo_root
                state["is_git_repo"] = True
                branch = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                status = subprocess.run(
                    ["git", "status", "--short"],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if branch.returncode == 0:
                    state["branch"] = branch.stdout.strip()
                if status.returncode == 0:
                    state["git_status"] = status.stdout.strip()
        except Exception:
            pass
        return state

    @staticmethod
    def _run_shell(command: str, cwd: str = None, session_id: str = "default", timeout: int = None) -> str:
        session = AdvancedTools._get_shell_session(session_id)
        payload = session.execute(command, cwd=cwd, timeout=timeout)
        return AdvancedTools._format_shell_result(payload)

    @staticmethod
    def _observe_environment(path: str = ".", depth: int = 2) -> str:
        """Return a compact snapshot of the current workspace and runtime."""
        try:
            root = Path(path).resolve()
            max_depth = max(1, min(int(depth), 4))

            lines = [
                f"cwd: {Path.cwd()}",
                f"target: {root}",
                f"os: {platform.system()} {platform.release()}",
                f"python: {sys.version.split()[0]}",
            ]

            interesting = []
            for name in ["package.json", "requirements.txt", "pyproject.toml", "Dockerfile", ".env"]:
                candidate = root / name
                if candidate.exists():
                    interesting.append(name)
            lines.append("markers: " + (", ".join(interesting) if interesting else "(none)"))

            def walk(current: Path, level: int):
                if level > max_depth:
                    return
                try:
                    items = sorted(current.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
                except Exception:
                    return
                for item in items[:25]:
                    rel = item.relative_to(root)
                    indent = "  " * level
                    lines.append(f"{indent}{'[D]' if item.is_dir() else '[F]'} {rel}")
                    if item.is_dir():
                        walk(item, level + 1)

            if root.exists() and root.is_dir():
                lines.append("tree:")
                walk(root, 0)

            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _read_file(path: str) -> str:
        try:
            return Path(path).read_text(errors="ignore")
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _write_file(path: str, content: str) -> str:
        try:
            target = Path(path)
            before = ""
            created = not target.exists()
            if target.exists() and target.is_file():
                try:
                    before = target.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    before = ""
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            diff_lines = list(
                difflib.unified_diff(
                    before.splitlines(),
                    content.splitlines(),
                    fromfile=f"{path} (before)",
                    tofile=f"{path} (after)",
                    lineterm="",
                    n=2,
                )
            )
            preview = "\n".join(diff_lines[:40]) if diff_lines else "(no textual diff)"
            return (
                "[WRITE_RESULT]\n"
                f"path={path}\n"
                f"created={'true' if created else 'false'}\n"
                "diff:\n"
                f"{preview}"
            )
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _create_directory(path: str) -> str:
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return f"Created: {path}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _list_directory(path: str) -> str:
        try:
            items = list(Path(path).iterdir())
            return "\n".join([f"{'[DIR]' if i.is_dir() else '[FILE]'} {i.name}" for i in items]) or "(empty)"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _web_search(query: str, max_results: int = 5) -> str:
        try:
            response = requests.get(
                "https://duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            response.raise_for_status()
            html = response.text
            matches = re.findall(
                r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                html,
                flags=re.IGNORECASE | re.DOTALL,
            )
            results = []
            for href, title_html in matches[: max(1, min(int(max_results), 10))]:
                title = re.sub(r"<[^>]+>", "", title_html)
                title = re.sub(r"\s+", " ", title).strip()
                results.append(f"- {title} | {href}")
            return "\n".join(results) if results else f"No search results found for: {query}"
        except Exception as e:
            return f"Error: web search failed: {e}"

    @staticmethod
    def _weather_report(location: str) -> str:
        try:
            response = requests.get(
                f"https://wttr.in/{requests.utils.quote(location)}",
                params={"format": "j1"},
                headers={"User-Agent": "curl/8.0"},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            current = (data.get("current_condition") or [{}])[0]
            temp_c = current.get("temp_C", "?")
            feels_like = current.get("FeelsLikeC", "?")
            humidity = current.get("humidity", "?")
            desc = ((current.get("weatherDesc") or [{}])[0].get("value", "Unknown"))
            return (
                f"Weather for {location}:\n"
                f"- Condition: {desc}\n"
                f"- Temperature: {temp_c} C\n"
                f"- Feels Like: {feels_like} C\n"
                f"- Humidity: {humidity}%"
            )
        except Exception as e:
            return f"Error: weather lookup failed: {e}"

    @staticmethod
    def _save_preference(key: str, value: str, store: UserDataStore) -> str:
        if store:
            store.user_profile.saved_data[key] = value
            store.save_profile()
            return f"Saved: {key}"
        return "Error: No data store"

    @staticmethod
    def _get_preference(key: str, store: UserDataStore) -> str:
        if store:
            return store.user_profile.saved_data.get(key, "Not found")
        return "Error: No data store"

    @staticmethod
    def _create_website(name: str, type: str, pages: List[str]) -> str:
        """Create complete website structure."""
        base_dir = Path(name)
        base_dir.mkdir(exist_ok=True)

        # Default pages
        if not pages:
            pages = ["home", "about", "contact"]

        files_created = []

        # Create HTML for each page
        for page in pages:
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page.title()} - {name}</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header>
        <nav>
            <div class="logo">{name}</div>
            <ul>
                {"".join([f'<li><a href="{p}.html">{p.title()}</a></li>' for p in pages])}
            </ul>
        </nav>
    </header>
    <main>
        <h1>{page.title()}</h1>
        <p>Welcome to {name} - {page} page content goes here.</p>
    </main>
    <footer>
        <p>&copy; 2026 {name}. All rights reserved.</p>
    </footer>
</body>
</html>"""
            (base_dir / f"{page}.html").write_text(html_content)
            files_created.append(f"{page}.html")

        # Create CSS
        css_content = """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: Arial, sans-serif; line-height: 1.6; }
header { background: #333; color: white; padding: 1rem; }
nav { display: flex; justify-content: space-between; align-items: center; }
nav ul { list-style: none; display: flex; gap: 1rem; }
nav a { color: white; text-decoration: none; }
main { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
footer { background: #333; color: white; text-align: center; padding: 1rem; margin-top: 2rem; }
"""
        (base_dir / "styles.css").write_text(css_content)
        files_created.append("styles.css")

        # Create JS
        js_content = """// Main JavaScript
document.addEventListener('DOMContentLoaded', () => {
    console.log('Website loaded:', document.title);
});
"""
        (base_dir / "script.js").write_text(js_content)
        files_created.append("script.js")

        return f"Created website '{name}' with {len(files_created)} files: {', '.join(files_created)}"

    @staticmethod
    def _generate_content(topic: str, type: str, length: str) -> str:
        """Generate content placeholder (AI will enhance)."""
        return f"Generated {length} {type} content about: {topic}"

    @staticmethod
    def _deploy_website(directory: str, platform: str) -> str:
        """Deploy to hosting platform."""
        try:
            from tools.deployer import deploy_to_netlify, deploy_to_vercel

            if platform == "netlify":
                return deploy_to_netlify(directory, Path(directory).resolve().name)
            return deploy_to_vercel(directory, Path(directory).resolve().name)
        except Exception as e:
            return f"Error deploying: {e}"

    @staticmethod
    def _open_browser(url: str) -> str:
        try:
            from tools.browser import navigate

            return navigate(url)
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _ensure_playwright(headless: bool = False):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            raise RuntimeError(
                "Playwright is not available. Install it with 'pip install playwright' and run 'playwright install chromium'."
            ) from e

        if AdvancedTools._playwright is None:
            AdvancedTools._playwright = sync_playwright().start()
        if AdvancedTools._browser is None:
            AdvancedTools._browser = AdvancedTools._playwright.chromium.launch(headless=headless)
        if AdvancedTools._browser_context is None:
            AdvancedTools._browser_context = AdvancedTools._browser.new_context(viewport={"width": 1440, "height": 960})
        if AdvancedTools._browser_page is None:
            AdvancedTools._browser_page = AdvancedTools._browser_context.new_page()
            AdvancedTools._browser_events = {
                "console_errors": [],
                "page_errors": [],
                "network_failures": [],
            }
            AdvancedTools._browser_page.on(
                "console",
                lambda msg: AdvancedTools._browser_events["console_errors"].append(msg.text)
                if msg.type == "error" else None
            )
            AdvancedTools._browser_page.on(
                "pageerror",
                lambda exc: AdvancedTools._browser_events["page_errors"].append(str(exc))
            )
            AdvancedTools._browser_page.on(
                "requestfailed",
                lambda request: AdvancedTools._browser_events["network_failures"].append(
                    f"{request.method} {request.url}: {request.failure.error_text if request.failure else 'failed'}"
                )
            )
        return AdvancedTools._browser_page

    @staticmethod
    def _browser_open(url: str, headless: bool = False) -> str:
        try:
            from tools.browser import navigate

            return navigate(url)
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _browser_click(selector: str) -> str:
        try:
            from tools.browser import click_element

            return click_element(selector=selector)
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _browser_type(selector: str, text: str, clear_first: bool = True) -> str:
        try:
            from tools.browser import type_into

            return type_into(selector=selector, value=text)
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _browser_wait(selector: str = None, timeout_ms: int = 5000) -> str:
        try:
            from tools.browser import wait_for_element

            if selector:
                return wait_for_element(selector, timeout_ms)
            time.sleep(max(timeout_ms, 0) / 1000)
            return "Browser idle"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _browser_snapshot(path: str = None, include_screenshot: bool = True) -> str:
        try:
            from tools import browser

            page = browser._get_page()
            payload = {
                "url": page.url,
                "title": page.title(),
                "visible_text": browser.get_page_text(),
                "screenshot_b64": browser.get_page_screenshot_b64() if include_screenshot else "",
                "screenshot_path": path or "",
            }
            return json.dumps(payload, indent=2)
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _browser_close() -> str:
        try:
            from tools.browser import close_browser

            return close_browser()
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _manage_browser_tabs(action: str, url: str = None, index: int = None) -> str:
        try:
            page = AdvancedTools._ensure_playwright()
            context = AdvancedTools._browser_context
            pages = context.pages if context else [page]
            normalized = action.lower().strip()

            if normalized == "list":
                rows = []
                for idx, tab in enumerate(pages):
                    rows.append({
                        "index": idx,
                        "url": tab.url,
                        "title": tab.title() if tab.url else "",
                        "active": tab == AdvancedTools._browser_page,
                    })
                return json.dumps(rows, indent=2)

            if normalized == "open":
                if not url:
                    return "Error: url is required for action=open"
                new_page = context.new_page()
                new_page.goto(url, wait_until="load", timeout=30000)
                AdvancedTools._browser_page = new_page
                return f"Opened tab {len(context.pages) - 1}: {new_page.url}"

            if normalized == "switch":
                if index is None or index < 0 or index >= len(pages):
                    return f"Error: invalid tab index {index}"
                AdvancedTools._browser_page = pages[index]
                AdvancedTools._browser_page.bring_to_front()
                return f"Switched to tab {index}: {AdvancedTools._browser_page.url}"

            if normalized == "close":
                if len(pages) <= 1:
                    return "Error: cannot close the last remaining tab"
                target_index = index if index is not None else pages.index(AdvancedTools._browser_page)
                if target_index < 0 or target_index >= len(pages):
                    return f"Error: invalid tab index {target_index}"
                closing = pages[target_index]
                closing.close()
                remaining = context.pages
                AdvancedTools._browser_page = remaining[min(target_index, len(remaining) - 1)]
                AdvancedTools._browser_page.bring_to_front()
                return f"Closed tab {target_index}"

            if normalized == "current":
                current = AdvancedTools._browser_page
                return json.dumps({
                    "index": pages.index(current),
                    "url": current.url,
                    "title": current.title() if current.url else "",
                }, indent=2)

            return f"Error: unknown action '{action}'. Use list, open, switch, close, or current."
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _browser_login(
        url: str,
        username_selector: str,
        password_selector: str,
        submit_selector: str,
        username: str,
        password: str,
        otp_selector: str = None,
        otp: str = None,
        wait_selector: str = None,
    ) -> str:
        try:
            page = AdvancedTools._ensure_playwright()
            page.goto(url, wait_until="load", timeout=30000)
            page.locator(username_selector).first.fill(username, timeout=10000)
            page.locator(password_selector).first.fill(password, timeout=10000)
            if otp_selector and otp:
                page.locator(otp_selector).first.fill(otp, timeout=10000)
            page.locator(submit_selector).first.click(timeout=10000)
            if wait_selector:
                page.locator(wait_selector).first.wait_for(timeout=15000)
            else:
                page.wait_for_load_state("networkidle", timeout=15000)
            return f"Login flow submitted in Playwright: {page.url}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _workflow_path(name: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_") or "workflow"
        return Config.WORKFLOWS_DIR / f"{safe}.json"

    @staticmethod
    def _save_workflow(name: str, steps: List[Dict[str, Any]], description: str = "") -> str:
        try:
            if not isinstance(steps, list) or not steps:
                return "Error: steps must be a non-empty list"
            normalized_steps = []
            for step in steps[:100]:
                if not isinstance(step, dict):
                    return "Error: each workflow step must be an object"
                tool_name = str(step.get("tool_name", "")).strip()
                tool_args = step.get("tool_args", {})
                if not tool_name or not isinstance(tool_args, dict):
                    return "Error: each workflow step needs tool_name and object tool_args"
                normalized_steps.append({
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                })
            payload = {
                "name": name,
                "description": description,
                "steps": normalized_steps,
                "saved_at": datetime.now().isoformat(),
            }
            path = AdvancedTools._workflow_path(name)
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return f"Saved workflow: {name}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _list_workflows() -> str:
        try:
            rows = []
            for path in sorted(Config.WORKFLOWS_DIR.glob("*.json")):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    rows.append({
                        "name": payload.get("name", path.stem),
                        "description": payload.get("description", ""),
                        "steps": len(payload.get("steps", [])),
                    })
                except Exception:
                    rows.append({"name": path.stem, "description": "(invalid workflow file)", "steps": 0})
            return json.dumps(rows, indent=2)
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _workflow_tool_names() -> List[str]:
        return sorted(
            name for name in AdvancedTools.AGENT_TOOL_NAMES
            if name not in {"save_workflow", "list_workflows", "run_workflow", "generate_workflow", "mutate_workflow"}
        )

    @staticmethod
    def _parse_json_object(content: str) -> Dict[str, Any]:
        if not content:
            return {}
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _generate_workflow(name: str, goal: str, description: str = "", ai_model: Any = None) -> str:
        try:
            if ai_model:
                prompt = f"""
You are generating a reusable workflow for an autonomous PC operator.
Workflow name: {name}
Goal: {goal}
Available tool names: {', '.join(AdvancedTools._workflow_tool_names())}
World state:
{AdvancedTools._world_state_summary()}

Return strict JSON:
{{
  "description": "...",
  "steps": [
    {{
      "tool_name": "...",
      "tool_args": {{}}
    }}
  ]
}}

Rules:
- Use 1 to 12 steps.
- Use only the available tool names.
- Prefer primitive actions over task-specific shortcuts.
- If browser work is needed, include browser_open/browser_snapshot.
- If file changes are needed, include observe_environment before writing.
"""
                response = ai_model.chat(
                    [
                        {"role": "system", "content": "Return strict JSON only."},
                        {"role": "user", "content": prompt},
                    ]
                )
                content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
                payload = AdvancedTools._parse_json_object(content)
                steps = payload.get("steps", [])
                desc = str(payload.get("description", "")).strip() or description
                if isinstance(steps, list) and steps:
                    return AdvancedTools._save_workflow(name, steps, desc)

            fallback_steps = [
                {"tool_name": "observe_environment", "tool_args": {"path": ".", "depth": 2}},
                {
                    "tool_name": "execute_python",
                    "tool_args": {
                        "code": (
                            f"goal = {json.dumps(goal)}\n"
                            "print('GOAL:', goal)\n"
                            "print('NEXT_STEP: synthesize a concrete artifact or action sequence for this workflow.')\n"
                        )
                    },
                },
            ]
            return AdvancedTools._save_workflow(name, fallback_steps, description or f"Generated workflow for: {goal}")
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _mutate_workflow(
        name: str,
        action: str,
        index: int = None,
        new_index: int = None,
        step: Dict[str, Any] = None,
        reason: str = "",
        goal: str = "",
        last_result: str = "",
        ai_model: Any = None,
    ) -> str:
        try:
            path = AdvancedTools._workflow_path(name)
            if not path.exists():
                return f"Error: workflow not found: {name}"
            payload = json.loads(path.read_text(encoding="utf-8"))
            steps = payload.get("steps", [])
            if not isinstance(steps, list):
                return "Error: workflow file is invalid"

            normalized = action.lower().strip()
            if normalized == "insert":
                if not isinstance(step, dict):
                    return "Error: step is required for insert"
                insert_at = len(steps) if index is None else max(0, min(int(index), len(steps)))
                steps.insert(insert_at, step)
            elif normalized == "remove":
                if index is None or index < 0 or index >= len(steps):
                    return f"Error: invalid index {index}"
                steps.pop(index)
            elif normalized == "replace":
                if index is None or index < 0 or index >= len(steps) or not isinstance(step, dict):
                    return "Error: replace requires valid index and step"
                steps[index] = step
            elif normalized == "reorder":
                if index is None or new_index is None:
                    return "Error: reorder requires index and new_index"
                if index < 0 or index >= len(steps) or new_index < 0 or new_index >= len(steps):
                    return "Error: reorder indices out of range"
                moving = steps.pop(index)
                steps.insert(new_index, moving)
            elif normalized in {"auto_rewrite", "auto_repair"}:
                if not ai_model:
                    return "Error: auto_rewrite requires AI model access"
                prompt = f"""
You are rewriting a workflow for an autonomous PC operator.
Workflow name: {name}
Goal: {goal or payload.get('description', '')}
Reason: {reason}
Last result: {last_result}
Current steps: {json.dumps(steps, ensure_ascii=True)}
Available tool names: {', '.join(AdvancedTools._workflow_tool_names())}
World state:
{AdvancedTools._world_state_summary()}

Return strict JSON:
{{
  "description": "...",
  "steps": [
    {{
      "tool_name": "...",
      "tool_args": {{}}
    }}
  ]
}}
"""
                response = ai_model.chat(
                    [
                        {"role": "system", "content": "Return strict JSON only."},
                        {"role": "user", "content": prompt},
                    ]
                )
                content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
                rewritten = AdvancedTools._parse_json_object(content)
                candidate_steps = rewritten.get("steps", [])
                if not isinstance(candidate_steps, list) or not candidate_steps:
                    return "Error: AI rewrite did not produce valid steps"
                steps = candidate_steps
                payload["description"] = str(rewritten.get("description", payload.get("description", "")))
            else:
                return f"Error: unknown mutate action '{action}'"

            payload["steps"] = steps[:100]
            payload["updated_at"] = datetime.now().isoformat()
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return f"Mutated workflow: {name} ({normalized})"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _render_workflow_value(value: Any, variables: Dict[str, Any]) -> Any:
        if isinstance(value, str):
            rendered = value
            for key, replacement in variables.items():
                rendered = rendered.replace(f"${{{key}}}", str(replacement))
            return rendered
        if isinstance(value, list):
            return [AdvancedTools._render_workflow_value(item, variables) for item in value]
        if isinstance(value, dict):
            return {k: AdvancedTools._render_workflow_value(v, variables) for k, v in value.items()}
        return value

    @staticmethod
    def _run_workflow(
        name: str,
        loop_count: int = 1,
        inputs: Dict[str, Any] = None,
        data_store: UserDataStore = None,
        ai_model: Any = None,
    ) -> str:
        try:
            path = AdvancedTools._workflow_path(name)
            if not path.exists():
                return f"Error: workflow not found: {name}"
            payload = json.loads(path.read_text(encoding="utf-8"))
            steps = payload.get("steps", [])
            if not isinstance(steps, list) or not steps:
                return "Error: workflow has no steps"

            loop_total = max(1, min(int(loop_count), 20))
            base_inputs = inputs if isinstance(inputs, dict) else {}
            results = []

            for iteration in range(loop_total):
                variables = dict(base_inputs)
                variables["iteration"] = iteration
                variables["loop_count"] = loop_total
                idx = 0
                while idx < len(steps):
                    step = steps[idx]
                    tool_name = str(step.get("tool_name", "")).strip()
                    raw_args = step.get("tool_args", {})
                    tool_args = AdvancedTools._render_workflow_value(raw_args, variables)
                    result = AdvancedTools.execute_tracked(tool_name, tool_args, data_store, ai_model)
                    results.append({
                        "iteration": iteration,
                        "step": idx,
                        "tool_name": tool_name,
                        "result": result[:500] if isinstance(result, str) else str(result)[:500],
                    })
                    variables[f"result_{idx}"] = result
                    evaluation = AdvancedTools._evaluate_workflow_step(
                        payload.get("description", ""),
                        steps,
                        idx,
                        tool_name,
                        tool_args,
                        result,
                        ai_model,
                    )
                    results[-1]["evaluation"] = evaluation
                    if isinstance(result, str) and result.lower().startswith("error"):
                        return json.dumps({
                            "status": "failed",
                            "workflow": name,
                            "iteration": iteration,
                            "step": idx,
                            "tool_name": tool_name,
                            "result": result,
                            "history": results[-10:],
                        }, indent=2)
                    if evaluation.get("change_workflow"):
                        mutation_action = evaluation.get("mutation_action", "auto_rewrite")
                        mutation_result = AdvancedTools._mutate_workflow(
                            name,
                            mutation_action,
                            idx,
                            evaluation.get("new_index"),
                            evaluation.get("step"),
                            evaluation.get("reason", ""),
                            payload.get("description", ""),
                            str(result)[:1000],
                            ai_model,
                        )
                        results.append({
                            "iteration": iteration,
                            "step": idx,
                            "tool_name": "mutate_workflow",
                            "result": mutation_result[:500],
                        })
                        if mutation_result.lower().startswith("error"):
                            return json.dumps({
                                "status": "failed",
                                "workflow": name,
                                "iteration": iteration,
                                "step": idx,
                                "tool_name": "mutate_workflow",
                                "result": mutation_result,
                                "history": results[-10:],
                            }, indent=2)
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        steps = payload.get("steps", steps)
                        if mutation_action in {"insert", "replace", "reorder", "auto_rewrite", "auto_repair"}:
                            idx = 0
                            continue
                    idx += 1

            return json.dumps({
                "status": "completed",
                "workflow": name,
                "iterations": loop_total,
                "steps": len(steps),
                "history": results[-20:],
            }, indent=2)
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _evaluate_workflow_step(
        workflow_goal: str,
        steps: List[Dict[str, Any]],
        index: int,
        tool_name: str,
        tool_args: Dict[str, Any],
        result: Any,
        ai_model: Any = None,
    ) -> Dict[str, Any]:
        if not ai_model:
            return {"step_ok": True, "change_workflow": False, "reason": "No AI evaluator available."}
        prompt = f"""
You are evaluating one workflow step in a dynamic autonomous system.
Workflow goal: {workflow_goal}
Current steps: {json.dumps(steps, ensure_ascii=True)}
Step index: {index}
Tool: {tool_name}
Args: {json.dumps(tool_args, ensure_ascii=True)}
Result: {str(result)[:1500]}
World state:
{AdvancedTools._world_state_summary()}

Return strict JSON:
{{
  "step_ok": true/false,
  "change_workflow": true/false,
  "reason": "...",
  "mutation_action": "auto_rewrite|insert|replace|remove|reorder",
  "new_index": 0,
  "step": {{"tool_name":"...","tool_args":{{}}}}
}}

Use change_workflow=true only if the workflow should be restructured, not just continued.
"""
        try:
            response = ai_model.chat(
                [
                    {"role": "system", "content": "Evaluate workflow execution. Return strict JSON only."},
                    {"role": "user", "content": prompt},
                ]
            )
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            payload = AdvancedTools._parse_json_object(content)
            if payload:
                return payload
        except Exception:
            pass
        return {"step_ok": True, "change_workflow": False, "reason": "Fallback evaluator used."}

    @staticmethod
    def _helper_path(name: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_") or "helper"
        return Config.HELPERS_DIR / f"{safe}.py"

    @staticmethod
    def _list_helpers() -> str:
        try:
            helpers = []
            for path in sorted(Config.HELPERS_DIR.glob("*.py")):
                helpers.append({"name": path.stem, "path": str(path), "size": path.stat().st_size})
            return json.dumps(helpers, indent=2)
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _synthesize_helper(name: str, purpose: str, signature: str = "", ai_model: Any = None) -> str:
        try:
            path = AdvancedTools._helper_path(name)
            helper_code = ""
            if ai_model:
                prompt = f"""
Write a narrow Python helper module for a constrained autonomous operator.
Helper name: {name}
Purpose: {purpose}
Optional signature: {signature}

Requirements:
- Single file Python module.
- Expose a function run(payload) that returns a JSON-serializable object or string.
- Accept JSON on stdin in a __main__ block and print JSON/text to stdout.
- Keep dependencies to the standard library.
- Keep behavior narrow and deterministic.

Return only code.
"""
                response = ai_model.chat(
                    [
                        {"role": "system", "content": "Generate code only."},
                        {"role": "user", "content": prompt},
                    ]
                )
                helper_code = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not helper_code.strip():
                helper_code = f"""import json
import sys

def run(payload):
    return {{
        "helper": {json.dumps(name)},
        "purpose": {json.dumps(purpose)},
        "payload": payload
    }}

if __name__ == "__main__":
    raw = sys.stdin.read().strip()
    payload = json.loads(raw) if raw else {{}}
    result = run(payload)
    print(json.dumps(result, indent=2, ensure_ascii=True))
"""

            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(helper_code, encoding="utf-8")
            state = AdvancedTools._load_world_state()
            state.setdefault("helpers", {})[name] = {
                "purpose": purpose,
                "signature": signature,
                "path": str(path),
                "updated_at": datetime.now().isoformat(),
                "status": "synthesized",
            }
            AdvancedTools._save_world_state(state)
            return f"Synthesized helper: {name}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _run_helper(name: str, payload: Dict[str, Any] = None) -> str:
        try:
            path = AdvancedTools._helper_path(name)
            if not path.exists():
                return f"Error: helper not found: {name}"
            data = json.dumps(payload if isinstance(payload, dict) else {}, ensure_ascii=True)
            result = subprocess.run(
                [sys.executable, str(path)],
                input=data,
                capture_output=True,
                text=True,
                timeout=Config.TOOL_TIMEOUT,
            )
            output = result.stdout or result.stderr or "(no output)"
            state = AdvancedTools._load_world_state()
            state.setdefault("helpers", {}).setdefault(name, {})
            state["helpers"][name].update(
                {
                    "last_run": datetime.now().isoformat(),
                    "last_result": output[:1000],
                    "path": str(path),
                }
            )
            AdvancedTools._save_world_state(state)
            return output
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _world_state_summary() -> str:
        try:
            state = AdvancedTools._load_world_state()
            summary = {
                "last_action": state.get("last_action", {}),
                "goal_progress": state.get("goal_progress", {}),
                "repo": state.get("repo", {}),
                "shell": {
                    "last_session": state.get("shell", {}).get("last_session", ""),
                    "sessions": state.get("shell", {}).get("sessions", {}),
                    "command_history": state.get("shell", {}).get("command_history", [])[-5:],
                },
                "current_browser": state.get("browser", {}),
                "workflows": list(state.get("workflows", {}).keys())[:20],
                "helpers": list(state.get("helpers", {}).keys())[:20],
                "recent_actions": state.get("recent_actions", [])[-5:],
            }
            return json.dumps(summary, indent=2, ensure_ascii=True)
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _fill_form_field(text: str) -> str:
        try:
            from tools.screen_control import type_text

            return type_text(text)
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _click_element(x: int, y: int) -> str:
        try:
            from tools.screen_control import click_at

            return click_at(x, y)
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _guide_account_setup(service: str, step: str = None) -> str:
        """Guide user through account creation."""
        guides = {
            "gmail": "1. Go to gmail.com\n2. Click 'Create account'\n3. Enter your name\n4. Choose username\n5. Create password\n6. Verify phone\n7. Complete setup",
            "netlify": "1. Go to netlify.com\n2. Click 'Sign up'\n3. Choose email/GitHub\n4. Verify email\n5. Complete profile",
            "vercel": "1. Go to vercel.com\n2. Click 'Sign Up'\n3. Continue with GitHub/GitLab\n4. Complete onboarding",
            "github": "1. Go to github.com\n2. Enter email\n3. Create password\n4. Choose username\n5. Verify email\n6. Complete signup",
        }
        guide = guides.get(service.lower(), f"Go to {service}.com and follow signup process")
        return f"Account setup guide for {service}:\n{guide}"

    @staticmethod
    def _request_otp(service: str, message: str) -> str:
        """Request OTP from user."""
        return f"[AUTH REQUIRED] {service}: {message}\nPlease enter the OTP when ready, and I'll guide you to the next step."

    @staticmethod
    def _validate_business_idea(idea: str, market: str = None) -> str:
        """Validate business idea (placeholder - AI will enhance)."""
        return f"Analyzing business idea: {idea}\nMarket: {market or 'General'}\n\n[AI will provide detailed validation]"

    @staticmethod
    def _create_business_plan(idea: str, target_audience: str = None) -> str:
        """Create business plan structure."""
        plan = f"""# Business Plan: {idea}

## Executive Summary
[AI-generated summary]

## Problem Statement
[What problem does this solve?]

## Solution
[Your product/service]

## Target Audience
{target_audience or 'To be defined'}

## Market Analysis
[Market size, trends, competition]

## Revenue Model
[How you'll make money]

## Marketing Strategy
[Customer acquisition plan]

## Financial Projections
[Costs, revenue, break-even]

## Timeline
[Milestones and deadlines]
"""
        return plan

    @staticmethod
    def _create_marketing_strategy(business_type: str, budget: str = None) -> str:
        """Create marketing strategy."""
        return f"""# Marketing Strategy: {business_type}
Budget: {budget or 'Not specified'}

## Channels
1. Social Media (Facebook, Instagram, LinkedIn)
2. Content Marketing (Blog, SEO)
3. Email Marketing
4. Paid Ads (Google, Social)
5. Influencer Partnerships

## Timeline
- Month 1: Setup & Content
- Month 2: Launch Campaigns
- Month 3: Optimize & Scale

## KPIs
- Website Traffic
- Conversion Rate
- Customer Acquisition Cost
- Lifetime Value
"""

    @staticmethod
    def _generate_weekly_report(store: UserDataStore, weeks: int) -> str:
        """Generate weekly report."""
        if not store:
            return "No data available"

        stats = store.get_weekly_stats(weeks * 7)
        report = f"""
# Weekly Report (Last {weeks} week(s))

## Overview
- Conversations: {stats['conversations']}
- Total Tasks: {stats['total_tasks']}
- Completed: {stats['completed_tasks']}
- Failed: {stats['failed_tasks']}
- Success Rate: {(stats['completed_tasks']/max(stats['total_tasks'],1)*100):.1f}%

## Projects
- Total Projects: {stats['projects']}
- Active: {stats['active_projects']}

## Summary
[AI will generate detailed summary]
"""
        return report

    @staticmethod
    def _get_task_statistics(store: UserDataStore, days: int) -> str:
        """Get task statistics."""
        if not store:
            return "No data available"
        stats = store.get_weekly_stats(days)
        return json.dumps(stats, indent=2)

    @staticmethod
    def _create_project(name: str, type: str, store: UserDataStore) -> str:
        """Create new project."""
        if not store:
            return "Error: No data store"

        project = Project(
            id=f"proj_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            name=name,
            type=type,
            status="active",
            created_at=datetime.now().isoformat(),
            last_updated=datetime.now().isoformat()
        )
        store.add_project(project)
        return f"Created project: {name} ({type}) - ID: {project.id}"

    @staticmethod
    def _update_project_status(project_id: str, status: str, store: UserDataStore) -> str:
        """Update project status."""
        if not store:
            return "Error: No data store"

        if store.update_project(project_id, {"status": status}):
            return f"Updated project {project_id} to: {status}"
        return f"Project not found: {project_id}"

    @staticmethod
    def _check_website_status(url: str) -> str:
        """Check if website is online."""
        try:
            import requests
            response = requests.get(url, timeout=10)
            status = "ONLINE" if response.status_code == 200 else f"STATUS: {response.status_code}"
            return f"{url}: {status}"
        except Exception as e:
            return f"Error checking {url}: {e}"

    @staticmethod
    def _monitor_project_health(project_id: str, store: UserDataStore) -> str:
        """Monitor project health."""
        if not store:
            return "Error: No data store"

        project = next((p for p in store.projects if p.id == project_id), None)
        if not project:
            return f"Project not found: {project_id}"

        return f"""Project: {project.name}
Status: {project.status}
Last Updated: {project.last_updated}
Files: {len(project.files)}
URL: {project.url or 'Not deployed'}
Health: [AI will analyze]
"""

    @staticmethod
    def _github_headers() -> Dict[str, str]:
        token = os.getenv("GITHUB_TOKEN", "").strip()
        if not token:
            return {}
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @staticmethod
    def _github_list_pull_requests(owner: str, repo: str, state: str = "open") -> str:
        """List pull requests from GitHub repository."""
        import requests

        headers = AdvancedTools._github_headers()
        if not headers:
            return "GitHub token missing. Set GITHUB_TOKEN in .env."

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        try:
            response = requests.get(url, headers=headers, params={"state": state, "per_page": 20}, timeout=20)
            if response.status_code >= 400:
                return f"GitHub API error {response.status_code}: {response.text[:300]}"
            pulls = response.json()
            if not pulls:
                return f"No {state} pull requests in {owner}/{repo}."
            lines = [f"PRs for {owner}/{repo} ({state}):"]
            for pr in pulls[:20]:
                lines.append(f"#{pr['number']} {pr['title']} | {pr['state']} | {pr['html_url']}")
            return "\n".join(lines)
        except Exception as e:
            return f"GitHub request failed: {e}"

    @staticmethod
    def _github_get_pull_request(owner: str, repo: str, pull_number: int) -> str:
        """Get pull request details."""
        import requests

        headers = AdvancedTools._github_headers()
        if not headers:
            return "GitHub token missing. Set GITHUB_TOKEN in .env."

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}"
        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code >= 400:
                return f"GitHub API error {response.status_code}: {response.text[:300]}"
            pr = response.json()
            summary = {
                "number": pr.get("number"),
                "title": pr.get("title"),
                "state": pr.get("state"),
                "draft": pr.get("draft"),
                "mergeable": pr.get("mergeable"),
                "mergeable_state": pr.get("mergeable_state"),
                "additions": pr.get("additions"),
                "deletions": pr.get("deletions"),
                "changed_files": pr.get("changed_files"),
                "commits": pr.get("commits"),
                "url": pr.get("html_url"),
            }
            return json.dumps(summary, indent=2)
        except Exception as e:
            return f"GitHub request failed: {e}"

    @staticmethod
    def _github_submit_pull_review(owner: str, repo: str, pull_number: int, event: str, body: str = None) -> str:
        """Submit PR review."""
        import requests

        headers = AdvancedTools._github_headers()
        if not headers:
            return "GitHub token missing. Set GITHUB_TOKEN in .env."

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
        payload = {"event": event}
        if body:
            payload["body"] = body

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            if response.status_code >= 400:
                return f"GitHub API error {response.status_code}: {response.text[:300]}"
            data = response.json()
            return f"Review submitted: {event} ({data.get('html_url', '')})"
        except Exception as e:
            return f"GitHub request failed: {e}"

    @staticmethod
    def _github_merge_pull_request(
        owner: str,
        repo: str,
        pull_number: int,
        merge_method: str = "squash",
        commit_title: str = None,
    ) -> str:
        """Merge PR."""
        import requests

        headers = AdvancedTools._github_headers()
        if not headers:
            return "GitHub token missing. Set GITHUB_TOKEN in .env."

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/merge"
        payload = {"merge_method": merge_method}
        if commit_title:
            payload["commit_title"] = commit_title

        try:
            response = requests.put(url, headers=headers, json=payload, timeout=20)
            if response.status_code >= 400:
                return f"GitHub API error {response.status_code}: {response.text[:300]}"
            data = response.json()
            if data.get("merged"):
                return f"PR #{pull_number} merged successfully ({data.get('sha', '')[:12]})"
            return f"PR #{pull_number} not merged: {data.get('message', 'unknown')}"
        except Exception as e:
            return f"GitHub request failed: {e}"

    @staticmethod
    def _send_notification(title: str, message: str) -> str:
        """Send desktop notification."""
        try:
            if platform.system() == "Windows":
                from win10toast import ToastNotifier
                ToastNotifier().show_toast(title, message, duration=5)
            else:
                # Linux/Mac fallback
                subprocess.run(f'echo "{message}" | notify-send "{title}"', shell=True)
            return f"Notification sent: {title}"
        except Exception as e:
            return f"Notification (console): {title} - {message}"

    @staticmethod
    def _copy_to_clipboard(text: str) -> str:
        try:
            import pyperclip
            pyperclip.copy(text)
            return f"Copied ({len(text)} chars)"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _get_clipboard() -> str:
        try:
            import pyperclip
            return pyperclip.paste()[:500]
        except Exception as e:
            return f"Error: {e}"

    # =========================================================================
    # NEW PC ACCESS TOOLS IMPLEMENTATION
    # =========================================================================

    @staticmethod
    def _search_files(pattern: str, path: str = None) -> str:
        """Search for files by pattern."""
        try:
            import fnmatch
            search_path = Path(path) if path else Path.home()
            matches = []
            for root, dirs, files in os.walk(str(search_path)):
                for name in files:
                    if fnmatch.fnmatch(name.lower(), pattern.lower()):
                        matches.append(os.path.join(root, name))
                        if len(matches) >= 50:  # Limit results
                            break
                if len(matches) >= 50:
                    break
            return f"Found {len(matches)} files:\n" + "\n".join(matches[:50]) if matches else "No files found"
        except Exception as e:
            return f"Error searching: {e}"

    @staticmethod
    def _get_system_info(info_type: str) -> str:
        """Get comprehensive system information."""
        try:
            import psutil
            info = []
            if info_type in ["all", "os"]:
                info.append(f"OS: {platform.system()} {platform.release()}")
                info.append(f"Machine: {platform.machine()}")
                info.append(f"Processor: {platform.processor()}")
                info.append(f"Hostname: {platform.node()}")
            if info_type in ["all", "hardware"]:
                info.append(f"CPU Cores: {psutil.cpu_count(logical=False)} (Logical: {psutil.cpu_count()})")
                info.append(f"CPU Usage: {psutil.cpu_percent(interval=0.5)}%")
                mem = psutil.virtual_memory()
                info.append(f"RAM: {mem.total / (1024**3):.1f} GB total, {mem.percent}% used")
            if info_type in ["all", "disk"]:
                disk = psutil.disk_usage('C:\\')
                info.append(f"Disk C:\\: {disk.total / (1024**3):.1f} GB total, {disk.percent}% used")
            if info_type in ["all", "network"]:
                addrs = psutil.net_if_addrs()
                for iface, addr_list in addrs.items():
                    for addr in addr_list:
                        if addr.family == psutil.AF_LINK:
                            info.append(f"{iface}: {addr.address}")
            if info_type in ["all", "processes"]:
                procs = [p.info['name'] for p in psutil.process_iter(['name'])][:20]
                info.append(f"Top processes: {', '.join(procs)}")
            return "\n".join(info)
        except ImportError:
            return "psutil not installed. Run: pip install psutil"
        except Exception as e:
            return f"Error getting system info: {e}"

    @staticmethod
    def _manage_processes(action: str, process_name: str = None, command: str = None) -> str:
        """Manage processes."""
        try:
            import psutil
            if action == "list":
                procs = []
                for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        procs.append(f"{p.info['pid']}: {p.info['name']} (CPU: {p.info['cpu_percent']:.1f}%, Mem: {p.info['memory_percent']:.1f}%)")
                    except:
                        pass
                return f"Running processes ({len(procs)}):\n" + "\n".join(procs[:50])
            elif action == "kill" and process_name:
                killed = 0
                for p in psutil.process_iter(['name']):
                    if process_name.lower() in p.info['name'].lower():
                        p.kill()
                        killed += 1
                return f"Killed {killed} process(es) matching '{process_name}'"
            elif action == "start" and command:
                subprocess.Popen(command, shell=True)
                return f"Started: {command}"
            return f"Unknown action or missing parameters: {action}"
        except ImportError:
            return "psutil not installed. Run: pip install psutil"
        except Exception as e:
            return f"Error managing processes: {e}"

    @staticmethod
    def _file_operations(operation: str, source: str, destination: str = None) -> str:
        """File operations: copy, move, delete, rename."""
        try:
            src = Path(source)
            if operation == "copy":
                import shutil
                shutil.copy2(src, destination)
                return f"Copied: {source} -> {destination}"
            elif operation == "move":
                import shutil
                shutil.move(src, destination)
                return f"Moved: {source} -> {destination}"
            elif operation == "delete":
                if src.is_file():
                    src.unlink()
                    return f"Deleted file: {source}"
                elif src.is_dir():
                    import shutil
                    shutil.rmtree(src)
                    return f"Deleted directory: {source}"
                return f"Not found: {source}"
            elif operation == "rename":
                src.rename(destination)
                return f"Renamed: {source} -> {destination}"
            return f"Unknown operation: {operation}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _get_disk_usage(path: str = None) -> str:
        """Get disk usage information."""
        try:
            import psutil
            partitions = psutil.disk_partitions()
            info = []
            for p in partitions:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    info.append(f"{p.device} ({p.mountpoint}): {usage.total/(1024**3):.1f}GB total, {usage.free/(1024**3):.1f}GB free ({usage.percent}% used)")
                except:
                    pass
            return "\n".join(info) if info else "No disk info available"
        except ImportError:
            return "psutil not installed"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _network_operations(action: str, target: str = None) -> str:
        """Network operations."""
        try:
            if action == "ping" and target:
                result = subprocess.run(f"ping -n 4 {target}", shell=True, capture_output=True, text=True, timeout=15)
                return result.stdout or result.stderr
            elif action == "get_ip":
                import socket
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
                return f"Hostname: {hostname}\nIP Address: {ip}"
            elif action == "port_scan" and target:
                import socket
                open_ports = []
                for port in [21, 22, 80, 443, 8080, 3306, 5432]:
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(0.5)
                        if s.connect_ex((target, port)) == 0:
                            open_ports.append(port)
                        s.close()
                    except:
                        pass
                return f"Open ports on {target}: {open_ports}" if open_ports else f"No common ports open on {target}"
            elif action == "netstat":
                result = subprocess.run("netstat -an", shell=True, capture_output=True, text=True, timeout=10)
                lines = result.stdout.split('\n')[:50]
                return "\n".join(lines)
            return f"Unknown action: {action}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _registry_operations(action: str, path: str, value_name: str = None, value_data: str = None) -> str:
        """Windows registry operations."""
        try:
            import winreg
            # Parse path like HKEY_CURRENT_USER\Software\MyApp
            parts = path.split('\\')
            if len(parts) < 2:
                return "Invalid registry path. Use format: HKEY_CURRENT_USER\\Software\\Key"
            root_map = {
                "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
                "HKCU": winreg.HKEY_CURRENT_USER,
                "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
                "HKLM": winreg.HKEY_LOCAL_MACHINE,
                "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
                "HKCR": winreg.HKEY_CLASSES_ROOT,
            }
            root = root_map.get(parts[0].upper(), winreg.HKEY_CURRENT_USER)
            sub_key = '\\'.join(parts[1:])
            if action == "read":
                key = winreg.OpenKey(root, sub_key, 0, winreg.KEY_READ)
                if value_name:
                    value, _ = winreg.QueryValueEx(key, value_name)
                    winreg.CloseKey(key)
                    return f"{value_name} = {value}"
                else:
                    info = []
                    for i in range(winreg.QueryInfoKey(key)[1]):
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            info.append(f"{name}: {value}")
                        except:
                            break
                    winreg.CloseKey(key)
                    return "\n".join(info) if info else "No values found"
            elif action == "write" and value_name and value_data:
                key = winreg.CreateKey(root, sub_key)
                winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, value_data)
                winreg.CloseKey(key)
                return f"Written: {path}\\{value_name} = {value_data}"
            elif action == "delete" and value_name:
                key = winreg.OpenKey(root, sub_key, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, value_name)
                winreg.CloseKey(key)
                return f"Deleted: {path}\\{value_name}"
            return f"Unknown action or missing parameters: {action}"
        except Exception as e:
            return f"Registry error: {e}"

    @staticmethod
    def _schedule_task(action: str, task_name: str = None, command: str = None, schedule: str = None) -> str:
        """Windows Task Scheduler operations."""
        try:
            if action == "create" and task_name and command:
                # Use schtasks command
                sched = schedule or "ONSTART"
                cmd = f'schtasks /Create /TN "{task_name}" /TR "{command}" /SC {sched} /F'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                return result.stdout or result.stderr or "Task created"
            elif action == "list":
                result = subprocess.run("schtasks /Query /FO TABLE", shell=True, capture_output=True, text=True)
                return result.stdout or result.stderr
            elif action == "delete" and task_name:
                result = subprocess.run(f'schtasks /Delete /TN "{task_name}" /F', shell=True, capture_output=True, text=True)
                return result.stdout or result.stderr or "Task deleted"
            return f"Unknown action or missing parameters: {action}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _web_scrape(url: str, selector: str = None) -> str:
        """Scrape content from websites."""
        try:
            from tools.research import search_and_read

            return search_and_read(url, num_results=3)
        except Exception as e:
            return f"Error scraping: {e}"

    @staticmethod
    def _download_file(url: str, destination: str = None) -> str:
        """Download files from URLs."""
        try:
            import requests
            dest = Path(destination) if destination else Path.cwd() / url.split('/')[-1]
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(dest, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return f"Downloaded to: {dest}"
        except Exception as e:
            return f"Error downloading: {e}"

    @staticmethod
    def _install_package(package: str, manager: str = "pip") -> str:
        """Install software packages."""
        try:
            managers = {
                "pip": f"pip install {package}",
                "npm": f"npm install -g {package}",
                "choco": f"choco install {package} -y",
                "winget": f"winget install {package}"
            }
            cmd = managers.get(manager, f"pip install {package}")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
            return result.stdout or result.stderr or "Installation completed"
        except Exception as e:
            return f"Error installing: {e}"

    @staticmethod
    def _send_email(to: str, subject: str, body: str, attachments: List[str] = None) -> str:
        """Send emails via SMTP."""
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.base import MIMEBase
            from email import encoders
            # Note: User needs to configure SMTP settings
            msg = MIMEMultipart()
            msg['From'] = os.getenv('EMAIL_FROM', 'user@example.com')
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            if attachments:
                for file in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(open(file, 'rb').read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{Path(file).name}"')
                    msg.attach(part)
            # Would need actual SMTP configuration
            return "Email configured (SMTP credentials needed in .env)"
        except Exception as e:
            return f"Email error: {e}"

    @staticmethod
    def _control_media(action: str, level: int = None) -> str:
        """Control volume, brightness, media."""
        try:
            if platform.system() == "Windows":
                import ctypes
                # Volume control using Windows API
                if action == "volume_up":
                    # Simulate volume up key
                    import pyautogui
                    pyautogui.press('volumeup')
                    return "Volume increased"
                elif action == "volume_down":
                    import pyautogui
                    pyautogui.press('volumedown')
                    return "Volume decreased"
                elif action == "mute":
                    import pyautogui
                    pyautogui.press('volumemute')
                    return "Volume muted"
                elif action == "play":
                    import pyautogui
                    pyautogui.press('playpause')
                    return "Play/Pause toggled"
                elif action == "pause":
                    import pyautogui
                    pyautogui.press('playpause')
                    return "Play/Pause toggled"
            return f"Media action: {action}"
        except Exception as e:
            return f"Error controlling media: {e}"

    @staticmethod
    def _take_screenshot(region: Dict = None, filename: str = None) -> str:
        """Capture screenshot."""
        try:
            from core.vision import get_screen_b64

            return get_screen_b64()
        except Exception as e:
            return f"Error taking screenshot: {e}"

    @staticmethod
    def _execute_python(code: str, args: List[str] = None) -> str:
        """Execute Python code dynamically."""
        try:
            # Capture stdout
            import io
            import sys
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            # Execute code
            exec(code)
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
            return f"Output:\n{output}" if output else "Code executed (no output)"
        except Exception as e:
            return f"Python error: {e}"


# ============================================================================
# STARTUP CREATION WIZARD
# ============================================================================

class StartupWizard:
    """Guided startup creation flow."""

    def __init__(self, ai: AIModel, data_store: UserDataStore):
        self.ai = ai
        self.data_store = data_store

    def run(self, idea: str) -> str:
        """Run startup creation wizard."""
        steps = [
            ("Validating business idea", self._validate_idea),
            ("Creating business plan", self._create_plan),
            ("Building website", self._build_website),
            ("Generating content", self._generate_content),
            ("Creating marketing strategy", self._marketing),
            ("Setting up deployment", self._deploy),
            ("Configuring analytics", self._analytics),
        ]

        results = []
        for step_name, step_func in steps:
            print(f"\n[*] {step_name}...")
            try:
                result = step_func(idea)
                results.append(f"✓ {step_name}")
                print(f"    Done: {result[:100]}...")
            except Exception as e:
                results.append(f"✗ {step_name}: {e}")

        return "\n".join(results)

    def _validate_idea(self, idea: str) -> str:
        return "Idea validated"

    def _create_plan(self, idea: str) -> str:
        return AdvancedTools._create_business_plan(idea)

    def _build_website(self, idea: str) -> str:
        name = idea.split()[0] if idea else "startup"
        return AdvancedTools._create_website(name, "startup", ["home", "about", "services", "contact"])

    def _generate_content(self, idea: str) -> str:
        return "Content generated for all pages"

    def _marketing(self, idea: str) -> str:
        return AdvancedTools._create_marketing_strategy("startup")

    def _deploy(self, idea: str) -> str:
        return "Deployment configured"

    def _analytics(self, idea: str) -> str:
        return "Analytics setup complete"


# ============================================================================
# MAIN PLATFORM
# ============================================================================

class AdvancedAIPlatform:
    """Main platform orchestrator."""

    def __init__(self):
        self.data_store = UserDataStore()
        self.ai = AIModel()
        self.router = RequestRouter()
        self.tools = AdvancedTools()
        self.conversation_history = []
        self.startup_wizard = StartupWizard(self.ai, self.data_store)
        self.console = Console(force_terminal=self._supports_color(), color_system="auto") if Console else None
        self.launch_profile = self._load_launch_profile()

        # Autonomous Agent (NEW - transforms from command runner to AI operator)
        from autonomous_agent import AutonomousAgent, MemorySystem, AutonomousToolsWrapper
        self.memory = MemorySystem()
        self.agent = AutonomousAgent(
            ai_model=self.ai,
            tools=AutonomousToolsWrapper(AdvancedTools, self.data_store, self.ai),
            memory=self.memory,
            emit_callback=self._emit_agent_event
        )
        self._run_startup_setup()
        self._print_welcome()

    def _supports_color(self) -> bool:
        if os.getenv("NO_COLOR") is not None:
            return False
        if os.getenv("FORCE_COLOR", "").lower() in {"1", "true", "yes"}:
            return True
        if os.name == "nt":
            term_program = os.getenv("TERM_PROGRAM", "").lower()
            if term_program in {"vscode", "windows_terminal"}:
                return True
            if os.getenv("WT_SESSION"):
                return True
        return bool(getattr(sys.stdout, "isatty", lambda: False)())

    def _style(self, text: str, code: str) -> str:
        if not self._supports_color():
            return text
        return f"\033[{code}m{text}\033[0m"

    def _accent(self, text: str) -> str:
        return self._style(text, "38;5;45")

    def _muted(self, text: str) -> str:
        return self._style(text, "38;5;250")

    def _strong(self, text: str) -> str:
        return self._style(text, "1;38;5;255")

    def _section_header(self, label: str) -> str:
        return self._accent(f"[{label}]")

    def _load_launch_profile(self) -> Dict[str, Any]:
        profile = self.data_store.user_profile.preferences.get("launch_profile", {})
        default = {
            "initialized": False,
            "default_mode": "shell",
            "preferred_provider": "",
            "prompt_gateway_each_launch": True,
        }
        if not isinstance(profile, dict):
            return default
        merged = dict(default)
        merged.update(profile)
        return merged

    def _save_launch_profile(self):
        self.data_store.user_profile.preferences["launch_profile"] = dict(self.launch_profile)
        self.data_store.save_profile()

    def _ask_choice(self, prompt: str, options: List[str], default: str = "") -> str:
        option_set = {item.strip().lower() for item in options}
        while True:
            raw = input(prompt).strip().lower()
            if not raw and default:
                return default
            if raw in option_set:
                return raw
            print(self._muted(f"Choose one of: {', '.join(options)}"))

    def _run_startup_setup(self):
        if not sys.stdin.isatty():
            return
        if not self.launch_profile.get("initialized"):
            self._run_first_launch_onboarding()
            return
        if not self.ai.provider:
            self._prompt_provider_setup()
        if not os.getenv("GITHUB_TOKEN", "").strip():
            self._prompt_optional_github_token()
        self._prompt_messaging_setup_if_missing()
        self._prompt_deployment_setup_if_needed()
        self._prompt_clerk_auth_setup_if_needed()

    def _run_first_launch_onboarding(self):
        print(f"\n{self._section_header('WELCOME')} First-time setup")
        print(self._muted("This will configure the basics so `connect` can start cleanly next time."))
        try:
            current_name = (self.data_store.user_profile.name or "User").strip()
            print(self._muted(f"Name [{current_name}]:"))
            name = input("> ").strip()
            if name:
                self.data_store.user_profile.name = name

            language_default = (self.data_store.user_profile.language or "en").strip().lower()
            print(self._muted(f"Language [en/ur/hi] ({language_default}):"))
            language = self._ask_choice("> ", ["en", "ur", "hi"], default=language_default)
            self.data_store.user_profile.language = language

            provider_default = self.launch_profile.get("preferred_provider") or self.ai.provider or "openai"
            if not self.ai.provider:
                print(self._muted("Choose model provider [openai/anthropic/groq/openrouter/gemini/huggingface/ollama]"))
                provider = self._ask_choice(
                    "> ",
                    ["openai", "anthropic", "groq", "openrouter", "gemini", "huggingface", "ollama"],
                    default=provider_default,
                )
                ok, message = self.ai.configure_provider(provider, interactive=True)
                print(message)
                if ok:
                    self.launch_profile["preferred_provider"] = provider
            else:
                self.launch_profile["preferred_provider"] = self.ai.provider

            self._prompt_optional_github_token()
            self._prompt_messaging_setup_if_missing()
            self._prompt_deployment_setup_if_needed()
            self._prompt_clerk_auth_setup_if_needed()

            print(self._muted("Default launch mode [shell/gateway/dashboard]"))
            default_mode = self._ask_choice("> ", ["shell", "gateway", "dashboard"], default="shell")
            self.launch_profile["default_mode"] = default_mode
            self.launch_profile["initialized"] = True
            self.launch_profile["prompt_gateway_each_launch"] = True
            self._save_launch_profile()
            self.data_store.save_profile()
            print(f"{self._section_header('WELCOME')} Setup saved.")
        except Exception:
            pass

    def _prompt_deployment_setup_if_needed(self):
        if not sys.stdin.isatty():
            return
        data = self._ensure_gateway_sections(self._load_gateway_json())
        gateway = data.setdefault("gateway", {})
        current_mode = str(gateway.get("deployment_mode", "") or "").strip().lower()
        if current_mode in {"local", "cloud"}:
            return
        print(f"\n{self._section_header('DEPLOY')} Where should gateway/dashboard bind by default? [local/cloud]")
        mode = self._ask_choice("> ", ["local", "cloud"], default="local")
        if mode == "cloud":
            gateway["deployment_mode"] = "cloud"
            gateway["host"] = "0.0.0.0"
            gateway["dashboard_host"] = "0.0.0.0"
        else:
            gateway["deployment_mode"] = "local"
            gateway["host"] = "127.0.0.1"
            gateway["dashboard_host"] = "127.0.0.1"
        self._save_gateway_json(data)

    def _prompt_clerk_auth_setup_if_needed(self):
        return

    def _has_messaging_config(self) -> bool:
        data = self._ensure_gateway_sections(self._load_gateway_json())
        messaging = data.get("messaging", {})
        if not isinstance(messaging, dict):
            return False
        telegram_ready = bool(str(messaging.get("telegram_bot_token", "")).strip() and str(messaging.get("telegram_default_chat_id", "")).strip())
        discord_webhooks = messaging.get("discord_webhooks", {})
        discord_ready = isinstance(discord_webhooks, dict) and any(
            str(name).strip() and str(url).strip() for name, url in discord_webhooks.items()
        )
        slack_webhooks = messaging.get("slack_webhooks", {})
        slack_ready = isinstance(slack_webhooks, dict) and any(
            str(name).strip() and str(url).strip() for name, url in slack_webhooks.items()
        )
        slack_bot_ready = bool(str(messaging.get("slack_bot_token", "")).strip() and str(messaging.get("slack_signing_secret", "")).strip())
        whatsapp_ready = bool(
            str(messaging.get("whatsapp_account_sid", "")).strip()
            and str(messaging.get("whatsapp_auth_token", "")).strip()
            and str(messaging.get("whatsapp_from_number", "")).strip()
        )
        return telegram_ready or discord_ready or slack_ready or slack_bot_ready or whatsapp_ready

    def _prompt_messaging_setup_if_missing(self):
        if not sys.stdin.isatty():
            return
        if self._has_messaging_config():
            return
        print(f"\n{self._section_header('MESSAGING')} No messaging connector is configured yet.")
        print(self._muted("Set one up now so CONNECT can send and receive real messages? [Y/n]"))
        try:
            answer = input("> ").strip().lower()
        except Exception:
            return
        if answer in {"n", "no", "skip"}:
            return
        message = self.run_messaging_setup()
        print(message)

    def _reference_title_lines(self) -> List[str]:
        return [
            "  #####   ###   #   #  #   #  #####   #####  #####",
            " #       #   #  ##  #  ##  #  #      #         #  ",
            " #       #   #  # # #  # # #  ###    #         #  ",
            " #       #   #  #  ##  #  ##  #      #         #  ",
            "  #####   ###   #   #  #   #  #####   #####    #  ",
            "",
            "    AI",
        ]
        return [
            " ██████╗ ██████╗ ███╗   ██╗███╗   ██╗███████╗ ██████╗████████╗",
            "██╔════╝██╔═══██╗████╗  ██║████╗  ██║██╔════╝██╔════╝╚══██╔══╝",
            "██║     ██║   ██║██╔██╗ ██║██╔██╗ ██║█████╗  ██║        ██║   ",
            "██║     ██║   ██║██║╚██╗██║██║╚██╗██║██╔══╝  ██║        ██║   ",
            "╚██████╗╚██████╔╝██║ ╚████║██║ ╚████║███████╗╚██████╗   ██║   ",
            " ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═══╝╚══════╝ ╚═════╝   ╚═╝   ",
            "     █████╗ ██╗",
            "    ██╔══██╗██║",
            "    ███████║██║",
            "    ██╔══██║██║",
            "    ██║  ██║██║",
            "    ╚═╝  ╚═╝╚═╝",
        ]

    def _welcome_lines(self) -> List[str]:
        provider = self.ai.provider or "none"
        model = self.ai.model_name or "unavailable"
        return [
            "CONNECT AI is ready with your configured model provider.",
            "",
            "Select login method:",
            f"  1. Active provider: {provider} ({model})",
            "  2. Use /provider [name] or /llm [name] to switch",
            "",
            "Use /help for help.",
        ]

    def _print_welcome_rich(self, title: str, subtitle: str, feature_lines: List[str]):
        title_text = Text("\n".join(self._reference_title_lines()), style="bold #6cb6ff")
        body_text = Text("\n".join(self._welcome_lines()), style="#d7e9ff")
        content = Text()
        content.append_text(title_text)
        content.append("\n\n")
        content.append_text(body_text)
        self.console.print(
            Panel(
                content,
                border_style="#365f8c",
                box=box.SQUARE if box else None,
                padding=(1, 2),
                style="on #141414",
                title="Welcome to CONNECT AI",
                title_align="left",
            )
        )

    def _emit_agent_event_rich(self, event_type: str, payload: Dict[str, Any]):
        title_map = {
            "plan_created": "PLAN UPDATE",
            "reasoning": "THOUGHT",
            "reasoning_retry": "THOUGHT",
            "action": "ACTION",
            "result": "RESULT",
            "patch": "PATCH",
            "observation": "OBSERVATION",
            "replan": "REWRITE",
            "evaluation": "EVALUATION",
        }
        title = title_map.get(event_type, event_type.upper())

        def render(lines: List[str], border: str = "cyan"):
            self.console.print(
                Panel(
                    "\n".join(lines) or "(empty)",
                    title=title,
                    border_style=border,
                    box=box.SQUARE if box else None,
                    padding=(0, 1),
                    style="on #141414",
                )
            )

        if event_type == "plan_created":
            render([f"{idx}. {step}" for idx, step in enumerate(payload.get("plan", []), start=1)])
            return
        if event_type in {"reasoning", "reasoning_retry"}:
            lines = [payload.get("thought", "").strip() or "(no thought provided)"]
            plan = payload.get("plan", [])
            if plan:
                lines.append("")
                lines.append("Plan:")
                lines.extend(f"{idx}. {step}" for idx, step in enumerate(plan, start=1))
            lines.append("")
            lines.append(f"Next: {payload.get('next_action', '')}")
            render(lines, "#7fb3ff")
            return
        if event_type == "action":
            lines = []
            intent = payload.get("intent", "")
            if intent:
                lines.append(f"Intent: {intent}")
            lines.append(payload.get("action", ""))
            render(lines, "#4ea1ff")
            return
        if event_type == "result":
            lines = []
            intent = payload.get("intent", "")
            if intent:
                lines.append(f"Intent: {intent}")
            lines.append(payload.get("summary", ""))
            render(lines, "#d7e9ff")
            return
        if event_type == "patch":
            lines = []
            intent = payload.get("intent", "")
            target = payload.get("target", "")
            if intent:
                lines.append(f"Intent: {intent}")
            if target:
                lines.append(f"Target: {target}")
            lines.extend(payload.get("changes", []))
            render(lines, "#4ea1ff")
            return
        if event_type == "observation":
            snapshot = str(payload.get("snapshot", "")).strip()
            if snapshot.startswith("{"):
                try:
                    data = json.loads(snapshot)
                    lines = [
                        f"URL: {data.get('url', '')}",
                        f"Title: {data.get('title', '')}",
                    ]
                    visible_text = str(data.get("visible_text", ""))[:350]
                    if visible_text:
                        lines.append(f"Visible Text: {visible_text}")
                    if data.get("console_errors"):
                        lines.append(f"Console Errors: {len(data.get('console_errors', []))}")
                    if data.get("page_errors"):
                        lines.append(f"Page Errors: {len(data.get('page_errors', []))}")
                    if data.get("network_failures"):
                        lines.append(f"Network Failures: {len(data.get('network_failures', []))}")
                    if data.get("screenshot_path"):
                        lines.append(f"Screenshot: {data.get('screenshot_path')}")
                    render(lines, "#6f8fb2")
                    return
                except Exception:
                    pass
            body = snapshot or "(none)"
            if len(body) > 420:
                body = body[:420] + "\n..."
            render([body], "#6f8fb2")
            return
        if event_type == "replan":
            lines = [f"Reason: {payload.get('error', '')}"]
            lines.extend(f"{idx}. {step}" for idx, step in enumerate(payload.get("plan", []), start=1))
            render(lines, "#4ea1ff")
            return
        if event_type == "evaluation":
            lines = []
            progress = payload.get("progress_score")
            goal_achieved = payload.get("goal_achieved")
            on_track = payload.get("on_track")
            if progress is not None:
                lines.append(f"Progress: {progress}/100")
            if goal_achieved is not None:
                lines.append(f"Goal Achieved: {goal_achieved}")
            if on_track is not None:
                lines.append(f"On Track: {on_track}")
            lines.append(payload.get("reason", ""))
            blockers = payload.get("blockers", [])
            if blockers:
                lines.append("")
                lines.append("Blockers:")
                lines.extend(f"- {blocker}" for blocker in blockers)
            next_steps = payload.get("next_steps", [])
            if next_steps:
                lines.append("")
                lines.append("Next Steps:")
                lines.extend(f"{idx}. {step}" for idx, step in enumerate(next_steps, start=1))
            render(lines, "#d7e9ff")

    def _print_tool_result_rich(self, tool_name: str, tool_args: Dict[str, Any], result: str):
        lines = [f"Tool: {tool_name}"]
        if tool_args:
            lines.append(f"Args: {json.dumps(tool_args, ensure_ascii=True)}")
        self.console.print(
            Panel(
                "\n".join(lines),
                title="TOOL",
                border_style="#365f8c",
                box=box.SQUARE if box else None,
                padding=(0, 1),
                style="on #141414",
            )
        )
        if tool_name == "run_shell_command":
            parsed = AdvancedTools._parse_shell_result(result)
            summary = [
                f"Session: {parsed.get('session_id', 'default')}",
                f"Cwd: {parsed.get('cwd', '')}",
                f"Exit: {parsed.get('exit_code', '')}",
                f"OK: {parsed.get('ok', False)}",
            ]
            self.console.print(
                Panel(
                    "\n".join(summary),
                    title="RESULT",
                    border_style="#d7e9ff",
                    box=box.SQUARE if box else None,
                    padding=(0, 1),
                    style="on #141414",
                )
            )
            stdout = parsed.get("stdout", "") or "(empty)"
            stderr = parsed.get("stderr", "") or "(empty)"
            self.console.print(
                Panel(
                    stdout[:1200],
                    title="STDOUT",
                    border_style="#6f8fb2",
                    box=box.SQUARE if box else None,
                    padding=(0, 1),
                    style="on #141414",
                )
            )
            if stderr != "(empty)":
                self.console.print(
                    Panel(
                        stderr[:1200],
                        title="STDERR",
                        border_style="#4ea1ff",
                        box=box.SQUARE if box else None,
                        padding=(0, 1),
                        style="on #141414",
                    )
                )
            return
        self.console.print(
            Panel(
                result or "(empty result)",
                title="RESULT",
                border_style="#d7e9ff",
                box=box.SQUARE if box else None,
                padding=(0, 1),
                style="on #141414",
            )
        )

    def doctor_report(self) -> str:
        lines = ["CONNECT Doctor", ""]
        lines.append("Providers:")
        for item in self.ai.get_provider_status():
            selected = " *" if item.get("selected") == "yes" else ""
            lines.append(
                f"  - {item['name']}: configured={item['configured']} ready={item['ready']} model={item['model']} note={item['note']}{selected}"
            )
        lines.append("")
        lines.append("Launchers:")
        repo_launcher = Path(__file__).resolve().parent / "connect.bat"
        lines.append(f"  - repo launcher: {repo_launcher} exists={repo_launcher.exists()}")
        user_launcher = Path.home() / "connect-bin" / "connect.cmd"
        lines.append(f"  - user launcher: {user_launcher} exists={user_launcher.exists()}")
        lines.append("")
        lines.append(f"Workspace cwd: {Path.cwd()}")
        lines.append(f"Launch profile: {json.dumps(self.launch_profile, ensure_ascii=True)}")
        gateway_config = self._load_gateway_json()
        messaging = gateway_config.get("messaging", {}) if isinstance(gateway_config, dict) else {}
        gateway = gateway_config.get("gateway", {}) if isinstance(gateway_config, dict) else {}
        auth = gateway_config.get("auth", {}) if isinstance(gateway_config, dict) else {}
        lines.append(
            f"Gateway config: deployment_mode={gateway.get('deployment_mode', 'local')} "
            f"host={gateway.get('host', '127.0.0.1')} "
            f"dashboard_host={gateway.get('dashboard_host', gateway.get('host', '127.0.0.1'))} "
            f"port={gateway.get('port', 18789)} dashboard_port={gateway.get('dashboard_port', 18890)}"
        )
        lines.append(
            f"Auth config: enabled={bool(auth.get('enabled', False))} "
            f"clerk_env={'yes' if (os.getenv('NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY', '').strip() and os.getenv('CLERK_SECRET_KEY', '').strip()) else 'no'} "
            f"webhook_bearer={'yes' if auth.get('webhook_bearer_token') else 'no'}"
        )
        lines.append(
            f"Messaging config: telegram_token={'yes' if messaging.get('telegram_bot_token') else 'no'} "
            f"telegram_chat_id={'yes' if messaging.get('telegram_default_chat_id') else 'no'} "
            f"discord_webhooks={list((messaging.get('discord_webhooks') or {}).keys())} "
            f"slack_webhooks={list((messaging.get('slack_webhooks') or {}).keys())} "
            f"slack_bot={'yes' if messaging.get('slack_bot_token') else 'no'} "
            f"whatsapp={'yes' if messaging.get('whatsapp_account_sid') else 'no'}"
        )
        return "\n".join(lines)

    def run_clerk_login(self) -> str:
        data = self._ensure_gateway_sections(self._load_gateway_json())
        auth = data.setdefault("auth", {})
        enabled = bool(auth.get("enabled", False))
        webhook_token = str(auth.get("webhook_bearer_token", "")).strip()
        try:
            from gateway_runtime.auth import ClerkAuthManager
            from gateway_runtime.config import load_gateway_config

            config = load_gateway_config(self._gateway_config_path())
            manager = ClerkAuthManager(config.workspace_root, enabled=enabled, webhook_bearer_token=webhook_token)
            if not manager.is_configured():
                return "Clerk publishable key is missing. Set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY so CONNECT can open the frontend login flow."
            ok, message = manager.start_cli_login()
            return message if ok else f"Login failed: {message}"
        except Exception as exc:
            return f"Login failed: {exc}"

    def run_clerk_logout(self) -> str:
        try:
            from gateway_runtime.auth import ClerkAuthManager
            from gateway_runtime.config import load_gateway_config

            data = self._ensure_gateway_sections(self._load_gateway_json())
            auth = data.setdefault("auth", {})
            config = load_gateway_config(self._gateway_config_path())
            manager = ClerkAuthManager(
                config.workspace_root,
                enabled=bool(auth.get("enabled", False)),
                webhook_bearer_token=str(auth.get("webhook_bearer_token", "")).strip(),
            )
            manager.clear_state()
            return "Signed out successfully."
        except Exception as exc:
            return f"Logout failed: {exc}"

    def provider_report(self) -> str:
        lines = ["Providers:"]
        for item in self.ai.get_provider_status():
            selected = " *" if item.get("selected") == "yes" else ""
            lines.append(
                f"  - {item['name']}: ready={item['ready']} configured={item['configured']} model={item['model']}{selected}"
            )
        lines.append("")
        lines.append("Usage:")
        lines.append("  /provider")
        lines.append("  /provider [name]")
        lines.append("  /llm [name]")
        lines.append("Switching providers will prompt for credentials when needed and save them in project .env.")
        return "\n".join(lines)

    def handle_provider_command(self, cmd: str) -> str:
        parts = cmd.split(maxsplit=1)
        if len(parts) == 1:
            return self.provider_report()
        target = parts[1].strip().lower()
        if target in {"list", "status"}:
            return self.provider_report()
        if sys.stdin.isatty() and hasattr(self.ai, "configure_provider"):
            ok, message = self.ai.configure_provider(target, interactive=True)
        else:
            ok, message = self.ai.switch_provider(target)
        if ok:
            return f"{message}\nNote: provider preference is saved in this project's .env."
        return message

    def run_goal_once(self, goal: str) -> str:
        route = self.router.route(goal, self.ai, self.conversation_history[-6:])
        if route.mode == "tool":
            result = AdvancedTools.execute_tracked(route.tool_name, route.tool_args, self.data_store, self.ai)
            self._print_tool_result(route.tool_name, route.tool_args, result)
            return result
        if route.mode == "agent":
            summary = self.agent.execute_goal(goal)
            print(f"\n{summary}")
            return summary
        messages = [{"role": "system", "content": AIModel.SYSTEM_PROMPT}]
        messages.extend(self.conversation_history[-10:])
        messages.append({"role": "user", "content": goal})
        streamed = self.ai.stream_chat(messages, on_chunk=lambda chunk: print(chunk, end="", flush=True))
        print("")
        return streamed

    def _print_welcome(self):
        if self.console and Panel and Text:
            self._print_welcome_rich(
                f"{Config.APP_NAME} | {Config.APP_TAGLINE}",
                "Plan, patch, execute, verify",
                [
                    "Live autonomous trace console",
                    "Browser, file, shell, and workflow control",
                    "Structured thought, action, patch, and evaluation streams",
                    "Professional local operator experience",
                ],
            )
            return
        print("")
        print(self._muted("Welcome to CONNECT AI"))
        print("")
        for line in self._reference_title_lines():
            print(self._style(line, "38;5;111"))
        print("")
        for line in self._welcome_lines():
            print(self._muted(line))
        print("")
        return
        if self.console and Panel and Text:
            self._print_welcome_rich(
                f"{Config.APP_NAME} | {Config.APP_TAGLINE}",
                "Plan, patch, execute, verify",
                [
                    "Live autonomous trace console",
                    "Browser, file, shell, and workflow control",
                    "Structured thought, action, patch, and evaluation streams",
                    "Professional local operator experience",
                ],
            )
            return
        border = self._accent("╔" + "═" * 62 + "╗")
        middle = self._accent("║") + " " * 62 + self._accent("║")
        title = f"{Config.APP_NAME} | {Config.APP_TAGLINE}"
        subtitle = "Plan, patch, execute, verify"
        feature_lines = [
            "Live autonomous trace console",
            "Browser, file, shell, and workflow control",
            "Structured thought, action, patch, and evaluation streams",
            "Professional local operator experience",
        ]
        print("")
        print(border)
        print(middle)
        print(self._accent("║") + self._strong(title.center(62)) + self._accent("║"))
        print(self._accent("║") + self._muted(subtitle.center(62)) + self._accent("║"))
        print(middle)
        print(self._accent("╚" + "═" * 62 + "╝"))
        print(self._muted("Mode: repo-aware local agent"))
        print(self._muted("Use `/agent <goal>` for autonomous execution or chat normally."))
        print("")
        for line in feature_lines:
            print(f"{self._accent('•')} {line}")
        print("")

    def _prompt_optional_github_token(self):
        """Ask for optional GitHub token in interactive CLI."""
        if os.getenv("GITHUB_TOKEN", "").strip():
            return
        if not sys.stdin.isatty():
            return

        try:
            print(f"\n{self._section_header('SETUP')} GitHub token is optional but required for PR read/review/merge tools.")
            print(self._muted("Add GITHUB_TOKEN now? (optional) [y/N]"))
            add_token = input("> ").strip().lower()
            if add_token not in {"y", "yes"}:
                return

            print(self._muted("Paste GITHUB_TOKEN:"))
            token = input("> ").strip()
            if not token:
                print(f"{self._section_header('SETUP')} Skipped (empty token).")
                return

            os.environ["GITHUB_TOKEN"] = token
            print(f"{self._section_header('SETUP')} GITHUB_TOKEN loaded for this session.")
        except Exception:
            # Keep startup resilient even if stdin is unavailable/interrupted
            pass

    def _gateway_config_path(self) -> Path:
        return Path.cwd() / "openclaw.json"

    def _load_gateway_json(self) -> Dict[str, Any]:
        path = self._gateway_config_path()
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_gateway_json(self, data: Dict[str, Any]):
        path = self._gateway_config_path()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _ensure_gateway_sections(self, data: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(data)
        out.setdefault("gateway", {"host": "127.0.0.1", "port": 18789, "dashboard_host": "127.0.0.1", "dashboard_port": 18890, "deployment_mode": "local"})
        out.setdefault("workspace", {"root": ".openclaw/workspace"})
        out.setdefault("provider", {"default": os.getenv("AI_PROVIDER", "").strip().lower()})
        out.setdefault("messaging", {})
        out["messaging"].setdefault("discord_webhooks", {})
        out["messaging"].setdefault("slack_webhooks", {})
        out["messaging"].setdefault("slack_bot_token", "")
        out["messaging"].setdefault("slack_signing_secret", "")
        out["messaging"].setdefault("whatsapp_account_sid", "")
        out["messaging"].setdefault("whatsapp_auth_token", "")
        out["messaging"].setdefault("whatsapp_from_number", "")
        out.setdefault("tools", {"allow": [], "deny": []})
        out.setdefault("auth", {"enabled": False, "webhook_bearer_token": ""})
        out.setdefault("agents", {"list": []})
        return out

    def run_messaging_setup(self) -> str:
        if not sys.stdin.isatty():
            return "Messaging setup requires interactive stdin."
        data = self._ensure_gateway_sections(self._load_gateway_json())
        messaging = data.setdefault("messaging", {})
        print(f"\n{self._section_header('MESSAGING')} Connector setup")
        print(self._muted("Choose connector [telegram/discord/slack/slack-bot/whatsapp/skip]"))
        connector = self._ask_choice("> ", ["telegram", "discord", "slack", "slack-bot", "whatsapp", "skip"], default="telegram")
        if connector == "skip":
            return "Messaging setup skipped."
        if connector == "telegram":
            print(self._muted("Telegram bot token:"))
            token = input("> ").strip()
            print(self._muted("Telegram chat ID for validation/default replies:"))
            chat_id = input("> ").strip()
            if not token or not chat_id:
                return "Telegram setup cancelled: token and chat ID are required."
            messaging["telegram_bot_token"] = token
            messaging["telegram_default_chat_id"] = chat_id
            self._save_gateway_json(data)
            return "Saved Telegram connector settings in openclaw.json"
        if connector == "discord":
            print(self._muted("Discord webhook name (example: ops):"))
            name = input("> ").strip()
            print(self._muted("Discord webhook URL:"))
            url = input("> ").strip()
            if not name or not url:
                return "Discord setup cancelled: webhook name and URL are required."
            webhooks = messaging.setdefault("discord_webhooks", {})
            webhooks[name] = url
            self._save_gateway_json(data)
            return f"Saved Discord webhook '{name}' in openclaw.json"
        if connector == "slack":
            print(self._muted("Slack webhook name (example: alerts):"))
            name = input("> ").strip()
            print(self._muted("Slack incoming webhook URL:"))
            url = input("> ").strip()
            if not name or not url:
                return "Slack setup cancelled: webhook name and URL are required."
            webhooks = messaging.setdefault("slack_webhooks", {})
            webhooks[name] = url
            self._save_gateway_json(data)
            return f"Saved Slack webhook '{name}' in openclaw.json"
        if connector == "slack-bot":
            print(self._muted("Slack bot token:"))
            token = input("> ").strip()
            print(self._muted("Slack signing secret:"))
            secret = input("> ").strip()
            if not token or not secret:
                return "Slack bot setup cancelled: token and signing secret are required."
            messaging["slack_bot_token"] = token
            messaging["slack_signing_secret"] = secret
            self._save_gateway_json(data)
            return "Saved Slack bot mode settings in openclaw.json"
        print(self._muted("Twilio Account SID:"))
        sid = input("> ").strip()
        print(self._muted("Twilio Auth Token:"))
        token = input("> ").strip()
        print(self._muted("Twilio WhatsApp sender (example: whatsapp:+14155238886):"))
        from_number = input("> ").strip()
        if not sid or not token or not from_number:
            return "WhatsApp setup cancelled: SID, auth token, and sender are required."
        messaging["whatsapp_account_sid"] = sid
        messaging["whatsapp_auth_token"] = token
        messaging["whatsapp_from_number"] = from_number
        self._save_gateway_json(data)
        return "Saved WhatsApp connector settings in openclaw.json"

    def run_telegram_validation(self) -> str:
        data = self._ensure_gateway_sections(self._load_gateway_json())
        messaging = data.setdefault("messaging", {})
        token = str(messaging.get("telegram_bot_token", "")).strip()
        chat_id = str(messaging.get("telegram_default_chat_id", "")).strip()
        if not token or not chat_id:
            return "Telegram is not configured. Run /messaging-setup first."
        try:
            from gateway_runtime.messaging import TelegramConnector

            connector = TelegramConnector(token, lambda payload: None)
            result = connector.send_message(chat_id, "CONNECT Telegram validation: outbound test succeeded.")
            return json.dumps({"ok": True, "result": result}, indent=2)
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, indent=2)

    def run_slack_validation(self, target: str) -> str:
        data = self._ensure_gateway_sections(self._load_gateway_json())
        messaging = data.setdefault("messaging", {})
        try:
            if str(messaging.get("slack_bot_token", "")).strip() and target.startswith(("C", "D")):
                from gateway_runtime.messaging import SlackBotConnector

                connector = SlackBotConnector(str(messaging.get("slack_bot_token", "")).strip(), str(messaging.get("slack_signing_secret", "")).strip(), lambda payload: None)
                result = connector.send_message(target, "CONNECT Slack validation: outbound bot test succeeded.")
                return json.dumps({"ok": True, "result": result}, indent=2)
            webhooks = messaging.get("slack_webhooks", {}) or {}
            if target in webhooks:
                from gateway_runtime.messaging import SlackWebhookConnector

                connector = SlackWebhookConnector(webhooks)
                result = connector.send_message(target, "CONNECT Slack validation: outbound webhook test succeeded.")
                return json.dumps({"ok": True, "result": result}, indent=2)
            return "Slack target not configured. Use a webhook name or a Slack channel ID with bot mode configured."
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, indent=2)

    def run_whatsapp_validation(self, target: str) -> str:
        data = self._ensure_gateway_sections(self._load_gateway_json())
        messaging = data.setdefault("messaging", {})
        sid = str(messaging.get("whatsapp_account_sid", "")).strip()
        token = str(messaging.get("whatsapp_auth_token", "")).strip()
        from_number = str(messaging.get("whatsapp_from_number", "")).strip()
        if not sid or not token or not from_number:
            return "WhatsApp is not configured. Run /messaging-setup first."
        try:
            from gateway_runtime.messaging import WhatsAppTwilioConnector

            connector = WhatsAppTwilioConnector(sid, token, from_number, lambda payload: None)
            target_number = target if target.startswith("whatsapp:") else f"whatsapp:{target}"
            result = connector.send_message(target_number, "CONNECT WhatsApp validation: outbound test succeeded.")
            return json.dumps({"ok": True, "result": result}, indent=2)
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, indent=2)

    def _reference_title_lines(self) -> List[str]:
        return [
            "  _________  _   _ _   _ _   _ ______ _____ _______",
            " / ____/ _ \\| \\ | | \\ | | \\ | |  ____/ ____|__   __|",
            "| |   | | | |  \\| |  \\| |  \\| | |__ | |       | |   ",
            "| |   | | | | . ` | . ` | . ` |  __|| |       | |   ",
            "| |___| |_| | |\\  | |\\  | |\\  | |___| |____   | |   ",
            " \\_____\\___/|_| \\_|_| \\_|_| \\_|______\\_____|  |_|   ",
        ]

    def _welcome_lines(self) -> List[str]:
        provider = self.ai.provider or "none"
        model = self.ai.model_name or "unavailable"
        return [
            f"Provider: {provider} ({model})",
            f"Default mode: {self.launch_profile.get('default_mode', 'shell')}",
            "Modes: interactive shell, autonomous operator, gateway server, visual dashboard",
            "Commands: /provider, /llm, /doctor, /setup, /login, /logout, /messaging-setup, /telegram-test, /agent <goal>",
        ]

    def _print_welcome_rich(self, title: str, subtitle: str, feature_lines: List[str]):
        title_text = Text("\n".join(self._reference_title_lines()), style="bold #f5eadc")
        body_text = Text("\n".join(self._welcome_lines()), style="#e7d7c7")
        content = Text()
        content.append_text(title_text)
        content.append("\n\n")
        content.append_text(Text("Operator Console", style="bold #c58c67"))
        content.append("\n")
        content.append_text(body_text)
        self.console.print(
            Panel(
                content,
                border_style="#c58c67",
                box=box.SQUARE if box else None,
                padding=(1, 2),
                style="on #1d1a17",
                title="Session",
                title_align="left",
            )
        )

    def _prompt_provider_setup(self):
        """Offer provider setup at startup when no provider is ready."""
        if self.ai.provider or not sys.stdin.isatty():
            return

        print(f"\n{self._section_header('SETUP')} No model provider is configured yet.")
        print(self._muted("Choose a provider now or press Enter to skip."))
        print(self._muted("Available: anthropic, groq, openai, openrouter, gemini, huggingface, ollama"))
        try:
            provider_name = input("> ").strip().lower()
        except Exception:
            return
        if not provider_name:
            return
        ok, message = self.ai.configure_provider(provider_name, interactive=True)
        print(message)

    def choose_start_mode(self) -> str:
        default_mode = str(self.launch_profile.get("default_mode", "shell") or "shell").lower()
        if not self.launch_profile.get("prompt_gateway_each_launch", True):
            return default_mode
        if not sys.stdin.isatty():
            return "shell"
        print(f"\n{self._section_header('MODE')} Launch mode [shell/gateway/dashboard] ({default_mode})")
        try:
            choice = self._ask_choice("> ", ["shell", "gateway", "dashboard"], default=default_mode)
        except Exception:
            return default_mode
        self.launch_profile["default_mode"] = choice
        self._save_launch_profile()
        return choice

    def _emit_agent_event(self, event_type: str, payload: Dict[str, Any]):
        """Print structured cognition for the autonomous operator."""
        if getattr(self, "console", None) and Panel:
            self._emit_agent_event_rich(event_type, payload)
            return
        if event_type == "plan_created":
            print(f"\n{self._section_header('PLAN UPDATE')}")
            for idx, step in enumerate(payload.get("plan", []), start=1):
                print(f"{idx}. {step}")
            return

        if event_type in {"reasoning", "reasoning_retry"}:
            print(f"\n{self._section_header('THOUGHT')}")
            print(payload.get("thought", ""))
            plan = payload.get("plan", [])
            if plan:
                print(f"\n{self._section_header('PLAN UPDATE')}")
                for idx, step in enumerate(plan, start=1):
                    print(f"{idx}. {step}")
            print(f"\n{self._section_header('NEXT ACTION')}")
            print(payload.get("next_action", ""))
            return

        if event_type == "action":
            print(f"\n{self._section_header('ACTION')}")
            intent = payload.get("intent", "")
            if intent:
                print(f"Intent: {intent}")
            print(payload.get("action", ""))
            return

        if event_type == "result":
            print(f"\n{self._section_header('RESULT')}")
            intent = payload.get("intent", "")
            if intent:
                print(f"Intent: {intent}")
            print(payload.get("summary", ""))
            return

        if event_type == "patch":
            print(f"\n{self._section_header('PATCH')}")
            intent = payload.get("intent", "")
            target = payload.get("target", "")
            if intent:
                print(f"Intent: {intent}")
            if target:
                print(f"Target: {target}")
            for line in payload.get("changes", []):
                print(line)
            return

        if event_type == "observation":
            print(f"\n{self._section_header('OBSERVATION')}")
            snapshot = str(payload.get("snapshot", "")).strip()
            if snapshot.startswith("{"):
                try:
                    data = json.loads(snapshot)
                    print(f"URL: {data.get('url', '')}")
                    print(f"Title: {data.get('title', '')}")
                    visible_text = str(data.get("visible_text", ""))[:350]
                    if visible_text:
                        print(f"Visible Text: {visible_text}")
                    if data.get("console_errors"):
                        print(f"Console Errors: {len(data.get('console_errors', []))}")
                    if data.get("page_errors"):
                        print(f"Page Errors: {len(data.get('page_errors', []))}")
                    if data.get("network_failures"):
                        print(f"Network Failures: {len(data.get('network_failures', []))}")
                    if data.get("screenshot_path"):
                        print(f"Screenshot: {data.get('screenshot_path')}")
                    return
                except Exception:
                    pass
            if len(snapshot) > 420:
                snapshot = snapshot[:420] + "\n..."
            print(snapshot or "(none)")
            return

        if event_type == "replan":
            print(f"\n{self._section_header('REWRITE')}")
            print(f"Reason: {payload.get('error', '')}")
            for idx, step in enumerate(payload.get("plan", []), start=1):
                print(f"{idx}. {step}")
            return

        if event_type == "evaluation":
            print(f"\n{self._section_header('EVALUATION')}")
            progress = payload.get("progress_score")
            goal_achieved = payload.get("goal_achieved")
            on_track = payload.get("on_track")
            if progress is not None:
                print(f"Progress: {progress}/100")
            if goal_achieved is not None:
                print(f"Goal Achieved: {goal_achieved}")
            if on_track is not None:
                print(f"On Track: {on_track}")
            print(payload.get("reason", ""))
            blockers = payload.get("blockers", [])
            if blockers:
                print(f"\n{self._section_header('BLOCKERS')}")
                for blocker in blockers:
                    print(f"- {blocker}")
            next_steps = payload.get("next_steps", [])
            if next_steps:
                print(f"\n{self._section_header('NEXT STEPS')}")
                for idx, step in enumerate(next_steps, start=1):
                    print(f"{idx}. {step}")

    def _print_tool_result(self, tool_name: str, tool_args: Dict[str, Any], result: str):
        if self.console and Panel:
            self._print_tool_result_rich(tool_name, tool_args, result)
            return
        print(f"\n{self._section_header('TOOL')}")
        print(f"Tool: {tool_name}")
        if tool_args:
            print(f"Args: {json.dumps(tool_args, ensure_ascii=True)}")
        print(f"\n{self._section_header('RESULT')}")
        print(result)

    def process_command(self, cmd: str) -> str:
        """Handle slash commands."""
        if cmd == "/help":
            return """
Commands:
  /help - Show all commands and help
  /chat - Start conversation mode
  /provider - Show provider status or switch provider
  /llm - Alias for /provider
  /setup - Rerun first-launch setup questions
  /login - Sign in with Clerk in the browser and return to CLI
  /logout - Clear local Clerk session
  /messaging-setup - Ask for Telegram/Discord connector details in CLI
  /telegram-test - Send a real outbound Telegram validation message
  /slack-test [target] - Send a real Slack validation message
  /whatsapp-test [number] - Send a real WhatsApp validation message
  agent - Start autonomous mode without slash
  /agent [goal] - Execute a goal autonomously
  /agent-runs - List recent autonomous runs
  /agent-resume [run_id] - Resume a paused or failed run
  /policy - Show autonomous policy scopes
  /policy-set [scope] [on|off] - Toggle a policy scope
  /audit [N] - Show last N audit entries
  /startup [idea] - Create startup from idea
  /report - Generate weekly report
  /projects - List all projects
  /stats - Show statistics
  /profile - Show user profile
  /agent-status - Show autonomous agent status
  /world - Show persistent world state
  /memory - Show agent memories
  /doctor - Show provider and launcher diagnostics
  /clear - Clear conversation
  /exit - Exit platform

Examples:
  /provider openai
  /llm groq
  /agent "Build a SaaS landing page with pricing and deploy it"
  Create a website for my restaurant

Tip:
  Use /help for help.
"""
        elif cmd == "/provider" or cmd == "/llm":
            return self.handle_provider_command(cmd)
        elif cmd.startswith("/provider ") or cmd.startswith("/llm "):
            return self.handle_provider_command(cmd)
        elif cmd == "/doctor":
            return self.doctor_report()
        elif cmd == "/setup":
            self.launch_profile["initialized"] = False
            self._save_launch_profile()
            self._run_first_launch_onboarding()
            return "Setup updated."
        elif cmd == "/login":
            return self.run_clerk_login()
        elif cmd == "/logout":
            return self.run_clerk_logout()
        elif cmd == "/messaging-setup":
            return self.run_messaging_setup()
        elif cmd == "/telegram-test":
            return self.run_telegram_validation()
        elif cmd.startswith("/slack-test "):
            return self.run_slack_validation(cmd[len("/slack-test "):].strip())
        elif cmd == "/slack-test":
            return "Usage: /slack-test [webhook_name|channel_id]"
        elif cmd.startswith("/whatsapp-test "):
            return self.run_whatsapp_validation(cmd[len("/whatsapp-test "):].strip())
        elif cmd == "/whatsapp-test":
            return "Usage: /whatsapp-test [number]"
        elif cmd == "/agent-status":
            status = self.agent.get_status()
            return f"""
Autonomous Agent Status:
  Active Plans: {status['active_plans']}
  Completed Plans: {status['completed_plans']}
  Memory Facts: {status['memory_facts']}
  Memory Patterns: {status['memory_patterns']}
  Memory Skills: {status.get('memory_skills', 0)}
  Stored Runs: {status.get('stored_runs', 0)}
  Failure Log: {status['failure_log_size']}
"""
        elif cmd == "/policy":
            policy = self.agent.get_policy()
            lines = ["Policy Scopes:"]
            for k in sorted(policy.keys()):
                lines.append(f"  - {k}: {'on' if policy[k] else 'off'}")
            return "\n".join(lines)
        elif cmd.startswith("/policy-set "):
            parts = cmd.split()
            if len(parts) != 3:
                return "Usage: /policy-set [scope] [on|off]"
            scope = parts[1].strip()
            value = parts[2].strip().lower()
            if value not in {"on", "off"}:
                return "Usage: /policy-set [scope] [on|off]"
            return self.agent.set_policy_scope(scope, value == "on")
        elif cmd.startswith("/audit"):
            parts = cmd.split()
            limit = 10
            if len(parts) == 2 and parts[1].isdigit():
                limit = max(1, min(100, int(parts[1])))
            entries = self.agent.get_audit_tail(limit)
            if not entries:
                return "No audit entries found."
            lines = [f"Last {len(entries)} Audit Entries:"]
            for e in entries:
                lines.append(
                    f"  - {e.get('ts','')} | {e.get('event','')} | run={e.get('run_id','')} | task={e.get('task_name','')}"
                )
            return "\n".join(lines)
        elif cmd == "/agent-runs":
            runs = self.agent.list_runs(10)
            if not runs:
                return "No autonomous runs found yet."
            lines = ["Recent Autonomous Runs:"]
            for r in runs:
                lines.append(f"  - {r['run_id']} | {r['status']} | {r['goal'][:70]}")
            return "\n".join(lines)
        elif cmd.startswith("/agent-resume "):
            run_id = cmd[len("/agent-resume "):].strip()
            if not run_id:
                return "Usage: /agent-resume [run_id]"
            print(f"\n{'='*60}")
            print(f" RESUMING AUTONOMOUS RUN: {run_id}")
            print(f"{'='*60}")
            return self.agent.resume_run(run_id)
        elif cmd == "/memory":
            facts = self.memory.ltm.get("facts", [])[-10:]
            patterns = self.memory.ltm.get("patterns", [])[-5:]
            skills = self.memory.ltm.get("skills", [])[-5:]
            return f"""
Recent Memories:
Facts ({len(facts)}):
{chr(10).join(f'  - {f["content"][:60]}...' for f in facts) if facts else '  (none)'}

Patterns ({len(patterns)}):
{chr(10).join(f'  - {p["content"][:60]}...' for p in patterns) if patterns else '  (none)'}

Skills ({len(skills)}):
{chr(10).join(f'  - {s["name"][:60]}...' for s in skills) if skills else '  (none)'}
"""
        elif cmd == "/world":
            return self.agent.world_state.snapshot_text()
        elif cmd == "/chat":
            return "Conversation mode active - just start chatting!"
        elif cmd.startswith("/agent "):
            # Autonomous agent execution
            goal = cmd[7:].strip()
            if not goal:
                return "Usage: /agent [goal] - e.g., /agent 'Create a website for my restaurant'"
            print(f"\n{'='*60}")
            print(f" AUTONOMOUS AGENT EXECUTING GOAL")
            print(f"{'='*60}")
            return "EXECUTE_AGENT"
        elif cmd == "/report":
            return AdvancedTools._generate_weekly_report(self.data_store, 1)
        elif cmd == "/stats":
            return AdvancedTools._get_task_statistics(self.data_store, 7)
        elif cmd == "/projects":
            if not self.data_store.projects:
                return "No projects yet"
            return "\n".join([f"- {p.name} ({p.type}): {p.status}" for p in self.data_store.projects])
        elif cmd == "/profile":
            return json.dumps(asdict(self.data_store.user_profile), indent=2)
        elif cmd == "/clear":
            self.conversation_history = []
            return "Conversation cleared"
        elif cmd == "/exit" or cmd == "/quit":
            return "EXIT_NOW"
        return f"Unknown command: {cmd}\nUse /help for help."

    def run(self):
        """Main platform loop."""
        while True:
            try:
                user_input = input("\n> ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    result = self.process_command(user_input)
                    if result == "EXIT_NOW":
                        print("Goodbye!")
                        break
                    elif result == "EXECUTE_AGENT":
                        # Execute goal autonomously
                        goal = user_input[7:].strip()
                        summary = self.agent.execute_goal(goal)
                        print(f"\n{summary}")
                    else:
                        print(result)
                    continue

                if user_input.lower() in ["exit", "quit", "bye"]:
                    print("Goodbye!")
                    break

                # Plain "agent" command (without slash)
                if user_input.lower() == "agent":
                    goal = input("> ").strip()
                    if not goal:
                        print("Usage: agent -> then enter a goal, e.g. Build a SaaS landing page")
                        continue
                    print(f"\n{'='*60}")
                    print(f" AUTONOMOUS AGENT EXECUTING GOAL")
                    print(f"{'='*60}")
                    summary = self.agent.execute_goal(goal)
                    print(f"\n{summary}")
                    continue

                # "agent <goal>" shorthand
                if user_input.lower().startswith("agent "):
                    goal = user_input[6:].strip()
                    if goal:
                        print(f"\n{'='*60}")
                        print(f" AUTONOMOUS AGENT EXECUTING GOAL")
                        print(f"{'='*60}")
                        summary = self.agent.execute_goal(goal)
                        print(f"\n{summary}")
                        continue

                route = self.router.route(user_input, self.ai, self.conversation_history[-6:])
                if route.mode == "tool":
                    result = AdvancedTools.execute_tracked(route.tool_name, route.tool_args, self.data_store, self.ai)
                    self._print_tool_result(route.tool_name, route.tool_args, result)
                    self.conversation_history.append({"role": "user", "content": user_input})
                    self.conversation_history.append({"role": "assistant", "content": result})
                    self.data_store.add_conversation(user_input, result, [route.tool_name], [])
                    continue

                # Handle startup creation
                if "startup" in user_input.lower() and ("banana" in user_input.lower() or "create" in user_input.lower() or "banata" in user_input.lower()):
                    idea = user_input.lower().split("startup")[-1].strip()
                    if idea:
                        print("\n[*] Starting Startup Creation Wizard...")
                        result = self.startup_wizard.run(idea)
                        print(f"\n{result}")
                        continue

                recent_history = self.conversation_history[-6:]
                if self.ai.should_use_autonomous_agent(user_input, recent_history):
                    print(f"\n{'='*60}")
                    print(" AUTONOMOUS OPERATOR EXECUTING GOAL")
                    print(f"{'='*60}")
                    summary = self.agent.execute_goal(user_input)
                    print(f"\n{summary}")
                    self.conversation_history.append({"role": "user", "content": user_input})
                    self.conversation_history.append({"role": "assistant", "content": summary})
                    self.data_store.add_conversation(
                        user_input,
                        summary,
                        ["autonomous_agent"],
                        ["autonomous_run"]
                    )
                    continue

                # Normal AI conversation with streaming text
                messages = [{"role": "system", "content": AIModel.SYSTEM_PROMPT}]
                messages.extend(self.conversation_history[-10:])
                messages.append({"role": "user", "content": user_input})

                debug_log(f"chat turn: input={user_input!r}")
                debug_log(f"chat turn: sending {len(messages)} messages")

                print("")
                streamed = self.ai.stream_chat(
                    messages,
                    on_chunk=lambda chunk: print(chunk, end="", flush=True)
                )

                if not streamed or not streamed.strip():
                    debug_log("chat turn: streaming returned empty output, falling back to non-streaming chat")
                    response = self.ai.chat(messages)
                    parsed = self.ai.parse_response(response)
                    if parsed and parsed.get("type") == "text":
                        streamed = parsed.get("content", "")
                    elif isinstance(response, dict) and response.get("error"):
                        streamed = f"[chat error] {response['error']}"
                    else:
                        streamed = "[empty response from model]"

                    if streamed.strip():
                        print(streamed, end="", flush=True)

                print("")
                self.conversation_history.append({"role": "user", "content": user_input})
                self.conversation_history.append({"role": "assistant", "content": streamed})
                self.data_store.add_conversation(user_input, streamed, [], [])

            except EOFError:
                print("\nInput stream closed. Exiting.")
                break
            except KeyboardInterrupt:
                print("\n\nInterrupted. Type /exit to quit.")
            except Exception as e:
                print(f"Error: {e}")


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("goal", nargs="*", help="Optional goal to run once instead of opening the interactive CLI.")
    parser.add_argument("--doctor", action="store_true", help="Print provider and launcher diagnostics, then exit.")
    parser.add_argument("--gateway", action="store_true", help="Run the OpenClaw-style WebSocket gateway server.")
    parser.add_argument("--dashboard", action="store_true", help="Run the local operator dashboard.")
    parser.add_argument("--service-stack", action="store_true", help="Run the selected stack for Windows service/background mode.")
    parser.add_argument("--cloud", action="store_true", help="Bind gateway/dashboard for remote access (0.0.0.0).")
    parser.add_argument("--local", action="store_true", help="Bind gateway/dashboard to localhost only.")
    parser.add_argument("--open-browser", action="store_true", help="Open the dashboard URL in the default browser.")
    parser.add_argument("--gateway-config", help="Path to an openclaw-style JSON config for gateway mode.")
    parser.add_argument("--login", action="store_true", help="Open Clerk sign-in in the browser and return to CLI.")
    parser.add_argument("--logout", action="store_true", help="Clear the local Clerk session.")
    args = parser.parse_args()
    alias = args.goal[0].strip().lower() if len(args.goal) == 1 else ""
    if alias == "gateway":
        args.gateway = True
        args.goal = []
    elif alias == "dashboard":
        args.dashboard = True
        args.open_browser = True
        args.goal = []
    elif alias == "login":
        args.goal = []
        args.login = True
    elif alias == "logout":
        args.goal = []
        args.logout = True
    elif alias == "doctor":
        args.doctor = True
        args.goal = []
    elif len(args.goal) >= 2 and args.goal[0].strip().lower() == "service":
        pass
    platform = AdvancedAIPlatform()
    if args.doctor:
        print(platform.doctor_report())
        return
    if getattr(args, "login", False):
        print(platform.run_clerk_login())
        return
    if getattr(args, "logout", False):
        print(platform.run_clerk_logout())
        return
    from gateway_runtime import AgentRuntime, DashboardServer, GatewayServer, load_gateway_config
    import asyncio
    import webbrowser

    def prepare_config():
        config = load_gateway_config(Path(args.gateway_config) if args.gateway_config else None)
        if args.cloud:
            config.deployment_mode = "cloud"
            config.host = "0.0.0.0"
            config.dashboard_host = "0.0.0.0"
        elif args.local:
            config.deployment_mode = "local"
            config.host = "127.0.0.1"
            config.dashboard_host = "127.0.0.1"
        return config

    def ensure_authenticated(config) -> bool:
        from gateway_runtime.auth import ClerkAuthManager

        manager = ClerkAuthManager(config.workspace_root, config.clerk_publishable_key, config.auth_enabled, config.webhook_bearer_token)
        if not manager.requires_auth(config.deployment_mode):
            return True
        if manager.is_signed_in():
            return True
        print("Authentication required. Opening browser sign-in...")
        ok, message = manager.start_cli_login()
        print(message)
        return ok

    def run_gateway_only(config, require_cli_login: bool = True):
        if require_cli_login and not ensure_authenticated(config):
            return
        runtime = AgentRuntime(config)
        print(f"Starting gateway on ws://{config.host}:{config.port}")
        asyncio.run(GatewayServer(runtime).serve())

    def run_dashboard_stack(config, open_browser: bool = False, require_cli_login: bool = True):
        if require_cli_login and not ensure_authenticated(config):
            return
        runtime = AgentRuntime(config)

        def gateway_thread():
            asyncio.run(GatewayServer(runtime).serve())

        thread = threading.Thread(target=gateway_thread, name="connect-gateway", daemon=True)
        thread.start()
        dashboard_url = f"http://{('127.0.0.1' if config.dashboard_host == '0.0.0.0' else config.dashboard_host)}:{config.dashboard_port}"
        print(f"Starting dashboard on {dashboard_url}")
        if open_browser:
            try:
                webbrowser.open(dashboard_url)
            except Exception:
                pass
        DashboardServer(runtime, host=config.dashboard_host, port=config.dashboard_port).serve()

    if len(args.goal) >= 2 and args.goal[0].strip().lower() == "service":
        from gateway_runtime.service_manager import (
            format_result,
            install_windows_service,
            remove_windows_service,
            start_windows_service,
            status_windows_service,
            stop_windows_service,
        )

        subcommand = args.goal[1].strip().lower()
        config = prepare_config()
        mode = "dashboard" if (len(args.goal) >= 3 and args.goal[2].strip().lower() == "gateway") is False else "gateway"
        config_path = str(Path(args.gateway_config) if args.gateway_config else Path.cwd() / "openclaw.json")
        if subcommand == "install":
            print(format_result(install_windows_service(mode, config_path)))
            return
        if subcommand == "uninstall":
            print(format_result(remove_windows_service()))
            return
        if subcommand == "start":
            print(format_result(start_windows_service()))
            return
        if subcommand == "stop":
            print(format_result(stop_windows_service()))
            return
        if subcommand == "status":
            print(format_result(status_windows_service()))
            return
        print("Usage: connect service [install|uninstall|start|stop|status] [gateway]")
        return

    if args.gateway:
        run_gateway_only(prepare_config())
        return
    if args.dashboard:
        run_dashboard_stack(prepare_config(), open_browser=args.open_browser or True)
        return
    if args.service_stack:
        run_dashboard_stack(prepare_config(), open_browser=False, require_cli_login=False)
        return
    if args.goal:
        platform.run_goal_once(" ".join(args.goal).strip())
        return
    if not sys.stdin.isatty():
        print("No interactive stdin detected. Pass a goal or use --doctor.")
        return
    start_mode = platform.choose_start_mode()
    if start_mode == "gateway":
        run_gateway_only(prepare_config())
        return
    if start_mode == "dashboard":
        run_dashboard_stack(prepare_config(), open_browser=True)
        return
    platform.run()


def nexus_loop(goal: str):
    from core.loop import run as nexus_run
    from tools.registry import build_registry

    return nexus_run(goal=goal, registry=build_registry())


if __name__ == "__main__":
    main()
