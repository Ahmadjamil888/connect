from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from config.config import (
    get_provider_defaults,
    load_config,
    resolve_runtime_state_root,
    save_config,
)
from core import model_manager
from setup.autostart import enable_autostart
from setup.consent import ConsentManager

try:
    from colorama import init as colorama_init
except Exception:
    def colorama_init(*_args, **_kwargs):
        return None


colorama_init(autoreset=True)

ORANGE = "\033[38;5;208m"
WHITE = "\033[97m"
DIM = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"

IMOS_LOGO = [
    "██╗███╗   ███╗ ██████╗ ███████╗",
    "██║████╗ ████║██╔═══██╗██╔════╝",
    "██║██╔████╔██║██║   ██║███████╗",
    "██║██║╚██╔╝██║██║   ██║╚════██║",
    "██║██║ ╚═╝ ██║╚██████╔╝███████║",
    "╚═╝╚═╝     ╚═╝ ╚═════╝ ╚══════╝",
]

PROVIDER_CHOICES = {
    "1": ("groq", "Groq", "GROQ_API_KEY"),
    "2": ("anthropic", "Anthropic", "ANTHROPIC_API_KEY"),
    "3": ("openai", "OpenAI", "OPENAI_API_KEY"),
    "4": ("gemini", "Google", "GOOGLE_AI_API_KEY"),
    "5": ("openrouter", "OpenRouter", "OPENROUTER_API_KEY"),
}
PROVIDER_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-3-5-sonnet-20241022",
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
    "openrouter": "openai/gpt-4o",
}

VOICE_CHOICES = {
    "1": ("gemini-tts", "Google Gemini TTS", "Kore"),
    "2": ("openai-tts", "OpenAI TTS", "nova"),
    "3": ("pyttsx3", "pyttsx3", ""),
}


def _env_path(project_root: Path) -> Path:
    return project_root / ".env"


def _setup_flag_path(workspace: str | Path | None) -> Path:
    return resolve_runtime_state_root(workspace) / "setup_complete"


def _print_logo() -> None:
    for line in IMOS_LOGO:
        print(f"{ORANGE}{line}{RESET}")


def _step_title(title: str) -> None:
    print()
    print(f"{WHITE}{BOLD}{title}{RESET}")
    print()


def _ask(prompt: str, default: str = "") -> str:
    value = input(f"{WHITE}{prompt}{RESET}")
    return value.strip() or default


def _yes_no(prompt: str) -> bool:
    while True:
        value = _ask(prompt).lower()
        if value in {"yes", "y"}:
            return True
        if value in {"no", "n"}:
            return False
        print(f"{WHITE}Please enter yes or no.{RESET}")


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env(path: Path, updates: dict[str, str]) -> None:
    values = _read_env(path)
    for key, value in updates.items():
        if value == "":
            values.pop(key, None)
        else:
            values[key] = value
            os.environ[key] = value
    lines = [f"{key}={value}" for key, value in sorted(values.items())]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _validate_provider(provider: str, api_key: str) -> None:
    if provider == "groq":
        from openai import OpenAI

        OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1").models.list()
        return
    if provider == "anthropic":
        import anthropic

        anthropic.Anthropic(api_key=api_key).models.list(limit=1)
        return
    if provider == "openai":
        from openai import OpenAI

        OpenAI(api_key=api_key).models.list()
        return
    if provider == "gemini":
        from google import genai

        next(iter(genai.Client(api_key=api_key).models.list()), None)
        return
    if provider == "openrouter":
        from openai import OpenAI

        OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1").models.list()


def ensure_first_run_setup(project_root: Path, workspace: str | Path | None) -> None:
    if _setup_flag_path(workspace).exists():
        return
    run_setup_wizard(project_root, workspace, forced=False)


def force_run_setup_wizard(project_root: Path, workspace: str | Path | None) -> None:
    run_setup_wizard(project_root, workspace, forced=True)


def run_setup_wizard(project_root: Path, workspace: str | Path | None, forced: bool) -> dict[str, Any]:
    cfg = load_config()
    env_file = _env_path(project_root)
    state_root = resolve_runtime_state_root(workspace or cfg.get("workspace") or project_root)
    consent_manager = ConsentManager(state_root)

    os.system("cls" if os.name == "nt" else "clear")

    _step_title("IMOS  First-time Setup")
    _print_logo()
    print()
    print(f"{WHITE}Welcome. This wizard configures IMOS once.{RESET}")
    input(f"{WHITE}Press Enter to continue.{RESET}")

    _step_title("Step 2  PC Control Consent")
    print(f"{WHITE}IMOS can control your PC: open apps, send messages,{RESET}")
    print(f"{WHITE}manage files, execute commands, and more.{RESET}")
    print()
    consent_granted = _yes_no("Grant full PC access? (yes/no): ")
    consent_manager.save(consent_granted)

    _step_title("Step 3  AI Model Provider")
    print(f"{WHITE}Choose your primary AI provider:{RESET}")
    print()
    print(f"{WHITE}1. Groq       {DIM}(free, fast  recommended){RESET}")
    print(f"{WHITE}2. Anthropic  {DIM}(Claude){RESET}")
    print(f"{WHITE}3. OpenAI     {DIM}(GPT-4o){RESET}")
    print(f"{WHITE}4. Google     {DIM}(Gemini){RESET}")
    print(f"{WHITE}5. OpenRouter {DIM}(multi-model){RESET}")
    print()
    provider = ""
    provider_label = ""
    api_key = ""
    while True:
        choice = ""
        while choice not in PROVIDER_CHOICES:
            choice = _ask("Enter choice (1-5): ")
        provider, provider_label, env_key = PROVIDER_CHOICES[choice]
        api_key = ""
        attempts = 0
        while attempts < 3:
            while not api_key:
                api_key = _ask("Enter your API key: ")
            provider_data = {
                "id": f"{provider}-wizard",
                "name": provider_label,
                "type": provider,
                "api_key": api_key,
                "base_url": get_provider_defaults(provider).get("base_url", ""),
                "model": PROVIDER_MODELS.get(provider, get_provider_defaults(provider).get("model", "")),
                "enabled": True,
                "is_default": True,
            }
            model_manager.add_provider(provider_data)
            result = model_manager.test_provider(provider_data["id"])
            if result.get("ok"):
                print(f" Connected  {result['latency']}ms")
                break
            attempts += 1
            print(f" Connection failed: {result.get('error')}")
            print("  Check your API key and try again.")
            api_key = ""
        defaults = get_provider_defaults(provider)
        model_cfg = dict(defaults)
        model_cfg["provider"] = provider
        if "api_key" in model_cfg:
            model_cfg["api_key"] = api_key
        cfg["model"] = model_cfg
        _write_env(
            env_file,
            {
                "AI_PROVIDER": provider,
                env_key: api_key,
            },
        )
        add_another = _ask("Add another provider? (yes/no) [no]: ", default="no").lower()
        if add_another not in {"yes", "y"}:
            break
        print()

    _step_title("Step 4  Voice Output")
    print(f"{WHITE}Choose voice provider:{RESET}")
    print()
    print(f"{WHITE}1. Google Gemini TTS  {DIM}(gemini-2.0-flash-preview-tts){RESET}")
    print(f"{WHITE}2. OpenAI TTS         {DIM}(tts-1, voices: alloy/echo/nova/shimmer){RESET}")
    print(f"{WHITE}3. pyttsx3            {DIM}(free, local, no key needed){RESET}")
    print()
    voice_choice = ""
    while voice_choice not in VOICE_CHOICES:
        voice_choice = _ask("Enter choice (1-3): ")
    voice_provider, voice_label, voice_name = VOICE_CHOICES[voice_choice]
    voice_key = ""
    if voice_choice in {"1", "2"}:
        voice_key = _ask("Enter API key (Enter to reuse Step 3 key): ", default=api_key)
    _write_env(
        env_file,
        {
            "VOICE_PROVIDER": voice_provider,
            "VOICE_API_KEY": voice_key,
            "VOICE_VOICE_ID": voice_name,
        },
    )

    _step_title("Step 5  Wake Word")
    wake_word = _ask("Wake word (default: IMOS, Enter to keep): ", default="IMOS")
    _write_env(env_file, {"WAKE_WORD": wake_word})
    cfg.setdefault("listen", {})
    cfg["listen"]["wake_word"] = wake_word
    cfg["listen"].setdefault("enabled", False)

    _step_title("Step 6  Integrations")
    smtp_host = _ask("Email SMTP host     (Enter to skip): ")
    smtp_port = _ask("Email SMTP port     (Enter to skip): ")
    smtp_user = _ask("Email address       (Enter to skip): ")
    smtp_pass = _ask("Email password      (Enter to skip): ")
    telegram_token = _ask("Telegram bot token  (Enter to skip): ")
    _write_env(
        env_file,
        {
            "SMTP_HOST": smtp_host,
            "SMTP_PORT": smtp_port,
            "SMTP_USER": smtp_user,
            "SMTP_PASSWORD": smtp_pass,
            "TELEGRAM_BOT_TOKEN": telegram_token,
        },
    )

    _step_title("Step 7  Auto-start")
    autostart_enabled = _yes_no("Start IMOS on Windows boot? (yes/no): ")
    if autostart_enabled:
        enable_autostart(project_root)
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        service = project_root / "service" / "imos_service.py"
        try:
            subprocess.Popen([str(pythonw), str(service)], cwd=str(project_root))
        except Exception:
            pass

    cfg["workspace"] = str(workspace or cfg.get("workspace") or project_root)
    cfg["autostart"] = bool(autostart_enabled)
    cfg.setdefault("listen", {})
    cfg["listen"]["enabled"] = True
    cfg["listen"]["persist"] = True
    save_config(cfg)
    _setup_flag_path(cfg["workspace"]).write_text("complete\n", encoding="utf-8")

    _step_title("Step 8  Complete")
    print(f"{WHITE}IMOS configured successfully.{RESET}")
    print()
    print(f"{WHITE}Provider:   {ORANGE}{provider_label}{RESET}")
    print(f"{WHITE}Voice:      {ORANGE}{voice_label}{RESET}")
    print(f"{WHITE}Wake word:  {ORANGE}{wake_word}{RESET}")
    print(f"{WHITE}Dashboard:  {ORANGE}http://127.0.0.1:8766{RESET}")
    print(f"{WHITE}Autostart:  {ORANGE}{'yes' if autostart_enabled else 'no'}{RESET}")
    print()
    print(f"{WHITE}Say \"Hey IMOS\" to activate hands-free.{RESET}")
    input(f"{WHITE}Press Enter to launch IMOS.{RESET}")
    return {
        "provider": provider,
        "voice_provider": voice_provider,
        "wake_word": wake_word,
        "autostart": autostart_enabled,
        "forced": forced,
    }
