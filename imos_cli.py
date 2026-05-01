"""
IMOS CLI — type 'imos' in terminal to start.
Usage:
  imos                  Start server + dashboard + interactive shell
  imos --setup          Run first-time setup wizard
  imos --shell          Interactive shell only
  imos --server         Server only (no shell)
  imos --help           Show help
  imos --version        Show version
  imos --status         Show system status
  imos --skills         List all skills
  imos --model          Show active model
  imos --setmodel       Change model interactively
"""
from __future__ import annotations

import os
import sys
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from imos.ui import get_cli_palette, get_ui_config, setup_terminal_io

VERSION = "1.0.0"

setup_terminal_io()
_palette = get_cli_palette()
O = _palette["O"]
W = _palette["W"]
G = _palette["G"]
R = _palette["R"]
D = _palette["D"]
X = _palette["X"]

def _banner_text(port: int) -> str:
    ui_cfg = get_ui_config()
    try:
        heading = f"""{O}
  ██╗███╗   ███╗ ██████╗ ███████╗
  ██║████╗ ████║██╔═══██╗██╔════╝
  ██║██╔████╔██║██║   ██║███████╗
  ██║██║╚██╔╝██║██║   ██║╚════██║
  ██║██║ ╚═╝ ██║╚██████╔╝███████║
  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚══════╝{X}"""
        heading.encode(sys.stdout.encoding or "utf-8", errors="strict")
    except Exception:
        heading = f"{O}IMOS{X}"
    return f"""{heading}
  {W}Intelligent Machine Operating System{X} {D}v{VERSION}{X}
  {D}Dashboard -> http://localhost:{port}{X}
  {D}Shell palette: {ui_cfg['shell_palette']}  Dashboard palette: {ui_cfg['dashboard_palette']}{X}
"""

HELP_TEXT = f"""
{O}IMOS - Intelligent Machine Operating System  v{VERSION}{X}

{W}Commands:{X}
  {O}imos{X}                   Ask what to start (shell or dashboard)
  {O}imos shell{X}             Interactive AI shell
  {O}imos dashboard{X}         Start server and open dashboard in browser
  {O}imos both{X}              Open dashboard and keep the shell in this terminal
  {O}imos server{X}            Start server only (no browser, no shell)
  {O}imos setup{X}             Run the setup wizard
  {O}imos status{X}            System status (model, CPU, RAM, GitHub...)
  {O}imos skills{X}            List all 38 loaded skills
  {O}imos model{X}             Show active AI model
  {O}imos setmodel{X}          Change AI model interactively
  {O}imos login{X}             Connect GitHub / cloud accounts
  {O}imos logout{X}            Disconnect / clear saved tokens
  {O}imos whoami{X}            Show current auth / account info
  {O}imos version{X}           Show version
  {O}imos help{X}              Show this help

{W}Flags (also work):{X}
  {O}--setup  --shell  --server  --dashboard{X}
  {O}--status  --skills  --model  --version  --help{X}

{W}Inside the shell — type / commands:{X}
  {O}/help{X}          All shell commands
  {O}/exit{X}          Quit
  {O}/clear{X}         Clear screen
  {O}/model{X}         Show model
  {O}/setmodel{X}      Change model
  {O}/skills{X}        List skills
  {O}/status{X}        System stats
  {O}/dashboard{X}     Open dashboard
  {O}/setup{X}         Re-run setup
  {O}/login{X}         Connect accounts
  {O}/logout{X}        Disconnect accounts
  {O}/whoami{X}        Show auth info
  {O}/github{X}        GitHub status
  {O}/deploy{X}        Deployment config
  {O}/workspace{X}     Workspace path
  {O}/voice on|off{X}  Toggle voice
  {O}/tasks{X}         Recent tasks
  {O}/audit{X}         Audit log
  {O}/history{X}       Command history

{W}Examples:{X}
  {D}${X} imos shell
  {D}${X} imos dashboard
  {D}${X} imos both
  {D}${X} imos setup
  {D}${X} imos login
  {D}imos>{X} clean my pc
  {D}imos>{X} build me a Next.js ecommerce app called ShopFlow
  {D}imos>{X} what is the weather in Islamabad?
  {D}imos>{X} open chrome and search for python tutorials
  {D}imos>{X} push my code to github
  {D}imos>{X} deploy to vercel
  {D}imos>{X} what is on my screen?
"""


def _show_status():
    _load_env()
    try:
        import psutil
        from config.config import get_model_config
        mc = get_model_config()
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\" if os.name == "nt" else "/")
        print(f"\n{O}IMOS Status{X}")
        print(f"  {D}Model:    {X}{mc.get('provider','?')}/{mc.get('model','?')}")
        print(f"  {D}CPU:      {X}{psutil.cpu_percent(interval=0.3):.0f}%")
        print(f"  {D}RAM:      {X}{vm.percent:.0f}% ({vm.used//(1024**3):.1f}/{vm.total//(1024**3):.1f} GB)")
        print(f"  {D}Disk:     {X}{disk.percent:.0f}%")
        print(f"  {D}Server:   {X}{'running' if not _check_port_free(5000) else 'stopped'} (port 5000)")
        gh = _read_env_key("GITHUB_TOKEN")
        print(f"  {D}GitHub:   {X}{'connected' if gh else 'not configured'}")
        vt = _read_env_key("VERCEL_TOKEN")
        print(f"  {D}Vercel:   {X}{'configured' if vt else 'not configured'}")
        nt = _read_env_key("NETLIFY_TOKEN")
        print(f"  {D}Netlify:  {X}{'configured' if nt else 'not configured'}")
        print()
    except Exception as e:
        print(f"{R}Status error: {e}{X}")


def _show_skills():
    _load_env()
    from connectai.skills import SkillRegistry
    from config.config import load_config
    ws = Path(load_config().get("workspace", str(Path.home() / "imos_workspace")))
    reg = SkillRegistry(workspace_root=ws, bundled_root=PROJECT_ROOT / "skills")
    skills = reg.load_all()
    print(f"\n{O}{len(skills)} skills loaded:{X}")
    for s in skills:
        print(f"  {O}·{X} {W}{s.name:<22}{X} {D}{s.description[:55]}{X}")
    print()


def _show_model():
    _load_env()
    from config.config import get_model_config
    mc = get_model_config()
    print(f"\n  {D}Provider:{X} {O}{mc.get('provider','?')}{X}")
    print(f"  {D}Model:   {X} {mc.get('model','?')}")
    print(f"  {D}Change:  {X} {D}imos setmodel{X}\n")


def _set_model_interactive():
    _load_env()
    from config.config import save_model_config
    providers = ["anthropic","groq","openai","openrouter","gemini","huggingface",
                 "ollama","azure","bedrock","nvidia","gcp"]
    print(f"\n{O}Change AI Model{X}")
    for i, p in enumerate(providers, 1):
        print(f"  {O}{i}.{X} {p}")
    raw = input(f"{O}  › {X}Provider number or name: ").strip()
    if raw.isdigit() and 1 <= int(raw) <= len(providers):
        provider = providers[int(raw)-1]
    elif raw in providers:
        provider = raw
    else:
        print(f"{R}  Invalid{X}"); return
    model = input(f"{O}  › {X}Model name: ").strip()
    if not model:
        print(f"{R}  Model name required{X}"); return
    import getpass
    api_key = getpass.getpass(f"{O}  › {X}API key (Enter to keep current): ").strip()
    cfg = {"provider": provider, "model": model}
    if api_key:
        cfg["api_key"] = api_key
    save_model_config(cfg)
    print(f"{G}  ✓ Model set to {provider}/{model}{X}\n")


def _check_port_free(port: int = 5000) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def _wait_for_server(port: int = 5000, timeout: int = 15) -> bool:
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                if s.connect_ex(("localhost", port)) == 0:
                    return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def _load_env():
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")


def _get_runtime():
    """Build and return the IMOS runtime + supporting objects."""
    _load_env()
    from config.config import get_model_config, load_config
    from connectai.memory import ConnectMemoryStore
    from connectai.ops import ApprovalPolicy, AuditLogger, CostTracker, ProcessRegistry, ShellRunner, TaskManager
    from connectai.sessions import ConnectSessionManager
    from connectai.skills import SkillRegistry
    from imos.runtime import IMOSRuntime

    workspace = Path(load_config().get("workspace", str(Path.home() / "imos_workspace")))
    workspace.mkdir(parents=True, exist_ok=True)
    logs = PROJECT_ROOT / "logs"
    logs.mkdir(exist_ok=True)

    audit = AuditLogger(logs)
    approval = ApprovalPolicy(load_config, audit)
    shell = ShellRunner(logs / "shell", audit, approval)
    processes = ProcessRegistry(logs / "processes", audit)
    tasks = TaskManager(logs / "tasks", audit)
    cost = CostTracker(logs / "cost")
    sessions = ConnectSessionManager(workspace / "sessions")
    memory = ConnectMemoryStore(workspace / "memory")
    skills = SkillRegistry(workspace_root=workspace, bundled_root=PROJECT_ROOT / "skills")

    runtime = IMOSRuntime(
        skill_registry=skills,
        memory_store=memory,
        shell_runner=shell,
        process_manager=processes,
        audit_logger=audit,
        task_manager=tasks,
        cost_tracker=cost,
    )
    return runtime, sessions, skills, workspace, get_model_config(), cost


def _cmd_login():
    """Open browser to IMOS sign-in, wait for completion, save session."""
    _load_env()
    from imos.auth import cmd_login
    cmd_login()


def _cmd_logout():
    """Sign out and clear the saved IMOS session."""
    _load_env()
    from imos.auth import cmd_logout
    cmd_logout()


def _cmd_whoami():
    """Show current IMOS account and connected services."""
    _load_env()
    from imos.auth import cmd_whoami_clerk
    cmd_whoami_clerk()

    # GitHub
    gh = _read_env_key("GITHUB_TOKEN")
    if gh:
        try:
            import requests
            r = requests.get("https://api.github.com/user",
                             headers={"Authorization": f"token {gh}"}, timeout=6)
            if r.status_code == 200:
                d = r.json()
                print(f"  {G}●{X} {W}GitHub{X}   {d.get('login','?')} ({d.get('name','')}) — {d.get('public_repos',0)} repos")
            else:
                print(f"  {R}●{X} {W}GitHub{X}   token invalid")
        except Exception:
            print(f"  {D}●{X} {W}GitHub{X}   token set (offline)")
    else:
        print(f"  {D}○{X} {W}GitHub{X}   not connected  {D}(imos setup){X}")

    vt = _read_env_key("VERCEL_TOKEN")
    print(f"  {'●' if vt else '○'} {W}Vercel{X}   {'configured' if vt else 'not set'}")

    nt = _read_env_key("NETLIFY_TOKEN")
    print(f"  {'●' if nt else '○'} {W}Netlify{X}  {'configured' if nt else 'not set'}")

    from config.config import get_model_config
    mc = get_model_config()
    key_set = bool(str(mc.get("api_key", "")).strip())
    print(f"  {G if key_set else D}●{X} {W}AI{X}       {mc.get('provider','?')}/{mc.get('model','?')} {'(key set)' if key_set else D+'(no key)'+X}")
    print()


def _read_env_key(key: str) -> str:
    """Read a key from .env file."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(key, "")


def _write_env_key(key: str, value: str):
    """Write a key to .env file."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        env_path.write_text("", encoding="utf-8")
    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{key}={value}")
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    if value:
        os.environ[key] = value


def _verify_token(service: str, env_key: str, token: str):
    """Try to verify a token. Returns username string or True/False."""
    try:
        import requests
        if service == "GitHub":
            r = requests.get("https://api.github.com/user",
                             headers={"Authorization": f"token {token}"}, timeout=6)
            if r.status_code == 200:
                return r.json().get("login", True)
        elif service == "Vercel":
            r = requests.get("https://api.vercel.com/v2/user",
                             headers={"Authorization": f"Bearer {token}"}, timeout=6)
            return r.status_code == 200
        elif service in ("Anthropic", "Groq", "OpenAI", "OpenRouter"):
            return True  # skip live test for AI keys
    except Exception:
        pass
    return False


def _start_server_background(port: int) -> bool:
    """Start the IMOS server in background. Returns True when ready."""
    subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "imos_server.py"), "--no-browser"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return _wait_for_server(port, timeout=14)


def _cmd_dashboard(port: int = 5000):
    """Start server if needed and open dashboard."""
    import webbrowser
    if not _check_port_free(port):
        print(f"{G}  Server already running → http://localhost:{port}{X}")
    else:
        print(f"{D}  Starting IMOS server...{X}", end="", flush=True)
        ok = _start_server_background(port)
        if ok:
            print(f"\r{G}  Server online → http://localhost:{port}          {X}")
        else:
            print(f"\r{D}  Server starting (may take a moment)...{X}")
    webbrowser.open(f"http://localhost:{port}")


def main():
    args = sys.argv[1:]

    # Normalise: treat "imos shell" same as "imos --shell" etc.
    # First positional arg (no leading --) is treated as a subcommand.
    subcommand = ""
    flags = []
    for a in args:
        if a.startswith("-"):
            flags.append(a.lstrip("-").lower())
        else:
            if not subcommand:
                subcommand = a.lower()
            else:
                flags.append(a.lower())

    # All recognised tokens in one place
    all_tokens = set(flags) | ({subcommand} if subcommand else set())

    # ── no-banner quick commands ──────────────────────────────────────────
    if "version" in all_tokens or "v" in all_tokens:
        print(f"IMOS v{VERSION}")
        return

    if "help" in all_tokens or "h" in all_tokens:
        print(HELP_TEXT)
        return

    if "status" in all_tokens:
        _show_status()
        return

    if "skills" in all_tokens:
        _show_skills()
        return

    if "model" in all_tokens and "setmodel" not in all_tokens:
        _show_model()
        return

    if "setmodel" in all_tokens:
        _set_model_interactive()
        return

    if "whoami" in all_tokens:
        _load_env()
        _cmd_whoami()
        return

    # ── banner ────────────────────────────────────────────────────────────
    from config.config import load_config
    port = load_config().get("dashboard", {}).get("port", 5000)
    print(_banner_text(port))
    _load_env()

    # ── authentication — required before anything else ────────────────────
    # Skip for: login, logout, whoami, setup, version, help, status
    auth_exempt = {"login", "logout", "whoami", "setup", "version", "help",
                   "status", "skills", "model", "setmodel", "v", "h"}
    if not all_tokens.intersection(auth_exempt):
        from imos.auth import require_auth
        authed = require_auth(skip_if_no_key=False)
        if not authed:
            print(f"{D}  Run {X}{O}imos login{X}{D} to sign in, then try again.{X}\n")
            return

    # ── first-time setup (auto on first run) ──────────────────────────────
    from imos_setup import is_first_run, run_setup, ensure_env_file
    ensure_env_file()
    if is_first_run() and "setup" not in all_tokens:
        print(f"{O}  Welcome to IMOS! Looks like this is your first run.{X}")
        print(f"{D}  Let's get you set up before we start.{X}\n")
        run_setup(force=True)
        _load_env()
        print()

    # ── explicit subcommands ──────────────────────────────────────────────
    if "setup" in all_tokens:
        run_setup(force=True)
        return

    if "login" in all_tokens:
        _cmd_login()
        return

    if "logout" in all_tokens:
        _cmd_logout()
        return

    # ── load port from config ─────────────────────────────────────────────
    from config.config import load_config
    port = load_config().get("dashboard", {}).get("port", 5000)

    if "dashboard" in all_tokens:
        _cmd_dashboard(port)
        return

    if "both" in all_tokens:
        if _check_port_free(port):
            print(f"\n{D}  Starting IMOS server...{X}", end="", flush=True)
            ok = _start_server_background(port)
            if ok:
                print(f"\r{G}  Server online -> http://localhost:{port}          {X}")
            else:
                print(f"\r{D}  Server starting...{X}")
        import webbrowser
        webbrowser.open(f"http://localhost:{port}")
        print(f"{G}  Dashboard opened in browser.{X}")
        print(f"{D}  Dropping into shell. Type {X}{O}/help{X}{D} for commands.{X}\n")
        _interactive_shell()
        return

    if "server" in all_tokens:
        from imos_server import startup, app
        startup(open_browser=False)
        app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
        return

    if "shell" in all_tokens or "s" in all_tokens:
        _interactive_shell()
        return

    # ── default: ask the user what they want ─────────────────────────────
    print(f"  {W}What would you like to do?{X}\n")
    print(f"  {O}1.{X} {W}Shell{X}      {D}Interactive AI shell in this terminal{X}")
    print(f"  {O}2.{X} {W}Dashboard{X}  {D}Open the web dashboard in your browser{X}")
    print(f"  {O}3.{X} {W}Both{X}       {D}Start server + open dashboard + drop into shell{X}")
    print(f"  {O}4.{X} {W}Setup{X}      {D}Re-run the setup wizard{X}")
    print(f"  {O}q.{X} {W}Quit{X}\n")

    try:
        choice = input(f"{O}  › {X}").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        return

    if choice in ("q", "quit", "exit", ""):
        return

    if choice in ("4", "setup"):
        run_setup(force=True)
        return

    open_dashboard = choice in ("2", "dashboard", "3", "both")
    open_shell = choice in ("1", "shell", "3", "both")

    if not open_dashboard and not open_shell:
        # Treat anything else as shell
        open_shell = True

    if open_dashboard or open_shell:
        # Start server in background (needed for both dashboard and shell API calls)
        if _check_port_free(port):
            print(f"\n{D}  Starting IMOS server...{X}", end="", flush=True)
            ok = _start_server_background(port)
            if ok:
                print(f"\r{G}  Server online → http://localhost:{port}          {X}")
            else:
                print(f"\r{D}  Server starting...{X}")

    if open_dashboard:
        import webbrowser
        webbrowser.open(f"http://localhost:{port}")
        print(f"{G}  Dashboard opened in browser.{X}")

    if open_shell:
        if open_dashboard:
            print(f"{D}  Dropping into shell. Type {X}{O}/help{X}{D} for commands.{X}\n")
        _interactive_shell()

def _show_skills():
    _load_env()
    from connectai.skills import SkillRegistry
    from config.config import load_config
    ws = Path(load_config().get("workspace", str(Path.home() / "imos_workspace")))
    reg = SkillRegistry(workspace_root=ws, bundled_root=PROJECT_ROOT / "skills")
    skills = reg.load_all()
    print(f"\n{O}{len(skills)} skills loaded:{X}")
    for s in skills:
        print(f"  {O}·{X} {W}{s.name:<22}{X} {D}{s.description[:55]}{X}")
    print()


def _show_model():
    _load_env()
    from config.config import get_model_config
    mc = get_model_config()
    print(f"\n  {D}Provider:{X} {mc.get('provider','?')}")
    print(f"  {D}Model:   {X} {mc.get('model','?')}")
    print(f"  {D}Change:  {X} imos --setmodel\n")


def _set_model_interactive():
    _load_env()
    from config.config import save_model_config
    providers = ["anthropic","groq","openai","openrouter","gemini","huggingface","ollama","azure","bedrock","nvidia","gcp"]
    print(f"\n{O}Change AI Model{X}")
    for i, p in enumerate(providers, 1):
        print(f"  {O}{i}.{X} {p}")
    raw = input(f"{O}  › {X}Provider number or name: ").strip()
    if raw.isdigit() and 1 <= int(raw) <= len(providers):
        provider = providers[int(raw)-1]
    elif raw in providers:
        provider = raw
    else:
        print(f"{R}Invalid{X}"); return
    model = input(f"{O}  › {X}Model name: ").strip()
    if not model:
        print(f"{R}Model name required{X}"); return
    import getpass
    api_key = getpass.getpass(f"{O}  › {X}API key (Enter to keep current): ").strip()
    cfg = {"provider": provider, "model": model}
    if api_key:
        cfg["api_key"] = api_key
    save_model_config(cfg)
    print(f"{G}  ✓ Model set to {provider}/{model}{X}\n")


def _handle_shell_builtin(cmd: str, runtime_ctx: dict) -> bool:
    """Handle /commands inside the shell. Returns True if handled."""
    sessions = runtime_ctx["sessions"]
    skills_reg = runtime_ctx["skills"]
    workspace = runtime_ctx["workspace"]
    model_config = runtime_ctx["model_config"]
    cost = runtime_ctx["cost"]

    raw = cmd.strip()
    low = raw.lower()
    builtin_names = {
        "exit", "quit", "clear", "help", "model", "setmodel", "skills",
        "status", "dashboard", "setup", "login", "logout", "whoami",
        "workspace", "github", "deploy", "memory", "tasks", "audit", "history",
    }
    if low.startswith("/"):
        canonical = low
    elif low in builtin_names or low.startswith("voice "):
        canonical = "/" + low
    else:
        canonical = low

    if canonical in ("/exit", "/quit"):
        print(f"\n{D}IMOS shutting down. Goodbye.{X}")
        sys.exit(0)

    if canonical == "/clear":
        os.system("cls" if os.name == "nt" else "clear")
        return True

    if canonical == "/help":
        print(HELP_TEXT)
        return True

    if canonical == "/model":
        print(f"\n  {D}Provider:{X} {model_config.get('provider','?')} / {model_config.get('model','?')}\n")
        return True

    if canonical == "/setmodel":
        _set_model_interactive()
        runtime_ctx["model_config"] = __import__("config.config", fromlist=["get_model_config"]).get_model_config()
        return True

    if canonical == "/skills":
        loaded = skills_reg.load_all()
        print(f"\n{O}  {len(loaded)} skills:{X} {', '.join(s.name for s in loaded)}\n")
        return True

    if canonical == "/status":
        _show_status()
        return True

    if canonical == "/dashboard":
        from config.config import load_config
        port = load_config().get("dashboard", {}).get("port", 5000)
        _cmd_dashboard(port)
        return True

    if canonical == "/setup":
        from imos_setup import run_setup
        run_setup(force=True)
        return True

    if canonical in ("/login",):
        from imos.auth import cmd_login
        cmd_login()
        return True

    if canonical in ("/logout",):
        from imos.auth import cmd_logout
        cmd_logout()
        return True

    if canonical in ("/whoami",):
        _cmd_whoami()
        return True

    if canonical == "/workspace":
        print(f"\n  {D}Workspace:{X} {workspace}\n")
        return True

    if canonical == "/github":
        _load_env()
        gh = os.environ.get("GITHUB_TOKEN", "")
        if gh:
            try:
                import requests
                r = requests.get("https://api.github.com/user",
                                 headers={"Authorization": f"token {gh}"}, timeout=5)
                if r.status_code == 200:
                    print(f"\n  {G}GitHub: connected as {r.json().get('login','?')}{X}\n")
                else:
                    print(f"\n  {R}GitHub: token invalid{X}\n")
            except Exception as e:
                print(f"\n  {R}GitHub: {e}{X}\n")
        else:
            print(f"\n  {R}GitHub: not configured. Run /setup{X}\n")
        return True

    if canonical == "/deploy":
        _load_env()
        vt = os.environ.get("VERCEL_TOKEN", "")
        nt = os.environ.get("NETLIFY_TOKEN", "")
        print(f"\n  {D}Vercel:{X}  {'configured' if vt else 'not set'}")
        print(f"  {D}Netlify:{X} {'configured' if nt else 'not set'}\n")
        return True

    if canonical.startswith("/voice"):
        parts = canonical.split()
        if len(parts) > 1 and parts[1] == "off":
            os.environ["IMOS_VOICE_ENABLED"] = "false"
            print(f"  {D}Voice disabled{X}")
        else:
            os.environ["IMOS_VOICE_ENABLED"] = "true"
            print(f"  {G}Voice enabled{X}")
        return True

    if canonical == "/memory":
        try:
            import requests
            r = requests.get("http://localhost:5000/api/memory", timeout=5)
            items = r.json().get("items", [])
            print(f"\n  {D}Memory entries:{X} {len(items)}\n")
        except Exception:
            print(f"\n  {D}Memory: server not running{X}\n")
        return True

    if canonical == "/tasks":
        try:
            import requests
            r = requests.get("http://localhost:5000/api/tasks", timeout=5)
            items = r.json().get("items", [])[:5]
            print(f"\n{O}  Recent tasks:{X}")
            for t in items:
                status_color = G if t.get("status") == "completed" else D
                print(f"  {status_color}·{X} {t.get('objective','')[:60]} [{t.get('status','')}]")
            print()
        except Exception:
            print(f"\n  {D}Tasks: server not running{X}\n")
        return True

    if canonical == "/audit":
        try:
            import requests
            r = requests.get("http://localhost:5000/api/audit?limit=10", timeout=5)
            items = r.json().get("items", [])
            print(f"\n{O}  Recent audit:{X}")
            for e in items[-8:]:
                print(f"  {D}{e.get('ts','')[:19]}{X} {O}{e.get('kind',''):<20}{X} {e.get('message','')[:50]}")
            print()
        except Exception:
            print(f"\n  {D}Audit: server not running{X}\n")
        return True

    if canonical == "/history":
        history = runtime_ctx.get("history", [])
        user_msgs = [m["content"] for m in history if m.get("role") == "user"]
        print(f"\n{O}  Command history:{X}")
        for i, m in enumerate(user_msgs[-10:], 1):
            print(f"  {D}{i:2}.{X} {m[:70]}")
        print()
        return True

    return False  # not a builtin


def _interactive_shell(runtime_ctx: dict = None):
    """Run the interactive IMOS shell."""
    if runtime_ctx is None:
        print(f"{D}  Loading IMOS runtime...{X}", flush=True)
        runtime, sessions, skills, workspace, model_config, cost = _get_runtime()
        session = sessions.get_or_create("cli-session", "cli", "operator", "IMOS CLI")
        history = []
        runtime_ctx = {
            "runtime": runtime,
            "sessions": sessions,
            "skills": skills,
            "workspace": workspace,
            "model_config": model_config,
            "cost": cost,
            "session": session,
            "history": history,
        }

    runtime = runtime_ctx["runtime"]
    sessions = runtime_ctx["sessions"]
    session = runtime_ctx["session"]
    workspace = runtime_ctx["workspace"]
    history = runtime_ctx["history"]

    model_config = runtime_ctx["model_config"]
    print(f"\n  {D}Provider:{X} {O}{model_config.get('provider','?')}{X}/{model_config.get('model','?')}")
    print(f"  {D}Workspace:{X} {workspace}")
    print(f"  {D}Type anything — natural language or shell commands.{X}")
    print(f"  {D}Type {X}{O}/help{X}{D} for all commands.{X}\n")

    while True:
        try:
            user_input = input(f"{O}imos>{X} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{D}IMOS shutting down. Goodbye.{X}")
            break

        if not user_input:
            continue

        if _handle_shell_builtin(user_input, runtime_ctx):
            continue

        # Stream response
        print(f"{D}IMOS:{X} ", end="", flush=True)
        full_response: list = []

        def on_token(token: str):
            print(token, end="", flush=True)
            full_response.append(token)

        try:
            # Reload model config in case it was changed
            model_config = runtime_ctx["model_config"]

            result = runtime.run(
                user_text=user_input,
                session_history=history,
                session_id=session.session_id,
                workspace=str(workspace),
                model_config=model_config,
                on_text_delta=on_token,
                return_meta=True,
            )
            if isinstance(result, dict):
                final = result.get("text", "".join(full_response))
                usage = result.get("usage", {})
            else:
                final = str(result)
                usage = {}

            if not full_response and final:
                print(final, end="")

            print()

            if usage.get("input_tokens") or usage.get("output_tokens"):
                inp = usage.get("input_tokens", 0)
                out = usage.get("output_tokens", 0)
                print(f"{D}  [{inp}→{out} tokens]{X}")

            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": final})
            if len(history) > 40:
                history[:] = history[-40:]

            try:
                sessions.append_message(session, "user", user_input)
                sessions.append_message(session, "assistant", final)
            except Exception:
                pass

        except KeyboardInterrupt:
            print(f"\n{D}[interrupted]{X}")
        except Exception as e:
            print(f"\n{R}Error: {e}{X}")


if __name__ == "__main__":
    main()
