"""
IMOS First-Time Setup Wizard.
Runs automatically on first launch or from the IMOS setup flow.
Covers: model, GitHub, cloud deploy, voice, workspace, system prompt,
        behaviour, goals, integrations, workflows, theme, fallbacks.
Writes everything to your local IMOS configuration.
"""
from __future__ import annotations

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from imos.ui import DASHBOARD_PALETTES, SHELL_PALETTES, get_cli_palette, setup_terminal_io

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"

# ── colours ──────────────────────────────────────────────────────────────────
setup_terminal_io()
_palette = get_cli_palette()
O  = _palette["O"]
W  = _palette["W"]
G  = _palette["G"]
Y  = O
R  = _palette["R"]
D  = _palette["D"]
X  = _palette["X"]
B  = W


def clr(text: str, c: str) -> str:
    return f"{c}{text}{X}"


def header(title: str):
    width = 60
    print()
    print(clr("─" * width, O))
    print(clr(f"  {title}", W))
    print(clr("─" * width, O))


def ask(prompt: str, default: str = "", secret: bool = False, required: bool = False) -> str:
    hint = f" {clr(f'[{default}]', D)}" if default else ""
    label = clr("  › ", O) + clr(prompt, W) + hint + clr(": ", D)
    while True:
        if secret:
            import getpass
            val = getpass.getpass(label)
        else:
            val = input(label).strip()
        if not val:
            val = default
        if required and not val:
            print(clr("    Required — please enter a value.", R))
            continue
        return val


def ask_choice(prompt: str, choices: list, default: str = "") -> str:
    print(clr(f"\n  {prompt}", W))
    for i, (key, label) in enumerate(choices, 1):
        marker = clr("●", O) if key == default else clr("○", D)
        print(f"    {marker} {clr(str(i), O)}. {label}")
    hint = f" {clr(f'[{default}]', D)}" if default else ""
    while True:
        raw = input(clr("  › ", O) + "Enter number or value" + hint + clr(": ", D)).strip()
        if not raw and default:
            return default
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx][0]
        for key, _ in choices:
            if raw.lower() == key.lower():
                return key
        print(clr("    Invalid choice.", R))


def ask_yn(prompt: str, default: bool = True) -> bool:
    hint = clr("[Y/n]" if default else "[y/N]", D)
    raw = input(clr("  › ", O) + clr(prompt, W) + " " + hint + clr(": ", D)).strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "1", "true")


def write_env(key: str, value: str):
    """Write or update a key in .env"""
    if not ENV_PATH.exists():
        ENV_PATH.write_text("", encoding="utf-8")
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.environ[key] = value


def read_env(key: str) -> str:
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(key, "")


def save_config_key(path: str, value):
    """Save a dot-path key into the local IMOS YAML config."""
    try:
        import yaml
        cfg_dir = Path.home() / ".connectai"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = cfg_dir / "config.yaml"
        cfg = {}
        if cfg_path.exists():
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        parts = path.split(".")
        node = cfg
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    except Exception as e:
        print(clr(f"    Warning: could not save config: {e}", Y))


def test_provider(provider: str, api_key: str, model: str) -> bool:
    """Quick test that the provider responds."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from config.config import get_client
        cfg = {"provider": provider, "model": model, "api_key": api_key}
        client = get_client(cfg)
        if provider in {"anthropic", "gcp"}:
            r = client.messages.create(model=model, max_tokens=5, messages=[{"role": "user", "content": "hi"}])
            return bool(r.content)
        else:
            r = client.chat.completions.create(model=model, max_tokens=5, messages=[{"role": "user", "content": "hi"}])
            return bool(r.choices)
    except Exception as e:
        print(clr(f"    Test failed: {e}", R))
        return False


# ── SECTIONS ─────────────────────────────────────────────────────────────────

def setup_model():
    header("1 / 9  —  AI Model")
    print(clr("  Choose your primary AI provider and model.", D))
    print(clr("  IMOS works with any provider — local or cloud.", D))

    providers = [
        ("anthropic",   "Anthropic Claude  (best tool use + vision)"),
        ("groq",        "Groq              (free tier, very fast)"),
        ("openai",      "OpenAI GPT-4o"),
        ("openrouter",  "OpenRouter        (routes to any model)"),
        ("gemini",      "Google Gemini     (free tier)"),
        ("huggingface", "Hugging Face      (free, many models)"),
        ("ollama",      "Ollama            (local, no key needed)"),
        ("azure",       "Azure OpenAI"),
        ("bedrock",     "AWS Bedrock"),
        ("nvidia",      "NVIDIA NIM"),
        ("gcp",         "GCP Vertex AI"),
    ]
    provider = ask_choice("Primary AI provider", providers, default="groq")
    write_env("AI_PROVIDER", provider)
    save_config_key("model.provider", provider)

    model_defaults = {
        "anthropic": "claude-sonnet-4-5",
        "groq": "llama-3.3-70b-versatile",
        "openai": "gpt-4o",
        "openrouter": "anthropic/claude-3.5-sonnet",
        "gemini": "gemini-2.0-flash",
        "huggingface": "meta-llama/Llama-3.1-8B-Instruct",
        "ollama": "llama3",
        "azure": "gpt-4o",
        "bedrock": "anthropic.claude-sonnet-4-5-20251101-v1:0",
        "nvidia": "meta/llama-3.1-70b-instruct",
        "gcp": "claude-sonnet-4-5@20251101",
    }
    default_model = model_defaults.get(provider, "")
    model = ask("Model name", default=default_model)
    save_config_key("model.model", model)

    if provider == "ollama":
        endpoint = ask("Ollama endpoint", default="http://localhost:11434")
        save_config_key("model.base_url", endpoint + "/v1")
        write_env("OLLAMA_MODEL", model)
        print(clr("  ✓ Ollama configured (no API key needed)", G))
    else:
        key_env = {
            "anthropic": "ANTHROPIC_API_KEY",
            "groq": "GROQ_API_KEY",
            "openai": "OPENAI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "gemini": "GOOGLE_GEMINI_API_KEY",
            "huggingface": "HUGGINGFACE_API_KEY",
            "azure": "AZURE_OPENAI_API_KEY",
            "bedrock": "AWS_ACCESS_KEY_ID",
            "nvidia": "NVIDIA_API_KEY",
            "gcp": "GOOGLE_CLOUD_PROJECT",
        }.get(provider, "API_KEY")

        existing = read_env(key_env)
        masked = ("***" + existing[-4:]) if len(existing) > 4 else ("set" if existing else "")
        prompt = f"API key for {provider}" + (f" (current: {masked})" if masked else "")
        api_key = ask(prompt, secret=True)
        if api_key:
            write_env(key_env, api_key)
            save_config_key("model.api_key", api_key)

        if provider == "azure":
            endpoint = ask("Azure endpoint (https://...openai.azure.com/)")
            if endpoint:
                write_env("AZURE_OPENAI_ENDPOINT", endpoint)
                save_config_key("model.base_url", endpoint)

        # Test connection
        if ask_yn("Test connection now?", default=True):
            print(clr("  Testing...", D), end="", flush=True)
            key = read_env(key_env)
            ok = test_provider(provider, key, model)
            print(clr(" ✓ Connected!", G) if ok else clr(" ✗ Failed (check key/model)", R))

    # Fallback model
    print()
    if ask_yn("Configure a fallback model (used if primary fails)?", default=False):
        fallback_providers = [p for p in providers if p[0] != provider]
        fb_provider = ask_choice("Fallback provider", fallback_providers, default="groq")
        fb_model = ask("Fallback model", default=model_defaults.get(fb_provider, ""))
        fb_key_env = {
            "groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY",
        }.get(fb_provider, "")
        if fb_key_env:
            fb_key = ask(f"API key for {fb_provider}", secret=True)
            if fb_key:
                write_env(fb_key_env, fb_key)
        save_config_key("fallback.provider", fb_provider)
        save_config_key("fallback.model", fb_model)
        print(clr(f"  ✓ Fallback: {fb_provider}/{fb_model}", G))


def setup_github():
    header("2 / 9  —  GitHub")
    print(clr("  IMOS uses GitHub to create repos, push code, and create PRs.", D))
    print(clr("  Your token is stored in .env (never committed to git).", D))
    print(clr("  Get a token: https://github.com/settings/tokens/new", D))
    print(clr("  Required scopes: repo, workflow", D))

    existing = read_env("GITHUB_TOKEN")
    if existing:
        print(clr(f"  Current token: ***{existing[-4:]}", D))
        if not ask_yn("Update GitHub token?", default=False):
            return

    token = ask("GitHub personal access token", secret=True)
    if token:
        write_env("GITHUB_TOKEN", token)
        # Test it
        try:
            import requests
            r = requests.get("https://api.github.com/user",
                             headers={"Authorization": f"token {token}"}, timeout=10)
            if r.status_code == 200:
                username = r.json().get("login", "")
                print(clr(f"  ✓ Connected as: {username}", G))
                save_config_key("github.username", username)
            else:
                print(clr(f"  ✗ Token invalid (HTTP {r.status_code})", R))
        except Exception as e:
            print(clr(f"  ✗ Could not verify: {e}", R))
    else:
        print(clr("  Skipped — GitHub features will be unavailable.", Y))


def setup_deployment():
    header("3 / 9  —  Cloud Deployment")
    print(clr("  Configure deployment targets. You can add more later in API Keys.", D))

    # Vercel
    print(clr("\n  Vercel", W))
    print(clr("  Get token: https://vercel.com/account/tokens", D))
    existing_v = read_env("VERCEL_TOKEN")
    if existing_v:
        print(clr(f"  Current: ***{existing_v[-4:]}", D))
    if not existing_v or ask_yn("Update Vercel token?", default=False):
        vt = ask("Vercel token (Enter to skip)", secret=True)
        if vt:
            write_env("VERCEL_TOKEN", vt)
            print(clr("  ✓ Vercel token saved", G))

    # Netlify
    print(clr("\n  Netlify", W))
    print(clr("  Get token: https://app.netlify.com/user/applications/personal", D))
    existing_n = read_env("NETLIFY_TOKEN")
    if existing_n:
        print(clr(f"  Current: ***{existing_n[-4:]}", D))
    if not existing_n or ask_yn("Update Netlify token?", default=False):
        nt = ask("Netlify token (Enter to skip)", secret=True)
        if nt:
            write_env("NETLIFY_TOKEN", nt)
            print(clr("  ✓ Netlify token saved", G))

    # AWS
    if ask_yn("\n  Configure AWS (for Bedrock / S3 / Lambda)?", default=False):
        write_env("AWS_ACCESS_KEY_ID", ask("AWS Access Key ID", secret=True))
        write_env("AWS_SECRET_ACCESS_KEY", ask("AWS Secret Access Key", secret=True))
        write_env("AWS_REGION", ask("AWS Region", default="us-east-1"))
        print(clr("  ✓ AWS configured", G))

    # Default deploy target
    deploy_target = ask_choice(
        "Default deploy target for new projects",
        [("vercel", "Vercel"), ("netlify", "Netlify"), ("none", "None (manual)")],
        default="vercel",
    )
    save_config_key("deploy.default_target", deploy_target)


def setup_workspace():
    header("4 / 9  —  Workspace")
    print(clr("  IMOS stores your projects and files in a workspace directory.", D))

    default_ws = str(Path.home() / "imos_workspace")
    existing_ws = read_env("IMOS_WORKSPACE") or default_ws
    ws = ask("Workspace directory", default=existing_ws)
    ws_path = Path(ws)
    ws_path.mkdir(parents=True, exist_ok=True)
    write_env("IMOS_WORKSPACE", str(ws_path))
    save_config_key("workspace", str(ws_path))
    print(clr(f"  ✓ Workspace: {ws_path}", G))


def setup_behaviour():
    header("5 / 9  —  Behaviour & Goals")
    print(clr("  Customise how IMOS behaves, its personality, and its goals.", D))

    # System prompt extra
    print(clr("\n  Extra system prompt instructions (appended to IMOS base prompt):", W))
    print(clr("  Example: 'Always respond in formal English. Prefer TypeScript over JavaScript.'", D))
    extra = ask("Extra instructions (Enter to skip)", default="")
    if extra:
        write_env("IMOS_SYSTEM_PROMPT_EXTRA", extra)
        save_config_key("behaviour.system_prompt_extra", extra)

    # Goals
    print(clr("\n  Primary goals (what IMOS should focus on):", W))
    goals_choices = [
        ("dev",       "Software development (build apps, deploy, manage code)"),
        ("ops",       "PC operations (automate tasks, manage files, monitor system)"),
        ("research",  "Research & knowledge (news, Wikipedia, data)"),
        ("assistant", "General assistant (everything)"),
        ("custom",    "Custom (I'll describe it)"),
    ]
    goal = ask_choice("Primary goal", goals_choices, default="assistant")
    if goal == "custom":
        goal = ask("Describe your goal")
    save_config_key("behaviour.goal", goal)

    # Approval mode
    approval = ask_choice(
        "Command approval mode",
        [
            ("warn",      "Warn on dangerous commands (recommended)"),
            ("allow-all", "Allow all commands without warning"),
            ("block",     "Block dangerous commands"),
        ],
        default="warn",
    )
    save_config_key("approvals.mode", approval)

    # Memory
    memory_on = ask_yn("Enable persistent memory (IMOS remembers past conversations)?", default=True)
    save_config_key("behaviour.memory_enabled", memory_on)

    # Auto-open browser
    auto_browser = ask_yn("Auto-open dashboard in browser on startup?", default=True)
    save_config_key("behaviour.auto_open_browser", auto_browser)


def setup_voice():
    header("6 / 9  —  Voice")
    print(clr("  IMOS can speak responses and listen for voice commands.", D))

    voice_on = ask_yn("Enable voice (TTS + wake word)?", default=True)
    write_env("IMOS_VOICE_ENABLED", "true" if voice_on else "false")
    save_config_key("voice.enabled", voice_on)

    if voice_on:
        voice_choices = [
            ("david", "DAVID (male, Windows default)"),
            ("zira",  "ZIRA (female, Windows)"),
        ]
        voice = ask_choice("Voice", voice_choices, default="david")
        save_config_key("voice.voice", voice)

        rate = ask("Speech rate (words per minute)", default="175")
        write_env("IMOS_VOICE_RATE", rate)
        save_config_key("voice.rate", int(rate))

        print(clr("  Wake word: 'IMOS' or 'Hey IMOS'", D))
        picovoice = ask("Picovoice API key for offline wake word (Enter to skip)", secret=True)
        if picovoice:
            write_env("PICOVOICE_KEY", picovoice)
            print(clr("  ✓ Picovoice configured", G))
        else:
            print(clr("  Using Google STT for wake word detection (requires internet)", D))


def setup_integrations():
    header("7 / 9  —  Integrations")
    print(clr("  Connect external services. All optional — add more later in the dashboard.", D))

    # Weather
    if ask_yn("\n  Add weather API key (open-meteo is free, no key needed)?", default=False):
        wk = ask("OpenWeather API key", secret=True)
        if wk:
            write_env("OPENWEATHER_API_KEY", wk)

    # News
    if ask_yn("  Add news API key (Google RSS is free, no key needed)?", default=False):
        nk = ask("NewsAPI key", secret=True)
        if nk:
            write_env("NEWS_API_KEY", nk)

    # Email
    if ask_yn("  Configure email (for send_email skill)?", default=False):
        write_env("EMAIL_FROM", ask("From email address"))
        write_env("EMAIL_SMTP_SERVER", ask("SMTP server", default="smtp.gmail.com"))
        write_env("EMAIL_SMTP_PORT", ask("SMTP port", default="587"))
        write_env("EMAIL_PASSWORD", ask("Email password / app password", secret=True))
        print(clr("  ✓ Email configured", G))


def setup_workflows():
    header("8 / 9  —  Workflows & Automations")
    print(clr("  IMOS can run automated workflows. Configure defaults here.", D))

    # Default project type
    proj_type = ask_choice(
        "Default project type when building apps",
        [
            ("nextjs",  "Next.js (full-stack, recommended)"),
            ("react",   "React / Vite (frontend)"),
            ("python",  "Python (scripts, APIs)"),
            ("any",     "Let IMOS decide"),
        ],
        default="nextjs",
    )
    save_config_key("workflows.default_project_type", proj_type)

    # Default DB
    db_type = ask_choice(
        "Default database for new projects",
        [
            ("sqlite",   "SQLite (local, no setup)"),
            ("postgres", "PostgreSQL"),
            ("mysql",    "MySQL"),
            ("mongodb",  "MongoDB"),
            ("none",     "No database"),
        ],
        default="sqlite",
    )
    save_config_key("workflows.default_db", db_type)

    # Auto-push to GitHub
    auto_push = ask_yn("Auto-push new projects to GitHub?", default=True)
    save_config_key("workflows.auto_github_push", auto_push)

    # Auto-deploy
    auto_deploy = ask_yn("Auto-deploy new projects after build?", default=False)
    save_config_key("workflows.auto_deploy", auto_deploy)


def setup_dashboard():
    header("9 / 9  —  Dashboard & Theme")
    print(clr("  Customise the IMOS dashboard appearance.", D))

    theme = ask_choice(
        "Colour theme",
        [
            ("orange", "Orange + Black (default)"),
            ("blue",   "Blue + Black"),
            ("green",  "Green + Black"),
            ("purple", "Purple + Black"),
            ("red",    "Red + Black"),
        ],
        default="orange",
    )
    write_env("IMOS_THEME", theme)
    save_config_key("dashboard.theme", theme)

    port = ask("Dashboard port", default="5000")
    save_config_key("dashboard.port", int(port))

    print(clr(f"  ✓ Dashboard: http://localhost:{port}", G))


def ensure_env_file():
    """Create .env from .env.example if it doesn't exist."""
    if not ENV_PATH.exists():
        if ENV_EXAMPLE.exists():
            shutil.copy(str(ENV_EXAMPLE), str(ENV_PATH))
            print(clr("  Created .env from .env.example", G))
        else:
            ENV_PATH.write_text("", encoding="utf-8")
            print(clr("  Created empty .env", G))


def is_first_run() -> bool:
    """Return True if IMOS has never been configured."""
    cfg_path = Path.home() / ".connectai" / "config.yaml"
    if not cfg_path.exists():
        return True
    try:
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return not cfg.get("model", {}).get("provider")
    except Exception:
        return True


def run_setup(force: bool = False):
    if not force and not is_first_run():
        return  # Already configured

    ensure_env_file()

    print()
    print(clr("╔══════════════════════════════════════════════════════════╗", O))
    print(clr("║          IMOS — First Time Setup Wizard                  ║", W))
    print(clr("║  This will configure your AI, GitHub, cloud, and more.   ║", D))
    print(clr("║  All secrets stay in .env — never committed to git.      ║", D))
    print(clr("╚══════════════════════════════════════════════════════════╝", O))
    print()
    print(clr("  Press Enter to accept defaults. Ctrl+C to skip any section.", D))

    sections = [
        ("AI Model",       setup_model),
        ("GitHub",         setup_github),
        ("Cloud Deploy",   setup_deployment),
        ("Workspace",      setup_workspace),
        ("Behaviour",      setup_behaviour),
        ("Voice",          setup_voice),
        ("Integrations",   setup_integrations),
        ("Workflows",      setup_workflows),
        ("Dashboard",      setup_dashboard),
    ]

    for name, fn in sections:
        try:
            fn()
        except KeyboardInterrupt:
            print(clr(f"\n  Skipped: {name}", Y))
        except Exception as e:
            print(clr(f"\n  Error in {name}: {e}", R))

    # Mark setup complete
    save_config_key("setup_complete", True)

    print()
    print(clr("╔══════════════════════════════════════════════════════════╗", O))
    print(clr("║                  Setup Complete!                         ║", G))
    print(clr("╚══════════════════════════════════════════════════════════╝", O))
    print()
    print(clr("  Start IMOS:  ", D) + clr("imos", O))
    print(clr("  Dashboard:   ", D) + clr("http://localhost:5000", W))
    print(clr("  Re-run setup:", D) + clr("launch IMOS, then use /setup", O))
    print()


if __name__ == "__main__":
    force = "--force" in sys.argv or "--setup" in sys.argv
    run_setup(force=force)
