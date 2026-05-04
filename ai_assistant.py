import os
import sys
import json
import shlex
import subprocess
import time
import webbrowser
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from urllib.parse import unquote
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from InquirerPy import get_style, inquirer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from rich.align import Align
from rich.panel import Panel
from rich.console import Console
from rich.text import Text
from rich.rule import Rule
from rich.columns import Columns
from rich import box
from rich.table import Table

from connectai.channels import ChannelAdapter
from connectai.command_router import CommandResult, CommandRouter
from connectai.gateway import ConnectAIGateway
from connectai.gitops import GitAutopilot
from connectai.memory import ConnectMemoryStore
from connectai.mcp_runtime import MCPRuntime, MCPServer
from connectai.ops import ApprovalPolicy, AuditLogger, CostTracker, ProcessRegistry, ShellRunner, TaskManager, TerminalSessionManager
from connectai.runtime import ConnectAIRuntime
from connectai.sessions import ConnectSessionManager
from connectai.skills import SkillRegistry
from connectai.workflows import WorkflowRegistry
from core.events import EventBus
from core.confirm import ConfirmationPolicy
from core.contacts import ContactBook
from core.listener import VoiceListenerService
from core.voice import VoiceManager
from core.router import RoutingRules
from core import model_manager
from dashboard.server import DashboardContext, DashboardService
from setup.autostart import autostart_status, disable_autostart, enable_autostart
from setup.consent import ConsentManager
from setup.wizard import ensure_first_run_setup, force_run_setup_wizard
from agents.orchestrator import run_orchestrator
from config.config import (
    get_model_config, load_config, save_config, save_model_config,
    list_providers, get_provider_defaults, is_configured, CONFIG_PATH,
    PROVIDER_DEFAULTS,
    resolve_runtime_state_root,
)

try:
    from colorama import init as colorama_init
except Exception:
    def colorama_init(*_args, **_kwargs):
        return None
from tools.agent_bridges import (
    chat_with_claude_code,
    chat_with_gemini,
    chat_with_openai,
    cursor_mcp_http_snippet,
    open_claude_code_interactive,
    open_cursor_workspace,
    open_ide_with_fallback,
    open_prompt_url,
    open_workspace_in_app,
    run_cli_agent,
    send_email_smtp,
    start_imos_mcp_server_http,
    start_imos_mcp_server_http_on,
)

console = Console(highlight=False)
colorama_init(autoreset=True)

ORANGE = "\033[38;5;208m"
WHITE = "\033[97m"
DIM = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
RICH_TAG_RE = re.compile(r"\[/?[^\]]+\]")

IMOS_LOGO = [
    "██╗███╗   ███╗ ██████╗ ███████╗",
    "██║████╗ ████║██╔═══██╗██╔════╝",
    "██║██╔████╔██║██║   ██║███████╗",
    "██║██║╚██╔╝██║██║   ██║╚════██║",
    "██║██║ ╚═╝ ██║╚██████╔╝███████║",
    "╚═╝╚═╝     ╚═╝ ╚═════╝ ╚══════╝",
]

HISTORY_PATH = Path.home() / ".imos" / "history"
_DASHBOARD_SERVICE: DashboardService | None = None
_LISTENER_SERVICE: VoiceListenerService | None = None
_VOICE_MANAGER: VoiceManager | None = None

PROVIDER_MODELS = {
    "anthropic": [
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
    ],
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-20b",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "o1",
        "o3-mini",
    ],
    "openrouter": [
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-2.0-flash-001",
    ],
    "gemini": [
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ],
    "huggingface": [
        "meta-llama/Llama-3.1-8B-Instruct:cerebras",
        "openai/gpt-oss-120b:fireworks-ai",
        "Qwen/Qwen2.5-Coder-32B-Instruct:nebius",
    ],
    "ollama": [
        "llama3",
        "llama3.1",
        "mistral",
        "codellama",
        "phi3",
        "gemma2",
        "qwen2",
    ],
    "azure": [
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-35-turbo",
    ],
    "bedrock": [
        "anthropic.claude-opus-4-5-20251101-v1:0",
        "anthropic.claude-sonnet-4-5-20251101-v1:0",
        "amazon.titan-text-express-v1",
    ],
    "nvidia": [
        "meta/llama-3.1-405b-instruct",
        "meta/llama-3.1-70b-instruct",
        "mistralai/mixtral-8x7b-instruct-v0.1",
    ],
    "gcp": [
        "claude-opus-4-5@20251101",
        "claude-sonnet-4-5@20251101",
    ],
}

PROVIDER_LABELS = {
    "anthropic": "Anthropic    Claude (Opus, Sonnet, Haiku)",
    "groq":      "Groq         Llama, GPT-OSS on Groq",
    "openai":    "OpenAI       GPT-4o, o1, o3",
    "openrouter":"OpenRouter   Unified multi-provider routing",
    "gemini":    "Google       Gemini 2.0 Flash, 1.5 Pro",
    "huggingface":"Hugging Face Inference Providers router",
    "ollama":    "Ollama       Local models (llama3, mistral)",
    "azure":     "Azure        Azure OpenAI Service",
    "bedrock":   "AWS          Bedrock (Claude, Titan)",
    "nvidia":    "NVIDIA       NIM (llama, mixtral)",
    "gcp":       "GCP          Vertex AI (Claude on Google Cloud)",
}

INQUIRER_STYLE = get_style({
    "questionmark":  "fg:#ff6b00 bold",
    "answermark":    "fg:#ff6b00 bold",
    "answer":        "fg:#ff6b00 bold",
    "input":         "fg:#ffffff",
    "question":      "fg:#ffffff bold",
    "instruction":   "fg:#555555",
    "long_instruction": "fg:#555555",
    "pointer":       "fg:#ff6b00 bold",
    "checkbox":      "fg:#ff6b00",
    "separator":     "fg:#333333",
    "skipped":       "fg:#555555",
    "validator":     "fg:#ff4444",
    "marker":        "fg:#ff6b00 bold",
    "fuzzy_prompt":  "fg:#ffffff",
    "fuzzy_info":    "fg:#555555",
    "fuzzy_border":  "fg:#333333",
    "fuzzy_match":   "fg:#ff6b00",
})

PROMPT_STYLE = Style.from_dict({
    "bottom-toolbar": "bg:#111111 fg:#555555",
    "prompt":         "fg:#ff6b00 bold",
})

WELCOME_ART = [
    "██╗███╗   ███╗ ██████╗ ███████╗",
    "██║████╗ ████║██╔═══██╗██╔════╝",
    "██║██╔████╔██║██║   ██║███████╗",
    "██║██║╚██╔╝██║██║   ██║╚════██║",
    "██║██║ ╚═╝ ██║╚██████╔╝███████║",
    "╚═╝╚═╝     ╚═╝ ╚═════╝ ╚══════╝",
]

HELP = """
  [bold bright_white]IMOS Shell Commands[/bold bright_white]

  [#ff6b00]/setup[/#ff6b00]                    re-run the setup wizard
  [#ff6b00]/status[/#ff6b00]                   show IMOS runtime status
  [#ff6b00]/history[/#ff6b00]                  show recent IMOS run history
  [#ff6b00]/adapters[/#ff6b00]                 show connected adapter registry
  [#ff6b00]/sessions[/#ff6b00]                 list local runtime sessions
  [#ff6b00]/session[/#ff6b00] [dim]new|list|resume|save|export[/dim]
  [#ff6b00]/tasks[/#ff6b00]                    list long-running task records
  [#ff6b00]/workflows[/#ff6b00]                list YAML workflows
  [#ff6b00]/runflow[/#ff6b00] [dim]<name>[/dim]              run a workflow by name
  [#ff6b00]/dashboard[/#ff6b00]                launch local dashboard
  [#ff6b00]/dashboard stop[/#ff6b00]           stop local dashboard
  [#ff6b00]/wake[/#ff6b00] [dim]status|start|stop|install|uninstall[/dim]
  [#ff6b00]/palette[/#ff6b00] [dim]list|set shell <name>|set dashboard <name>[/dim]
  [#ff6b00]/model[/#ff6b00]                    show current model config
  [#ff6b00]/provider[/#ff6b00]                 show active provider and model
  [#ff6b00]/models[/#ff6b00]                   list all providers and status
  [#ff6b00]/use[/#ff6b00] [dim]<provider>[/dim]             switch provider interactively
  [#ff6b00]/setmodel[/#ff6b00] [dim]<model>[/dim]           set a new model name for current provider
  [#ff6b00]/pickmodel[/#ff6b00]                pick any provider/model pair interactively
  [#ff6b00]/setkey[/#ff6b00] [dim]<provider> <key>[/dim]    set API key directly
  [#ff6b00]/settoken[/#ff6b00] [dim]<svc> <tok>[/dim]       set deploy token
  [#ff6b00]/mcp[/#ff6b00]                      list MCP servers and discovered tools
  [#ff6b00]/mcp[/#ff6b00] [dim]install[/dim]              install Cursor/Windsurf MCP config files
  [#ff6b00]/mcp[/#ff6b00] [dim]serve[/dim]                start IMOS MCP server on http://127.0.0.1:8767/mcp
  [#ff6b00]/claude-code[/#ff6b00] [dim]<prompt>[/dim]     send one task to Claude Code CLI
  [#ff6b00]/claude-code[/#ff6b00]            open Claude Code interactive shell
  [#ff6b00]/openai[/#ff6b00] [dim]<prompt>[/dim]          send one prompt directly to OpenAI
  [#ff6b00]/codex[/#ff6b00] [dim]<prompt>[/dim]           alias for /openai
  [#ff6b00]/cursor[/#ff6b00]                   open workspace in Cursor, start MCP on :8765, print config snippet
  [#ff6b00]/ide[/#ff6b00] [dim]<prompt>[/dim]             open the best available IDE, else open vibe coding tools in browser
  [#ff6b00]/vscode[/#ff6b00]                   open workspace in VS Code and print MCP setup note
  [#ff6b00]/windsurf[/#ff6b00] [dim]<prompt>[/dim]        send one task to Windsurf CLI, or open workspace with no prompt
  [#ff6b00]/aider[/#ff6b00] [dim]<prompt>[/dim]           send one task to aider CLI
  [#ff6b00]/continue[/#ff6b00] [dim]<prompt>[/dim]        send one task to Continue CLI
  [#ff6b00]/gemini[/#ff6b00] [dim]<prompt>[/dim]          send one prompt directly to Gemini
  [#ff6b00]/email[/#ff6b00] [dim]<to>|<subject>|<body>[/dim] send email through SMTP env vars
  [#ff6b00]/whatsapp[/#ff6b00] [dim]<contact>|<message>[/dim] best-effort desktop/web handoff
  [#ff6b00]/telegram[/#ff6b00] [dim]<contact>|<message>[/dim] best-effort desktop/web handoff
  [#ff6b00]/v0[/#ff6b00] [dim]<prompt>[/dim]              open v0.dev with the prompt
  [#ff6b00]/lovable[/#ff6b00] [dim]<prompt>[/dim]         open lovable.dev with the prompt
  [#ff6b00]/bolt[/#ff6b00] [dim]<prompt>[/dim]            open bolt.new with the prompt
  [#ff6b00]/doctor[/#ff6b00]                   run IMOS doctor report
  [#ff6b00]/route[/#ff6b00] [dim]set <type> <provider>|list[/dim]
  [#ff6b00]/contact[/#ff6b00] [dim]add <name> <number>|list|remove <name>[/dim]
  [#ff6b00]/listen[/#ff6b00] [dim]start|stop|status|wake "phrase"[/dim]
  [#ff6b00]/voice[/#ff6b00] [dim]set <voice_id>|test|off|on|status[/dim]
  [#ff6b00]/autostart[/#ff6b00] [dim]enable|disable|status[/dim]
  [#ff6b00]/terminal[/#ff6b00]                 list managed terminal sessions
  [#ff6b00]/processes[/#ff6b00]                list managed background processes
  [#ff6b00]/audit[/#ff6b00]                    show recent audit log entries
  [#ff6b00]/memory[/#ff6b00] [dim]<query>[/dim]              search local memory index
  [#ff6b00]/git[/#ff6b00] [dim]status|branch|commit|diff|log[/dim]
  [#ff6b00]/config[/#ff6b00] [dim]get <path>[/dim]           inspect YAML config
  [#ff6b00]/config[/#ff6b00] [dim]set <path> <json>[/dim]    update YAML config path
  [#ff6b00]/integrations[/#ff6b00]             show configured integration keys
  [#ff6b00]/workspace[/#ff6b00]                show workspace path
  [#ff6b00]/cd[/#ff6b00] [dim]<path>[/dim]                   change workspace
  [#ff6b00]/imos[/#ff6b00] [dim]<cli args>[/dim]             run any IMOS CLI command from this shell
  [#ff6b00]/login[/#ff6b00]                    run Clerk login flow
  [#ff6b00]/logout[/#ff6b00]                   clear Clerk session
  [#ff6b00]/clear[/#ff6b00]                    clear screen
  [#ff6b00]/help[/#ff6b00]                     show this
  [#ff6b00]/exit[/#ff6b00]                     quit

  [bold bright_white]IMOS CLI Commands[/bold bright_white]

  [#ff6b00]imos[/#ff6b00]                               start IMOS shell
  [#ff6b00]imos shell[/#ff6b00] [dim]--session main[/dim]        open a named shell session
  [#ff6b00]imos shell[/#ff6b00] [dim]--beast[/dim]                open shell with multi-adapter orchestration
  [#ff6b00]imos run[/#ff6b00] [dim]"<prompt>"[/dim]                run one orchestration task
  [#ff6b00]imos run[/#ff6b00] [dim]"<prompt>" --beast[/dim]        run across configured model and IDE adapters
  [#ff6b00]imos run[/#ff6b00] [dim]"<prompt>" --adapters a,b[/dim] target specific adapters
  [#ff6b00]imos dashboard[/#ff6b00]                     open IMOS dashboard
  [#ff6b00]imos adapters list[/#ff6b00]                 list adapters
  [#ff6b00]imos adapters add[/#ff6b00] [dim]<type> <name>[/dim]
  [#ff6b00]imos adapters test[/#ff6b00] [dim]<name>[/dim]
  [#ff6b00]imos adapters remove[/#ff6b00] [dim]<name>[/dim]
  [#ff6b00]imos sessions list[/#ff6b00]                 list runtime sessions
  [#ff6b00]imos sessions history[/#ff6b00] [dim]<id>[/dim]         show session transcript
  [#ff6b00]imos sessions status[/#ff6b00] [dim]<id>[/dim]          show session status
  [#ff6b00]imos sessions export[/#ff6b00] [dim]<id>[/dim]          export parent and worker session graph
  [#ff6b00]imos history[/#ff6b00]                       show recent history
  [#ff6b00]imos status[/#ff6b00]                        show runtime status
  [#ff6b00]imos mcp install[/#ff6b00]                   install editor bridge
  [#ff6b00]imos wake install[/#ff6b00]                  install wake listener
  [#ff6b00]imos wake status[/#ff6b00]                   show wake listener status
  [#ff6b00]imos palette set[/#ff6b00] [dim]--shell <name> --dashboard <name>[/dim]
"""


def _home_title():
    title = Text()
    safe_art = [
        "██╗███╗   ███╗ ██████╗ ███████╗",
        "██║████╗ ████║██╔═══██╗██╔════╝",
        "██║██╔████╔██║██║   ██║███████╗",
        "██║██║╚██╔╝██║██║   ██║╚════██║",
        "██║██║ ╚═╝ ██║╚██████╔╝███████║",
    ]
    for line in safe_art:
        title.append(line + "\n", style="bold #ff8c1a")
    return title


def render_home_screen(model_config, workspace):
    provider = model_config.get("provider", "?")
    model = model_config.get("model", "?")
    for line in IMOS_LOGO:
        print(f"{ORANGE}{line}{RESET}")
    print(f"{WHITE}Intelligent Machine Operating System  {DIM}v1.0.0{RESET}")
    print(f"{WHITE}Dashboard  http://localhost:8766{RESET}")
    print()
    print(f"{WHITE}Server already running on port 8766{RESET}")
    print(f"{WHITE}Type /help for all commands. Type /dashboard to open browser.{RESET}")
    print()
    print(f"{WHITE}Loading IMOS runtime...{RESET}")
    print()
    print(f"{WHITE}Provider:   {ORANGE}{provider}/{model}{RESET}")
    print(f"{WHITE}Workspace:  {ORANGE}{workspace}{RESET}")
    print(f"{WHITE}Type anything  natural language or shell commands.{RESET}")
    print(f"{WHITE}Type /help for all commands.{RESET}")
    print()


def _plain(text: object) -> str:
    value = str(text)
    value = ANSI_RE.sub("", value)
    value = RICH_TAG_RE.sub("", value)
    return (
        value.replace("â€”", "-")
        .replace("â–ˆ", "█")
        .replace("â•‘", "║")
        .replace("â•”", "╔")
        .replace("â•", "═")
        .replace("â•", "╝")
        .replace("â•š", "╚")
    )


def _orange(text: object) -> str:
    return f"{ORANGE}{_plain(text)}{RESET}"


def _white(text: object) -> str:
    return f"{WHITE}{_plain(text)}{RESET}"


def _dim(text: object) -> str:
    return f"{DIM}{_plain(text)}{RESET}"


def _imos_prompt() -> str:
    return f"{ORANGE}imos>{RESET} "


def _print_command_output(text: object) -> None:
    output = str(text).rstrip()
    if not output:
        return
    print(output)


def _print_assistant_output(text: object) -> None:
    output = _plain(text).rstrip()
    if not output:
        return
    lines = output.splitlines() or [output]
    print(f"{ORANGE}IMOS:{RESET} {WHITE}{lines[0]}{RESET}")
    for line in lines[1:]:
        print(f"{' ' * 6}{WHITE}{line}{RESET}")


def _help_output() -> str:
    sections = [
        (
            "RUNTIME",
            [
                ("imos", "Start server + dashboard + shell"),
                ("imos --setup", "Run first-time setup wizard"),
                ("imos --shell", "Interactive shell only"),
                ("imos --server", "Server only"),
                ("imos --status", "Show system status"),
            ],
        ),
        (
            "SESSIONS",
            [
                ("/session new <name>", "Create and switch to session"),
                ("/session list", "List all sessions"),
                ("/session resume <name>", "Resume a session"),
                ("/session save", "Save current session"),
                ("/session export <name>", "Export session to file"),
            ],
        ),
        (
            "ROUTING",
            [
                ("/route set <type> <provider>", "Set routing rule"),
                ("/route list", "Show all routing rules"),
            ],
        ),
        (
            "VOICE",
            [
                ("/listen start", "Start wake word listener"),
                ("/listen stop", "Stop listener"),
                ("/listen status", "Show listener status"),
                ("/voice test", "Speak test phrase"),
                ("/voice set <name>", "Change voice"),
                ("/voice off / on", "Mute toggle"),
            ],
        ),
        (
            "INTEGRATIONS",
            [
                ("/ide", "Open project in best available IDE"),
                ("/mcp serve", "Start MCP server"),
                ("/mcp install", "Write Cursor/Windsurf MCP config"),
                ("/claude-code <prompt>", "Send task to Claude Code CLI"),
                ("/codex <prompt>", "Send task to OpenAI"),
            ],
        ),
        (
            "CONTACTS",
            [
                ("/contact add <name> <number>", "Add contact"),
                ("/contact list", "List contacts"),
                ("/contact remove <name>", "Remove contact"),
            ],
        ),
        (
            "SYSTEM",
            [
                ("/dashboard", "Open dashboard in browser"),
                ("/dashboard stop", "Stop dashboard server"),
                ("/doctor", "Show full system health"),
                ("/autostart enable", "Enable Windows autostart"),
                ("/autostart disable", "Disable autostart"),
                ("/consent", "Re-show consent screen"),
            ],
        ),
        (
            "NATURAL LANGUAGE (no slash needed)",
            [
                ('open [app]', "Open any application"),
                ('message [contact] [text]', "Send WhatsApp message"),
                ('email [person] about [topic]', "Draft and send email"),
                ('create folder [name]', "Create folder"),
                ('screenshot', "Take screenshot"),
                ('shut down / restart', "System power commands"),
                ('build [project]', "Scaffold + open in IDE"),
                ('find clients in [niche]', "Prospect and outreach"),
            ],
        ),
    ]
    lines = [f"{ORANGE}IMOS  Intelligent Machine Operating System{RESET}", ""]
    for title, rows in sections:
        lines.append(f"{ORANGE}{title}{RESET}")
        for command, description in rows:
            lines.append(f"  {ORANGE}{command:<30}{RESET}  {WHITE}{description}{RESET}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _workspace_root_from_cfg(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    return Path(cfg.get("workspace", str(Path.home() / "imos_workspace")))


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


def _clerk_env() -> tuple[str, str]:
    publishable = os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "").strip()
    secret = os.getenv("CLERK_SECRET_KEY", "").strip()
    if publishable and secret:
        return publishable, secret

    candidates = [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT.parent / "connect frontend" / ".env",
    ]
    for candidate in candidates:
        if not publishable:
            publishable = _read_env_value(candidate, "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY") or publishable
        if not secret:
            secret = _read_env_value(candidate, "CLERK_SECRET_KEY") or secret
        if publishable and secret:
            break
    return publishable, secret


def _auth_manager_for_workspace(workspace: Path):
    from gateway_runtime.auth import ClerkAuthManager
    publishable, secret = _clerk_env()
    return ClerkAuthManager(workspace, publishable_key=publishable, enabled=bool(publishable), secret_key=secret)


def _dashboard_html(model_config: dict, workspace: Path, auth_info: dict, login_command: str) -> str:
    provider = model_config.get("provider", "not configured")
    model = model_config.get("model", "not configured")
    signed_in = "Signed in" if auth_info.get("signed_in") else "Signed out"
    user_label = auth_info.get("email") or auth_info.get("user_id") or "No active Clerk session"
    workspace_text = str(workspace).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>IMOS Dashboard</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm/css/xterm.css" />
  <script src="https://cdn.jsdelivr.net/npm/xterm/lib/xterm.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit/lib/xterm-addon-fit.js"></script>
  <style>
    :root {{
      --bg: #171717;
      --panel: #1d1d1d;
      --cyan: #7dd3fc;
      --salmon: #ff9b73;
      --muted: #a8b3bd;
      --border: rgba(255,155,115,0.88);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: #f6f6f6;
      font-family: Consolas, "Courier New", monospace;
      padding: 40px 32px 56px;
    }}
    .welcome {{
      display: inline-block;
      padding: 20px 34px;
      border: 2px solid var(--border);
      border-radius: 12px;
      color: #f8f8f8;
      font-size: clamp(22px, 2.4vw, 34px);
      margin-bottom: 26px;
      background: rgba(255,255,255,0.01);
      box-shadow: 0 0 0 1px rgba(255,155,115,0.15) inset;
    }}
    .welcome .mark {{ color: var(--salmon); margin-right: 14px; }}
    pre.hero {{
      margin: 0 0 24px;
      color: var(--cyan);
      font-size: clamp(13px, 1.42vw, 22px);
      line-height: 1.02;
      white-space: pre;
      overflow-x: auto;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      max-width: 1080px;
    }}
    .card {{
      border: 1px solid rgba(255,155,115,0.35);
      background: var(--panel);
      border-radius: 14px;
      padding: 18px 20px;
    }}
    .label {{ color: var(--muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.12em; }}
    .value {{ color: #f5f5f5; font-size: 22px; margin-top: 8px; word-break: break-word; }}
    .value.cyan {{ color: var(--cyan); }}
    .actions {{ margin-top: 28px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }}
    .button {{
      color: #111;
      background: var(--salmon);
      padding: 12px 16px;
      border-radius: 999px;
      font-weight: 700;
      border: none;
      font-family: inherit;
      cursor: pointer;
    }}
    .footer {{ margin-top: 24px; color: var(--muted); font-size: 14px; }}
    .footer code {{ color: var(--cyan); }}
  </style>
</head>
<body>
  <div class="welcome"><span class="mark">*</span>Welcome to <strong>IMOS</strong></div>
  <pre class="hero">{chr(10).join(WELCOME_ART)}</pre>
  <div class="grid">
    <section class="card">
      <div class="label">Provider</div>
      <div class="value cyan">{provider}</div>
    </section>
    <section class="card">
      <div class="label">Model</div>
      <div class="value">{model}</div>
    </section>
    <section class="card">
      <div class="label">Workspace</div>
      <div class="value">{workspace_text}</div>
    </section>
    <section class="card">
      <div class="label">Clerk Session</div>
      <div class="value">{signed_in}</div>
      <div class="footer">{user_label}</div>
    </section>
  </div>
  <div class="actions">
    <button class="button" onclick="navigator.clipboard.writeText('{login_command}')">Copy connect login</button>
    <span class="footer">Then run <code>{login_command}</code> in your terminal.</span>
  </div>
  <div class="footer">Dashboard is running locally. Use <code>connect logout</code> to clear the Clerk session.</div>
</body>
</html>"""


def _dashboard_app_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>IMOS Dashboard</title>
  <style>
    :root {
      --bg: #111111;
      --panel: #181818;
      --panel-2: #1f1f1f;
      --border: rgba(255, 155, 115, 0.28);
      --accent: #ff9b73;
      --cyan: #8ed8ff;
      --text: #f6f6f6;
      --muted: #9ca3af;
      --green: #8df0b3;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: radial-gradient(circle at top left, rgba(255,155,115,0.08), transparent 28%), var(--bg);
      color: var(--text);
      font-family: Consolas, "SFMono-Regular", "Cascadia Code", monospace;
      overflow-x: hidden;
    }
    .layout {
      display: grid;
      grid-template-columns: 290px minmax(0, 1fr) 360px;
      grid-template-areas: "sidebar main rightbar";
      min-height: 100vh;
      align-items: stretch;
    }
    .sidebar, .rightbar {
      background: var(--panel);
      padding: 22px 18px;
      min-width: 0;
      overflow-y: auto;
    }
    .sidebar {
      grid-area: sidebar;
      border-right: 1px solid var(--border);
    }
    .rightbar {
      grid-area: rightbar;
      border-left: 1px solid var(--border);
    }
    .main {
      grid-area: main;
      padding: 24px;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      gap: 16px;
      min-width: 0;
      min-height: 100vh;
    }
    .eyebrow {
      color: var(--accent);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      margin-bottom: 12px;
    }
    .brand {
      border: 2px solid rgba(255,155,115,0.7);
      border-radius: 12px;
      padding: 14px 18px;
      display: inline-block;
      margin-bottom: 18px;
      max-width: 100%;
    }
    .brand strong { color: var(--cyan); }
    .hero {
      white-space: pre;
      color: var(--cyan);
      font-size: 11px;
      line-height: 1.05;
      overflow-x: auto;
      margin: 0 0 18px;
    }
    .stack {
      display: grid;
      gap: 14px;
      min-width: 0;
    }
    .panel {
      background: var(--panel-2);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      min-width: 0;
    }
    .panel h3 {
      margin: 0 0 10px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      color: var(--muted);
    }
    .metric {
      font-size: 22px;
      color: var(--cyan);
      word-break: break-word;
    }
    .row {
      display: flex;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      min-width: 0;
    }
    .list {
      display: grid;
      gap: 8px;
      max-height: 260px;
      overflow: auto;
      min-width: 0;
    }
    .item {
      border: 1px solid rgba(255,255,255,0.06);
      border-radius: 12px;
      padding: 10px 12px;
      background: rgba(255,255,255,0.02);
      min-width: 0;
    }
    .item button {
      all: unset;
      cursor: pointer;
      display: block;
      width: 100%;
    }
    .item .title {
      color: var(--text);
      font-size: 14px;
      word-break: break-word;
    }
    .item .meta {
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
      word-break: break-word;
    }
    .chat-log {
      background: #101010;
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      overflow: auto;
      min-height: clamp(320px, 50vh, 720px);
      max-height: calc(100vh - 250px);
      min-width: 0;
    }
    .bubble {
      padding: 12px 14px;
      border-radius: 14px;
      margin-bottom: 12px;
      line-height: 1.55;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .user { background: rgba(255,155,115,0.12); border: 1px solid rgba(255,155,115,0.2); }
    .assistant { background: rgba(142,216,255,0.08); border: 1px solid rgba(142,216,255,0.18); }
    .composer {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 140px;
      gap: 12px;
      align-items: end;
      min-width: 0;
    }
    textarea, select, input {
      width: 100%;
      background: #0f0f0f;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px 14px;
      font: inherit;
    }
    textarea { min-height: 88px; resize: vertical; }
    button.cta {
      border: none;
      border-radius: 14px;
      padding: 14px 18px;
      background: var(--accent);
      color: #111;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }
    .pill {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.08);
      font-size: 12px;
      color: var(--green);
    }
    .muted { color: var(--muted); }
    .mono {
      font-family: inherit;
      word-break: break-word;
    }
    @media (max-width: 1200px) {
      .layout {
        grid-template-columns: 260px minmax(0, 1fr);
        grid-template-areas:
          "sidebar main"
          "rightbar rightbar";
      }
      .rightbar {
        border-left: none;
        border-top: 1px solid var(--border);
      }
      .rightbar .stack {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        align-items: start;
      }
    }
    @media (max-width: 900px) {
      .layout {
        grid-template-columns: 1fr;
        grid-template-areas:
          "sidebar"
          "main"
          "rightbar";
      }
      .sidebar,
      .rightbar {
        border-right: none;
        border-left: none;
        border-bottom: 1px solid var(--border);
        overflow: visible;
      }
      .main {
        padding: 18px;
        min-height: auto;
      }
      .chat-log {
        min-height: 45vh;
        max-height: none;
      }
      .composer {
        grid-template-columns: 1fr;
      }
      button.cta {
        width: 100%;
      }
      .rightbar .stack {
        grid-template-columns: 1fr;
      }
      .hero {
        font-size: 9px;
      }
    }
    @media (max-width: 640px) {
      .sidebar,
      .rightbar,
      .main {
        padding: 14px;
      }
      .panel {
        padding: 14px;
        border-radius: 14px;
      }
      .brand {
        width: 100%;
        margin-bottom: 14px;
      }
      .hero {
        font-size: 7px;
        line-height: 1.15;
      }
      .row {
        align-items: flex-start;
        flex-direction: column;
      }
    }
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">* Welcome to <strong>IMOS</strong></div>
      <pre class="hero">   _________  _   _ _   _ _   _ ______ _____ _______     ___  _____ 
  / ____/ _ \\| \\ | | \\ | | \\ | |  ____/ ____|__   __|   / _ \\|_   _|
 | |   | | | |  \\| |  \\| |  \\| | |__ | |       | |     / /_\\ \\ | |  
 | |   | | | | . ` | . ` | . ` |  __|| |       | |     |  _  | | |  
 | |___| |_| | |\\  | |\\  | |\\  | |___| |____    | |     | | | |_| |_ 
  \\_____\\___/|_| \\_|_| \\_|_| \\_|______\\_____|   |_|     \\_| |_/_____|</pre>
      <div class="stack">
        <section class="panel">
          <h3>Runtime</h3>
          <div class="row"><span class="muted">Provider</span><span id="provider" class="metric">...</span></div>
          <div class="row"><span class="muted">Model</span><span id="model" class="muted mono">...</span></div>
          <div class="row"><span class="muted">Auth</span><span id="auth" class="pill">...</span></div>
        </section>
        <section class="panel">
          <h3>Sessions</h3>
          <div id="sessions" class="list"></div>
        </section>
        <section class="panel">
          <h3>Workflows</h3>
          <div id="workflows" class="list"></div>
        </section>
        <section class="panel">
          <h3>Tasks</h3>
          <div id="tasks" class="list"></div>
        </section>
        <section class="panel">
          <h3>MCP</h3>
          <div id="mcpTools" class="list"></div>
        </section>
      </div>
    </aside>

    <main class="main">
      <section class="panel">
        <div class="row">
          <div>
            <div class="eyebrow">Operator Chat</div>
            <div class="muted">Chat with the live local runtime. Sessions, memory, skills, and workflows all route through this panel.</div>
          </div>
          <div class="muted" id="workspace">...</div>
        </div>
      </section>
      <section class="chat-log" id="chatLog"></section>
      <section class="panel">
        <div class="composer">
          <div class="stack">
            <select id="sessionSelect"></select>
            <textarea id="promptBox" placeholder="Ask the runtime to build, inspect, automate, deploy, or run a workflow..."></textarea>
          </div>
          <button class="cta" id="sendBtn">Send</button>
        </div>
      </section>
      <section class="panel">
        <div class="row">
          <div>
            <div class="eyebrow">Terminal</div>
            <div class="muted">Interactive shell session for the current workspace.</div>
          </div>
          <button class="cta" onclick="openTerminal()">Open terminal</button>
        </div>
        <div id="terminalPane" style="height:280px; background:#0b0b0b; border-radius:12px; margin-top:12px;"></div>
      </section>
    </main>

    <aside class="rightbar">
      <div class="stack">
        <section class="panel">
          <h3>Installed Skills</h3>
          <div id="skills" class="list"></div>
        </section>
        <section class="panel">
          <h3>Model Settings</h3>
          <div class="stack">
            <div class="item">
              <div class="title" id="tokenCount">0 tokens</div>
              <div class="meta" id="costUsd">$0.0000 this session</div>
            </div>
            <select id="providerSelect"></select>
            <input id="modelInput" placeholder="Model name" />
            <button class="cta" onclick="saveModelSettings()">Save model</button>
          </div>
        </section>
        <section class="panel">
          <h3>Integrations</h3>
          <div id="integrations" class="list"></div>
        </section>
        <section class="panel">
          <h3>Memory</h3>
          <div id="memory" class="list"></div>
        </section>
        <section class="panel">
          <h3>Processes</h3>
          <div id="processes" class="list"></div>
        </section>
        <section class="panel">
          <h3>Terminal Sessions</h3>
          <div id="terminals" class="list"></div>
        </section>
        <section class="panel">
          <h3>Audit</h3>
          <div id="audit" class="list"></div>
        </section>
        <section class="panel">
          <h3>Actions</h3>
          <div class="stack">
            <button class="cta" onclick="window.location.reload()">Refresh Dashboard</button>
            <button class="cta" onclick="navigator.clipboard.writeText('connect login')">Copy connect login</button>
          </div>
        </section>
        <section class="panel">
          <h3>Live Activity</h3>
          <div id="liveFeed" class="list"></div>
        </section>
      </div>
    </aside>
  </div>
  <script>
    let activeSessionId = '';
    let auditStream = null;
    let currentChatAbort = null;
    let terminalSessionId = '';
    let terminal = null;
    let terminalPoll = null;

    function bubble(role, content) {
      const div = document.createElement('div');
      div.className = 'bubble ' + role;
      div.textContent = content;
      return div;
    }

    async function loadJson(path, options = {}) {
      const res = await fetch(path, options);
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    }

    async function loadStatus() {
      const data = await loadJson('/api/status');
      document.getElementById('provider').textContent = data.provider || 'n/a';
      document.getElementById('model').textContent = data.model || 'n/a';
      document.getElementById('workspace').textContent = data.workspace || '';
      document.getElementById('auth').textContent = data.auth?.signed_in ? 'signed in' : 'signed out';
      const providerSelect = document.getElementById('providerSelect');
      providerSelect.innerHTML = '';
      for (const name of data.providers || []) {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        if (name === data.provider) option.selected = true;
        providerSelect.appendChild(option);
      }
      document.getElementById('modelInput').value = data.model || '';
    }

    async function loadCost() {
      const data = await loadJson('/api/cost');
      document.getElementById('tokenCount').textContent = (data.session_total_tokens || 0).toLocaleString() + ' tokens';
      document.getElementById('costUsd').textContent = '$' + Number(data.session_cost_usd || 0).toFixed(4) + ' this session';
    }

    async function loadSkills() {
      const data = await loadJson('/api/skills');
      const root = document.getElementById('skills');
      root.innerHTML = '';
      for (const item of data.items || []) {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = '<div class="title">' + item.name + '</div><div class="meta">' + item.source + ' - ' + item.description + '</div>';
        root.appendChild(div);
      }
    }

    async function loadWorkflows() {
      const data = await loadJson('/api/workflows');
      const root = document.getElementById('workflows');
      root.innerHTML = '';
      for (const item of data.items || []) {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = '<button onclick="runWorkflow(\\'' + item.name + '\\')"><div class="title">' + item.name + '</div><div class="meta">' + item.steps + ' steps</div></button>';
        root.appendChild(div);
      }
    }

    async function loadSessions() {
      const data = await loadJson('/api/sessions');
      const root = document.getElementById('sessions');
      const select = document.getElementById('sessionSelect');
      root.innerHTML = '';
      select.innerHTML = '';
      const items = data.items || [];
      if (!items.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'Default session';
        select.appendChild(option);
        activeSessionId = '';
        return;
      }
      for (const item of items) {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = '<button onclick="selectSession(\\'' + item.session_id + '\\')"><div class="title">' + item.title + '</div><div class="meta">' + item.channel + ' - ' + item.message_count + ' messages</div></button>';
        root.appendChild(div);

        const option = document.createElement('option');
        option.value = item.session_id;
        option.textContent = item.title + ' (' + item.message_count + ')';
        select.appendChild(option);
      }
      if (!activeSessionId && items[0]) activeSessionId = items[0].session_id;
      select.value = activeSessionId;
      await loadTranscript(activeSessionId);
    }

    async function loadTranscript(sessionId) {
      activeSessionId = sessionId || '';
      const log = document.getElementById('chatLog');
      log.innerHTML = '';
      const data = await loadJson('/api/sessions/' + encodeURIComponent(activeSessionId || 'default'));
      for (const item of data.items || []) {
        log.appendChild(bubble(item.role === 'user' ? 'user' : 'assistant', item.content));
      }
      log.scrollTop = log.scrollHeight;
    }

    async function loadMemory() {
      const data = await loadJson('/api/memory');
      const root = document.getElementById('memory');
      root.innerHTML = '';
      for (const item of data.items || []) {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = '<div class="title">' + item.kind + '</div><div class="meta">' + item.content + '</div>';
        root.appendChild(div);
      }
    }

    async function loadTasks() {
      const data = await loadJson('/api/tasks');
      const root = document.getElementById('tasks');
      root.innerHTML = '';
      for (const item of data.items || []) {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = '<div class="title">[' + item.status + '] ' + item.objective + '</div><div class="meta">' + item.task_id + ' - attempts=' + item.attempts + '</div>';
        root.appendChild(div);
      }
    }

    async function loadMcp() {
      const data = await loadJson('/api/mcp');
      const root = document.getElementById('mcpTools');
      root.innerHTML = '';
      for (const item of data.tools || []) {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = '<div class="title">' + item.name + '</div><div class="meta">' + item.server + ' - ' + item.description + '</div>';
        root.appendChild(div);
      }
      if (!root.childElementCount) {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = '<div class="title">No MCP tools</div><div class="meta">Register a server through the config or API.</div>';
        root.appendChild(div);
      }
    }

    async function loadProcesses() {
      const data = await loadJson('/api/processes');
      const root = document.getElementById('processes');
      root.innerHTML = '';
      for (const item of data.items || []) {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = '<div class="title">[' + item.status + '] ' + item.command + '</div><div class="meta">' + item.process_id + ' - pid=' + item.pid + '<br>' + (item.log_tail || '').replace(/</g, '&lt;') + '</div>';
        root.appendChild(div);
      }
    }

    async function loadTerminals() {
      const data = await loadJson('/api/terminals');
      const root = document.getElementById('terminals');
      root.innerHTML = '';
      for (const item of data.items || []) {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = '<div class="title">' + item.session_id + '</div><div class="meta">pid=' + item.pid + ' - ' + item.cwd + '</div>';
        root.appendChild(div);
      }
    }

    async function loadAudit() {
      const data = await loadJson('/api/audit');
      const root = document.getElementById('audit');
      root.innerHTML = '';
      for (const item of (data.items || []).slice(-12).reverse()) {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = '<div class="title">' + item.kind + '</div><div class="meta">' + item.message + '</div>';
        root.appendChild(div);
      }
    }

    function connectAuditStream() {
      if (auditStream) {
        auditStream.close();
      }
      const root = document.getElementById('liveFeed');
      root.innerHTML = '';
      auditStream = new EventSource('/api/stream');
      auditStream.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = '<div class="title">' + payload.kind + '</div><div class="meta">' + payload.message + '</div>';
        root.prepend(div);
        while (root.childElementCount > 20) {
          root.removeChild(root.lastChild);
        }
      };
      auditStream.onerror = () => {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = '<div class="title">stream</div><div class="meta">Live stream disconnected. Refresh to reconnect.</div>';
        root.prepend(div);
        auditStream.close();
      };
    }

    async function loadIntegrations() {
      const data = await loadJson('/api/integrations');
      const root = document.getElementById('integrations');
      root.innerHTML = '';
      const groups = [
        ['tokens', data.tokens || {}],
        ['messaging', data.messaging || {}],
      ];
      for (const [label, payload] of groups) {
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = '<div class="title">' + label + '</div><div class="meta">' + JSON.stringify(payload) + '</div>';
        root.appendChild(div);
      }
      const auth = document.createElement('div');
      auth.className = 'item';
      auth.innerHTML = '<div class="title">clerk</div><div class="meta">publishable=' + data.clerk_publishable_key + ' - secret=' + data.clerk_secret_key + '</div>';
      root.appendChild(auth);
    }

    async function saveModelSettings() {
      const provider = document.getElementById('providerSelect').value;
      const model = document.getElementById('modelInput').value.trim();
      if (!provider || !model) return;
      await loadJson('/api/model', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({provider, model})
      });
      await loadStatus();
      alert('Model settings updated.');
    }

    async function sendChat() {
      const text = document.getElementById('promptBox').value.trim();
      if (!text) return;
      const log = document.getElementById('chatLog');
      log.appendChild(bubble('user', text));
      document.getElementById('promptBox').value = '';
      const assistantBubble = bubble('assistant', '');
      log.appendChild(assistantBubble);
      log.scrollTop = log.scrollHeight;
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text, session_id: activeSessionId})
      });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let data = { session_id: activeSessionId, response: '', usage: {} };
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        const parts = buffer.split('\\n\\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          const line = part.split('\\n').find((entry) => entry.startsWith('data: '));
          if (!line) continue;
          const event = JSON.parse(line.slice(6));
          if (event.type === 'token') {
            assistantBubble.textContent += event.text;
            log.scrollTop = log.scrollHeight;
          } else if (event.type === 'done') {
            data = event;
            if (!assistantBubble.textContent && event.response) {
              assistantBubble.textContent = event.response;
            }
          } else if (event.type === 'error') {
            assistantBubble.textContent = event.error || 'Streaming error.';
          }
        }
      }
      await loadSessions();
      await loadTranscript(data.session_id || activeSessionId);
      await Promise.all([loadMemory(), loadTasks(), loadProcesses(), loadTerminals(), loadAudit(), loadCost()]);
    }

    async function runWorkflow(name) {
      await loadJson('/api/workflows/run', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name})
      });
      await Promise.all([loadMemory(), loadTasks(), loadProcesses(), loadTerminals(), loadAudit()]);
      alert('Workflow completed: ' + name);
    }

    function ensureTerminal() {
      if (terminal) return terminal;
      if (window.Terminal) {
        terminal = new Terminal({ cursorBlink: true, theme: { background: '#0b0b0b', foreground: '#f6f6f6' } });
        const fitAddon = window.FitAddon ? new FitAddon.FitAddon() : null;
        if (fitAddon) terminal.loadAddon(fitAddon);
        terminal.open(document.getElementById('terminalPane'));
        if (fitAddon) fitAddon.fit();
        terminal.onData((data) => {
          if (!terminalSessionId) return;
          fetch('/api/terminal/write', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_id: terminalSessionId, data})
          });
        });
      } else {
        const pane = document.getElementById('terminalPane');
        pane.innerHTML = '<pre id="terminalFallback" style="white-space:pre-wrap; margin:0; padding:12px; color:#f6f6f6;"></pre>';
        terminal = {
          write(text) { document.getElementById('terminalFallback').textContent += text; }
        };
      }
      return terminal;
    }

    async function openTerminal() {
      const data = await loadJson('/api/terminal/open', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({})
      });
      if (!data.ok) return;
      terminalSessionId = data.session_id;
      ensureTerminal();
      terminal.write('Connected to terminal session ' + terminalSessionId + '\\r\\n');
      if (terminalPoll) clearInterval(terminalPoll);
      terminalPoll = setInterval(async () => {
        if (!terminalSessionId) return;
        const chunk = await loadJson('/api/terminal/read', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({session_id: terminalSessionId})
        });
        if (chunk.ok && chunk.output) {
          terminal.write(chunk.output.replace(/\\n/g, '\\r\\n'));
        }
      }, 500);
      await loadTerminals();
    }

    async function selectSession(sessionId) {
      document.getElementById('sessionSelect').value = sessionId;
      await loadTranscript(sessionId);
    }

    document.getElementById('sendBtn').addEventListener('click', sendChat);
    document.getElementById('promptBox').addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendChat();
      }
    });
    document.getElementById('sessionSelect').addEventListener('change', (event) => loadTranscript(event.target.value));
    Promise.all([loadStatus(), loadSkills(), loadWorkflows(), loadSessions(), loadMemory(), loadTasks(), loadProcesses(), loadTerminals(), loadMcp(), loadAudit(), loadIntegrations(), loadCost()]).then(() => {
      connectAuditStream();
    }).catch((error) => {
      document.getElementById('chatLog').appendChild(bubble('assistant', 'Dashboard error: ' + error.message));
    });
  </script>
</body>
</html>"""


def _jarvis_dashboard_html() -> str:
    return (PROJECT_ROOT / "dashboard" / "jarvis_dashboard.html").read_text(encoding="utf-8")


def launch_dashboard():
    global _DASHBOARD_SERVICE
    if _DASHBOARD_SERVICE is None:
        raise RuntimeError("Dashboard service is not initialized.")
    url = _DASHBOARD_SERVICE.start(open_browser=True)
    console.print(f"  [#ff9b73]Opened IMOS dashboard[/#ff9b73] [dim]{url}/[/dim]")


def run_login():
    workspace = _workspace_root_from_cfg()
    auth = _auth_manager_for_workspace(workspace)
    ok, message = auth.start_cli_login()
    if ok:
        console.print(f"  [green]{message}[/green]")
    else:
        console.print(f"  [red]{message}[/red]")


def run_logout():
    workspace = _workspace_root_from_cfg()
    auth = _auth_manager_for_workspace(workspace)
    auth.clear_state()
    console.print("  [green]Signed out locally.[/green]")


def auth_is_mandatory(workspace: Path) -> bool:
    auth = _auth_manager_for_workspace(workspace)
    if auth.is_configured():
        return True
    return False


def ensure_authenticated(workspace: Path) -> bool:
    auth = _auth_manager_for_workspace(workspace)
    if not auth_is_mandatory(workspace):
        return True
    if auth.is_signed_in():
        return True
    console.print("  [yellow]Authentication required. Opening the Clerk sign-in flow...[/yellow]")
    ok, message = auth.start_cli_login()
    if ok:
        console.print(f"  [green]{message}[/green]")
        return True
    console.print(f"  [red]{message}[/red]")
    return False


class CLIChannel(ChannelAdapter):
    name = "cli"


def _mask_secret(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    if len(clean) <= 8:
        return "*" * len(clean)
    return f"{clean[:4]}{'*' * max(4, len(clean) - 8)}{clean[-4:]}"


def _provider_to_model_config(provider: dict) -> dict:
    payload = dict(provider)
    payload["provider"] = provider.get("type", provider.get("provider", ""))
    return payload


def _save_provider(provider: str, preserve_model: bool = False) -> dict:
    defaults = get_provider_defaults(provider)
    existing = model_manager.get_default() if preserve_model else None
    payload = dict(defaults)
    if existing is not None:
        payload.update({"api_key": existing.get("api_key", ""), "base_url": existing.get("base_url", ""), "model": existing.get("model", payload.get("model", ""))})
    payload["id"] = defaults.get("id", provider)
    payload["name"] = defaults.get("name", provider.title())
    payload["type"] = defaults.get("type", provider)
    payload["is_default"] = True
    payload["enabled"] = True
    model_manager.add_provider(payload)
    return get_model_config()


def _save_model_name(model_name: str) -> dict:
    current = model_manager.get_default()
    if current is None:
        cfg = get_model_config()
        cfg["model"] = model_name
        save_model_config(cfg)
        return get_model_config()
    model_manager.update_provider(current["id"], {"model": model_name})
    return get_model_config()


def build_gateway(workspace: str):
    import asyncio
    from imos.orchestrator import IMOSOrchestrator
    from imos.registry import AdapterRegistry

    workspace_path = Path(workspace)
    cfg = load_config()
    state_root = resolve_runtime_state_root(workspace_path)
    consent_manager = ConsentManager(state_root)
    consent_record = consent_manager.ensure()
    session_manager = ConnectSessionManager(state_root / "sessions")
    session_manager.ensure_default()
    memory_store = ConnectMemoryStore(state_root / "memory")
    audit_logger = AuditLogger(state_root / "audit")
    cost_tracker = CostTracker(state_root / "cost")
    event_bus = EventBus(state_root / "events")
    routing_rules = RoutingRules(PROJECT_ROOT / "config" / "routing.json")
    approval_policy = ApprovalPolicy(load_config, audit_logger)
    confirm_policy = ConfirmationPolicy()
    contact_book = ContactBook(state_root)
    shell_runner = ShellRunner(state_root / "commands", audit_logger, approval_policy)
    process_manager = ProcessRegistry(state_root / "processes", audit_logger)
    task_manager = TaskManager(state_root / "tasks", audit_logger)
    terminal_manager = TerminalSessionManager(state_root / "terminals", audit_logger)
    mcp_runtime = MCPRuntime()
    for row in cfg.get("mcp", {}).get("servers", []):
        try:
            mcp_runtime.register_server(MCPServer(name=row["name"], url=row["url"], enabled=bool(row.get("enabled", True))))
        except Exception:
            continue
    skill_registry = SkillRegistry(workspace_path, bundled_root=Path.cwd() / "skills")
    workflow_registry = WorkflowRegistry(workspace_path)
    runtime = ConnectAIRuntime(
        skill_registry,
        memory_store,
        shell_runner=shell_runner,
        process_manager=process_manager,
        audit_logger=audit_logger,
        task_manager=task_manager,
        cost_tracker=cost_tracker,
        mcp_runtime=mcp_runtime,
        event_bus=event_bus,
        session_manager=session_manager,
    )
    runtime.consent_manager = consent_manager
    registry = AdapterRegistry()
    try:
        asyncio.run(registry.auto_discover())
        imos_orchestrator = IMOSOrchestrator(registry)
    except Exception:
        imos_orchestrator = None
    cli_channel = CLIChannel()
    global _LISTENER_SERVICE, _VOICE_MANAGER
    if _VOICE_MANAGER is None:
        _VOICE_MANAGER = VoiceManager(state_root / "voice")
    else:
        _VOICE_MANAGER.state_root = state_root / "voice"
        _VOICE_MANAGER.state_root.mkdir(parents=True, exist_ok=True)
        _VOICE_MANAGER.path = _VOICE_MANAGER.state_root / "voice.json"
    if _LISTENER_SERVICE is None:
        _LISTENER_SERVICE = VoiceListenerService(
            state_root / "listener",
            event_bus=event_bus,
            audit_logger=audit_logger,
            speaker=_VOICE_MANAGER,
        )
    else:
        _LISTENER_SERVICE.state_root = state_root / "listener"
        _LISTENER_SERVICE.state_root.mkdir(parents=True, exist_ok=True)
        _LISTENER_SERVICE.path = _LISTENER_SERVICE.state_root / "listener.json"
        _LISTENER_SERVICE.event_bus = event_bus
        _LISTENER_SERVICE.audit_logger = audit_logger
        _LISTENER_SERVICE.speaker = _VOICE_MANAGER
    _LISTENER_SERVICE.maybe_start_from_config(cfg)

    def _tool_executor(name: str, args: dict):
        skill = next((item for item in skill_registry.load_all() if item.name == name), None)
        if not skill:
            return f"Unknown skill: {name}"
        return skill.handler(
            args,
            workspace=str(workspace_path),
            memory_store=memory_store,
            session_id="workflow",
            model_config=get_model_config(),
            shell_runner=shell_runner,
            process_manager=process_manager,
            audit_logger=audit_logger,
        )

    def _doctor_output() -> str:
        from imos.doctor import doctor_report
        import asyncio

        return asyncio.run(
            doctor_report(
                session_manager=session_manager,
                dashboard_service=_DASHBOARD_SERVICE,
                routing_rules=routing_rules,
                event_bus=event_bus,
                process_manager=process_manager,
                listener_service=_LISTENER_SERVICE,
                consent_manager=consent_manager,
                contact_book=contact_book,
                voice_manager=_VOICE_MANAGER,
                state_root=state_root,
            )
        )

    def _set_nested_value(data: dict, path: str, value):
        parts = [part for part in path.split(".") if part]
        node = data
        for key in parts[:-1]:
            current = node.get(key)
            if not isinstance(current, dict):
                current = {}
                node[key] = current
            node = current
        if parts:
            node[parts[-1]] = value

    def _get_nested_value(data: dict, path: str):
        node = data
        for key in [part for part in path.split(".") if part]:
            if not isinstance(node, dict) or key not in node:
                raise KeyError(path)
            node = node[key]
        return node

    def _mutation_blocked(action: str) -> CommandResult | None:
        if consent_manager.is_granted():
            return None
        return CommandResult(True, f"Read-only mode: {action} requires /consent first.")

    def _prompt_contact_resolution(query: str) -> str | None:
        if not sys.stdin or not sys.stdin.isatty():
            return None
        console.print(f"I don't have a contact for '{query}'.")
        answer = input("What's their name or number? ").strip()
        if not answer:
            return None
        contact_book.add(query, answer)
        return answer

    def _open_dashboard_url() -> str:
        if _DASHBOARD_SERVICE is None:
            return "Dashboard is not initialized."
        status = _DASHBOARD_SERVICE.status()
        url = status.get("url", "http://127.0.0.1:8766")
        webbrowser.open(url + "/")
        _DASHBOARD_SERVICE._browser_opened = True
        return f"Opened IMOS dashboard {url}/"

    def _cmd_help(_raw: str) -> CommandResult:
        return CommandResult(True, _help_output())

    def _cmd_exit(_raw: str) -> CommandResult:
        return CommandResult(True, should_exit=True)

    def _cmd_clear(_raw: str) -> CommandResult:
        os.system("cls" if os.name == "nt" else "clear")
        render_home_screen(get_model_config(), workspace)
        return CommandResult(True, "")

    def _cmd_model(_raw: str) -> CommandResult:
        parts = _raw.split()
        if len(parts) == 1:
            safe = dict(get_model_config())
            for key in ("api_key", "aws_secret_access_key"):
                if safe.get(key):
                    safe[key] = _mask_secret(str(safe[key]))
            return CommandResult(True, json.dumps(safe, indent=2))
        action = parts[1].lower()
        if action == "list":
            lines = []
            for provider in model_manager.load_providers():
                health = model_manager.test_provider(provider["id"])
                status = "healthy" if health.get("ok") else "unhealthy"
                latency = f"{health.get('latency', 0)}ms" if health.get("latency") else "-"
                marker = " [default]" if provider.get("is_default") else ""
                lines.append(f"{provider['id']:<18} {provider['type']:<12} {provider.get('model', '-'):<32} {status:<10} {latency}{marker}")
            return CommandResult(True, "\n".join(lines) if lines else "No providers configured.")
        if action == "add":
            shortcut = parts[2].lower() if len(parts) >= 3 else ""
            provider_type = shortcut if shortcut in model_manager.PROVIDER_TYPES else _select(
                "Provider type",
                [Choice(value=name, name=meta["name"]) for name, meta in model_manager.PROVIDER_TYPES.items()],
            )
            defaults = model_manager.PROVIDER_TYPES[provider_type]
            display_name = defaults["name"] if shortcut else _text("Display name", default=defaults["name"])
            model_name = _text("Model", default="") or get_provider_defaults(provider_type).get("model", "")
            api_key = ""
            if defaults.get("requires_key", False):
                api_key = _secret("API key")
            base_url = defaults.get("base_url", "")
            if provider_type in {"ollama", "lmstudio", "custom"}:
                base_url = _text("Base URL", default=base_url)
            provider_id = re.sub(r"[^a-z0-9._-]+", "-", display_name.strip().lower()).strip("-") or f"{provider_type}-main"
            provider = model_manager.add_provider(
                {
                    "id": provider_id,
                    "name": display_name,
                    "type": provider_type,
                    "api_key": api_key,
                    "base_url": base_url,
                    "model": model_name,
                    "enabled": True,
                    "is_default": not bool(model_manager.load_providers()),
                }
            )
            return CommandResult(True, f"Added provider {provider['id']}")
        if action == "set" and len(parts) >= 4 and parts[2].lower() == "default":
            provider = model_manager.set_default(parts[3])
            return CommandResult(True, f"Default provider set to {provider['id']}", updated_model_config=_provider_to_model_config(provider))
        if action == "test" and len(parts) >= 3:
            result = model_manager.test_provider(parts[2])
            if result.get("ok"):
                return CommandResult(True, f"Provider {parts[2]} healthy ({result.get('latency', 0)}ms)")
            return CommandResult(True, f"Provider {parts[2]} failed: {result.get('error', 'unknown error')}")
        if action == "remove" and len(parts) >= 3:
            removed = model_manager.remove_provider(parts[2])
            return CommandResult(True, f"Removed {parts[2]}" if removed else f"Provider not found: {parts[2]}")
        if action == "models" and len(parts) >= 3:
            try:
                rows = model_manager.list_models(parts[2])
            except Exception as exc:
                return CommandResult(True, f"Model list failed: {exc}")
            return CommandResult(True, "\n".join(rows) if rows else "No models returned.")
        return CommandResult(True, "Usage: /model list | /model add [ollama|lmstudio] | /model set default <id> | /model test <id> | /model remove <id> | /model models <id>")

    def _cmd_provider(_raw: str) -> CommandResult:
        cfg = get_model_config()
        return CommandResult(True, f"{cfg.get('provider')}/{cfg.get('model')}")

    def _cmd_models(_raw: str) -> CommandResult:
        return _cmd_model("/model list")

    def _cmd_use(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 2:
            provider = parts[1].strip().lower()
        else:
            provider_choices = [Choice(value=k, name=PROVIDER_LABELS[k]) for k in list_providers()]
            provider = _select("Switch to which provider?", provider_choices)
        if provider not in list_providers():
            return CommandResult(True, f"Unknown provider: {provider}")
        updated = _save_provider(provider)
        return CommandResult(True, f"Switched to {updated.get('provider')}/{updated.get('model')}", updated_model_config=updated)

    def _cmd_claude_code(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            result = open_claude_code_interactive(str(workspace_path))
            if result.get("success"):
                return CommandResult(True, f"Opened Claude Code interactive shell in {workspace_path}")
            return CommandResult(True, str(result.get("error", "Claude Code launch failed.")))
        result = chat_with_claude_code(parts[1].strip(), project_path=str(workspace_path))
        if result.get("success"):
            return CommandResult(True, str(result.get("output") or "(no output)"))
        return CommandResult(True, str(result.get("error") or "Claude Code request failed."))

    def _cmd_openai(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return CommandResult(True, "Usage: /openai <prompt>")
        result = chat_with_openai(parts[1].strip())
        if result.get("success"):
            return CommandResult(True, str(result.get("reply") or ""))
        return CommandResult(True, str(result.get("error") or "OpenAI request failed."))

    def _cmd_codex(raw: str) -> CommandResult:
        prompt = raw.split(maxsplit=1)[1].strip() if len(raw.split(maxsplit=1)) == 2 else ""
        if not prompt:
            return CommandResult(True, "Usage: /codex <prompt>")
        result = chat_with_openai(prompt)
        if result.get("success"):
            return CommandResult(True, str(result.get("reply") or ""))
        return CommandResult(True, str(result.get("error") or "OpenAI request failed."))

    def _start_mcp_server(port: int = 8765, host: str = "127.0.0.1") -> tuple[str, list[str]]:
        import urllib.request

        warnings: list[str] = []
        proc = start_imos_mcp_server_http_on(PROJECT_ROOT, port=port, host=host)
        url = f"http://{host}:{port}/mcp/sse"
        ready = False
        for _ in range(10):
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    if int(getattr(response, "status", 0)) == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.3)
        if not ready:
            if proc.poll() is not None:
                raise RuntimeError(f"MCP server process exited early with code {proc.returncode}")
            raise RuntimeError(f"MCP server did not become reachable at {url}")
        try:
            record = process_manager.register(
                name="imos-mcp-server",
                command=f'{sys.executable} -m imos.mcp_server --http --host {host} --port {port}',
                cwd=str(PROJECT_ROOT),
                process=proc,
                metadata={"url": f"http://{host}:{port}/mcp"},
            )
            started = f"MCP server started on http://{host}:{port}/mcp (pid={record.pid}, process_id={record.process_id})"
        except PermissionError as exc:
            warnings.append(f"Process tracking warning: {exc}")
            started = f"MCP server started on http://{host}:{port}/mcp (pid={proc.pid}, untracked)"
        except Exception as exc:
            warnings.append(f"Process tracking warning: {exc}")
            started = f"MCP server started on http://{host}:{port}/mcp (pid={proc.pid}, untracked)"
        return started, warnings

    def _cmd_doctor(_raw: str) -> CommandResult:
        try:
            return CommandResult(True, _doctor_output())
        except Exception as exc:
            return CommandResult(True, f"Doctor failed: {exc}")

    def _cmd_cursor(raw: str) -> CommandResult:
        prompt = raw.split(maxsplit=1)[1].strip() if len(raw.split(maxsplit=1)) == 2 else ""
        cursor_result = open_ide_with_fallback(workspace_path, prompt=prompt)
        lines = []
        launcher = cursor_result.get("launcher", "Cursor")
        if cursor_result.get("success") and launcher != "browser fallback":
            lines.append(f"Launched {launcher} for {workspace_path} (pid={cursor_result.get('pid')})")
        elif cursor_result.get("success") and launcher == "browser fallback":
            lines.append("No desktop IDE found. Opened browser fallback:")
            for url in cursor_result.get("urls", []):
                lines.append(f"- {url}")
        else:
            lines.append(f"IDE launch failed: {cursor_result.get('error')}")
            searched = cursor_result.get("searched") or []
            if searched:
                lines.append("Searched:")
                lines.extend(f"- {item}" for item in searched)

        existing = None
        for row in process_manager.list():
            if row.get("name") == "imos-mcp-server" and str(row.get("status")) == "running":
                meta = row.get("metadata") or {}
                if str(meta.get("url", "")) == "http://127.0.0.1:8765/mcp":
                    existing = row
                    break

        if existing is not None:
            lines.append(
                f"MCP server already running on http://127.0.0.1:8765/mcp (pid={existing.get('pid')}, process_id={existing.get('process_id')})"
            )
        else:
            try:
                started, warnings = _start_mcp_server(port=8765, host="127.0.0.1")
                lines.append(started)
                lines.extend(warnings)
            except Exception as exc:
                lines.append(f"MCP server failed to start: {exc}")

        lines.append("")
        lines.append("Cursor mcp.json snippet:")
        lines.append(cursor_mcp_http_snippet("http://127.0.0.1:8765/mcp"))
        return CommandResult(True, "\n".join(lines))

    def _cmd_ide(raw: str) -> CommandResult:
        prompt = raw.split(maxsplit=1)[1].strip() if len(raw.split(maxsplit=1)) == 2 else ""
        result = open_ide_with_fallback(workspace_path, prompt=prompt)
        lines = []
        launcher = result.get("launcher", "IDE")
        if result.get("success") and launcher != "browser fallback":
            lines.append(f"Launched {launcher} for {workspace_path} (pid={result.get('pid')})")
        elif launcher == "browser fallback":
            lines.append("No desktop IDE found. Opened browser fallback:")
            for url in result.get("urls", []):
                lines.append(f"- {url}")
        else:
            lines.append(f"IDE launch failed: {result.get('error')}")
        searched = result.get("searched") or []
        if searched and not result.get("success"):
            lines.append("Searched:")
            lines.extend(f"- {item}" for item in searched)
        return CommandResult(True, "\n".join(lines))

    def _cmd_vscode(_raw: str) -> CommandResult:
        result = open_workspace_in_app("code", workspace_path, install_hint="https://code.visualstudio.com/")
        if result.get("success"):
            return CommandResult(
                True,
                f"Opened VS Code for {workspace_path} (pid={result.get('pid')})\nInstall the IMOS MCP config with: imos mcp install",
            )
        return CommandResult(True, str(result.get("error") or "VS Code launch failed."))

    def _cmd_windsurf(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            result = open_workspace_in_app("windsurf", workspace_path, install_hint="Install Windsurf desktop/CLI")
            if result.get("success"):
                return CommandResult(True, f"Opened Windsurf for {workspace_path} (pid={result.get('pid')})\nMCP config path is already supported by `imos mcp install`.")
            return CommandResult(True, str(result.get("error") or "Windsurf launch failed."))
        result = run_cli_agent("windsurf", parts[1].strip(), project_path=str(workspace_path), install_hint="Install Windsurf CLI")
        return CommandResult(True, str(result.get("output") if result.get("success") else result.get("error")))

    def _cmd_aider(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return CommandResult(True, "Usage: /aider <prompt>")
        result = run_cli_agent("aider", parts[1].strip(), project_path=str(workspace_path), install_hint="pip install aider-chat")
        return CommandResult(True, str(result.get("output") if result.get("success") else result.get("error")))

    def _cmd_continue(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return CommandResult(True, "Usage: /continue <prompt>")
        result = run_cli_agent("continue", parts[1].strip(), project_path=str(workspace_path), install_hint="Install Continue CLI")
        return CommandResult(True, str(result.get("output") if result.get("success") else result.get("error")))

    def _cmd_gemini(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return CommandResult(True, "Usage: /gemini <prompt>")
        result = chat_with_gemini(parts[1].strip())
        return CommandResult(True, str(result.get("reply") if result.get("success") else result.get("error")))

    def _cmd_email(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or "|" not in parts[1]:
            return CommandResult(True, "Usage: /email <to>|<subject>|<body>")
        to_addr, subject, body = [item.strip() for item in parts[1].split("|", 2)]
        result = send_email_smtp(to_addr, subject, body)
        return CommandResult(True, json.dumps(result, indent=2))

    def _cmd_whatsapp(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or "|" not in parts[1]:
            return CommandResult(True, "Usage: /whatsapp <contact>|<message>")
        contact, message = [item.strip() for item in parts[1].split("|", 1)]
        url = f"https://web.whatsapp.com/"
        result = open_prompt_url(url + "?text=", f"{contact}: {message}")
        return CommandResult(True, f"Opened WhatsApp handoff URL for {contact}\n{result.get('url')}")

    def _cmd_telegram(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or "|" not in parts[1]:
            return CommandResult(True, "Usage: /telegram <contact>|<message>")
        contact, message = [item.strip() for item in parts[1].split("|", 1)]
        result = open_prompt_url("https://web.telegram.org/k/#?text=", f"{contact}: {message}")
        return CommandResult(True, f"Opened Telegram handoff URL for {contact}\n{result.get('url')}")

    def _cmd_v0(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return CommandResult(True, "Usage: /v0 <prompt>")
        result = open_prompt_url("https://v0.dev/chat?q=", parts[1].strip())
        return CommandResult(True, str(result.get("url")))

    def _cmd_lovable(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return CommandResult(True, "Usage: /lovable <prompt>")
        result = open_prompt_url("https://lovable.dev/?prompt=", parts[1].strip())
        return CommandResult(True, str(result.get("url")))

    def _cmd_bolt(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            return CommandResult(True, "Usage: /bolt <prompt>")
        result = open_prompt_url("https://bolt.new/?prompt=", parts[1].strip())
        return CommandResult(True, str(result.get("url")))

    def _cmd_setmodel(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) != 2 or not parts[1].strip():
            provider, model_name = pick_provider_model(get_model_config().get("provider"))
            cfg = load_config()
            current = get_provider_defaults(provider)
            current["provider"] = provider
            current["model"] = model_name
            cfg["model"] = current
            save_config(cfg)
            updated = get_model_config()
            return CommandResult(True, f"Switched to {updated.get('provider')}/{updated.get('model')}", updated_model_config=updated)
        updated = _save_model_name(parts[1].strip())
        return CommandResult(True, f"Model set to {updated.get('model')}", updated_model_config=updated)

    def _cmd_pickmodel(_raw: str) -> CommandResult:
        provider, model_name = pick_provider_model(get_model_config().get("provider"))
        cfg = load_config()
        current = get_provider_defaults(provider)
        current["provider"] = provider
        current["model"] = model_name
        cfg["model"] = current
        save_config(cfg)
        updated = get_model_config()
        return CommandResult(True, f"Switched to {updated.get('provider')}/{updated.get('model')}", updated_model_config=updated)

    def _cmd_setkey(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=2)
        if len(parts) != 3:
            return CommandResult(True, "Usage: /setkey <provider> <key>")
        _, provider, key = parts
        cfg = load_config()
        model_cfg = get_provider_defaults(provider)
        current = cfg.get("model", {})
        if current.get("provider") == provider:
            model_cfg.update(current)
        model_cfg["provider"] = provider
        model_cfg["api_key"] = key
        cfg["model"] = model_cfg
        save_config(cfg)
        updated = get_model_config()
        return CommandResult(True, f"Key saved for {provider}", updated_model_config=updated)

    def _cmd_settoken(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=2)
        if len(parts) != 3:
            return CommandResult(True, "Usage: /settoken <service> <token>")
        _, svc, tok = parts
        cfg = load_config()
        cfg.setdefault("tokens", {})[svc] = tok
        save_config(cfg)
        return CommandResult(True, f"{svc} token saved")

    def _cmd_workspace(_raw: str) -> CommandResult:
        return CommandResult(True, workspace)

    def _cmd_cd(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) != 2:
            return CommandResult(True, "Usage: /cd <path>")
        new_ws = parts[1].strip()
        if not Path(new_ws).exists():
            return CommandResult(True, f"Path not found: {new_ws}")
        return CommandResult(True, f"Workspace changed to {new_ws}", updated_workspace=new_ws)

    def _cmd_dashboard(_raw: str) -> CommandResult:
        parts = _raw.split()
        if len(parts) > 1 and parts[1].lower() == "stop":
            if _DASHBOARD_SERVICE is not None:
                _DASHBOARD_SERVICE.stop()
                return CommandResult(True, "Dashboard stopped.")
            return CommandResult(True, "Dashboard is not initialized.")
        if _DASHBOARD_SERVICE is None:
            return CommandResult(True, "Dashboard is not initialized.")
        return CommandResult(True, _open_dashboard_url())

    def _cmd_consent(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) == 1:
            status = consent_manager.status()
            state = "granted" if status.get("granted") else "declined"
            return CommandResult(True, f"Consent: {state}")
        action = parts[1].strip().lower()
        if action in {"grant", "agree"}:
            consent_manager.save(True)
            return CommandResult(True, "Consent granted.")
        if action in {"decline", "deny"}:
            consent_manager.save(False)
            return CommandResult(True, "Consent declined. IMOS is now read-only.")
        return CommandResult(True, "Usage: /consent grant|decline")

    def _cmd_contact(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=3)
        if len(parts) == 1 or parts[1].lower() == "list":
            rows = contact_book.list()
            if not rows:
                return CommandResult(True, "No contacts saved.")
            return CommandResult(True, "\n".join(f"- {name}: {value}" for name, value in sorted(rows.items())))
        action = parts[1].lower()
        if action == "add" and len(parts) == 4:
            result = contact_book.add(parts[2], parts[3])
            return CommandResult(True, f"Saved contact: {result['name']}")
        if action == "remove" and len(parts) >= 3:
            result = contact_book.remove(parts[2])
            return CommandResult(True, f"Removed contact: {parts[2]}" if result.get("ok") else f"Contact not found: {parts[2]}")
        return CommandResult(True, "Usage: /contact add <name> <number> | /contact list | /contact remove <name>")

    def _cmd_listen(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=2)
        if len(parts) == 1 or parts[1].lower() == "status":
            status = _LISTENER_SERVICE.status() if _LISTENER_SERVICE is not None else {"active": False}
            mode = "active" if status.get("active") else "inactive"
            details = f"{mode} (wake: {status.get('wake_word', 'IMOS')})"
            if status.get("missing"):
                details += f"\nMissing deps: {', '.join(status['missing'])}"
            return CommandResult(True, details)
        if _LISTENER_SERVICE is None:
            return CommandResult(True, "Listener is not initialized.")
        action = parts[1].lower()
        if action == "start":
            persist = "--save" in raw.lower()
            status = _LISTENER_SERVICE.start(persist=persist)
            cfg = load_config()
            cfg.setdefault("listen", {})
            cfg["listen"]["enabled"] = True
            cfg["listen"]["persist"] = persist
            save_config(cfg)
            return CommandResult(True, f"Listener {'started' if status.get('configured_active') else 'not started'}")
        if action == "stop":
            _LISTENER_SERVICE.stop()
            cfg = load_config()
            cfg.setdefault("listen", {})
            cfg["listen"]["enabled"] = False
            cfg["listen"]["persist"] = False
            save_config(cfg)
            return CommandResult(True, "Listener stopped")
        if action == "wake" and len(parts) == 3:
            phrase = parts[2].strip().strip('"')
            status = _LISTENER_SERVICE.set_wake_word(phrase)
            return CommandResult(True, f"Wake word set to {status.get('wake_word')}")
        return CommandResult(True, "Usage: /listen start [--save] | /listen stop | /listen status | /listen wake \"phrase\"")

    def _cmd_voice(raw: str) -> CommandResult:
        if _VOICE_MANAGER is None:
            return CommandResult(True, "Voice is not initialized.")
        parts = raw.split(maxsplit=2)
        if len(parts) == 1 or parts[1].lower() == "status":
            status = _VOICE_MANAGER.status()
            muted = "muted" if status.get("muted") else "on"
            return CommandResult(True, f"{status.get('provider')} ({status.get('provider_label')}) {muted}")
        action = parts[1].lower()
        if action == "set" and len(parts) == 3:
            status = _VOICE_MANAGER.set_voice(parts[2].strip())
            return CommandResult(True, f"Voice set to {status.get('provider_label')}")
        if action == "test":
            result = _VOICE_MANAGER.speak(_VOICE_MANAGER.test_phrase())
            return CommandResult(True, "Voice test played." if result.get("ok") else f"Voice test failed: {result.get('error', 'unknown error')}")
        if action == "off":
            _VOICE_MANAGER.mute()
            return CommandResult(True, "Voice muted.")
        if action == "on":
            _VOICE_MANAGER.unmute()
            return CommandResult(True, "Voice enabled.")
        return CommandResult(True, "Usage: /voice set <voice_id> | /voice test | /voice off | /voice on | /voice status")

    def _cmd_autostart(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        action = "status" if len(parts) == 1 else parts[1].strip().lower()
        if action == "enable":
            result = enable_autostart(PROJECT_ROOT)
            return CommandResult(True, f"Autostart enabled: {result.get('command', '')}")
        if action == "disable":
            result = disable_autostart()
            return CommandResult(True, "Autostart disabled." if result.get("removed") else "Autostart was not enabled.")
        if action == "status":
            status = autostart_status(PROJECT_ROOT)
            return CommandResult(True, "enabled" if status.get("enabled") else "disabled")
        return CommandResult(True, "Usage: /autostart enable|disable|status")

    def _run_imos_cli(args: list[str]) -> CommandResult:
        command = [sys.executable, "-m", "imos.cli", *args]
        try:
            result = subprocess.run(
                command,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            return CommandResult(True, f"IMOS CLI error: {exc}")
        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()
        if result.returncode != 0:
            return CommandResult(True, error or output or f"IMOS CLI exited with code {result.returncode}")
        return CommandResult(True, output or error or "Command completed.")

    def _cmd_imos(raw: str) -> CommandResult:
        try:
            parts = shlex.split(raw)
        except Exception as exc:
            return CommandResult(True, f"Parse error: {exc}")
        if len(parts) == 1:
            return CommandResult(True, "Usage: /imos <command...>")
        return _run_imos_cli(parts[1:])

    def _cmd_status(_raw: str) -> CommandResult:
        return _run_imos_cli(["status"])

    def _cmd_history(_raw: str) -> CommandResult:
        return _run_imos_cli(["history"])

    def _cmd_adapters(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        args = ["adapters"]
        if len(parts) == 1:
            args.append("list")
        else:
            args.extend(shlex.split(parts[1]))
        return _run_imos_cli(args)

    def _cmd_wake(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        action = "status" if len(parts) == 1 else parts[1].strip()
        if action not in {"status", "start", "stop", "install", "uninstall"}:
            return CommandResult(True, "Usage: /wake status|start|stop|install|uninstall")
        return _run_imos_cli(["wake", action])

    def _cmd_palette(raw: str) -> CommandResult:
        parts = raw.split()
        if len(parts) == 1 or parts[1].lower() == "list":
            return _run_imos_cli(["palette", "list"])
        if len(parts) == 4 and parts[1].lower() == "set" and parts[2].lower() in {"shell", "dashboard"}:
            option = f"--{parts[2].lower()}"
            return _run_imos_cli(["palette", "set", option, parts[3]])
        return CommandResult(True, "Usage: /palette list | /palette set shell <name> | /palette set dashboard <name>")

    def _cmd_login(_raw: str) -> CommandResult:
        run_login()
        return CommandResult(True, "")

    def _cmd_logout(_raw: str) -> CommandResult:
        run_logout()
        return CommandResult(True, "")

    def _cmd_skills(_raw: str) -> CommandResult:
        items = skill_registry.load_all()
        return CommandResult(True, "\n".join(f"- {item.name} [{item.source}]: {item.description}" for item in items))

    def _cmd_workflows(_raw: str) -> CommandResult:
        rows = workflow_registry.list_workflows()
        if not rows:
            return CommandResult(True, "No workflows found.")
        return CommandResult(True, "\n".join(f"- {row['name']} ({row['steps']} steps)" for row in rows))

    def _cmd_runflow(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        if len(parts) != 2:
            return CommandResult(True, "Usage: /runflow <name>")
        result = workflow_registry.run(parts[1].strip(), tool_executor=_tool_executor, sender=lambda content: content)
        return CommandResult(True, json.dumps(result, indent=2))

    def _cmd_sessions(_raw: str) -> CommandResult:
        rows = session_manager.list_sessions()
        if not rows:
            return CommandResult(True, "No sessions yet.")
        return CommandResult(True, "\n".join(f"- {row.session_key} ({row.message_count} messages)" for row in rows))

    def _cmd_session(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=2)
        if len(parts) == 1 or parts[1].lower() == "list":
            rows = session_manager.list_sessions()
            if not rows:
                return CommandResult(True, "No sessions yet.")
            active_name = session_manager.get_active().name
            return CommandResult(
                True,
                "\n".join(
                    f"- {row.name} [{row.status}] {row.message_count} messages{' (active)' if row.name == active_name else ''}"
                    for row in rows
                ),
            )
        action = parts[1].lower()
        if action == "new":
            if len(parts) < 3 or not parts[2].strip():
                return CommandResult(True, "Usage: /session new <name>")
            session = session_manager.create(parts[2].strip(), channel="cli", user_id="local-user")
            return CommandResult(True, f"Active session: {session.name}")
        if action == "resume":
            if len(parts) < 3 or not parts[2].strip():
                return CommandResult(True, "Usage: /session resume <name>")
            session = session_manager.get(parts[2].strip())
            if session is None:
                return CommandResult(True, f"Session not found: {parts[2].strip()}")
            session.status = "active"
            session_manager.update(session)
            session_manager.set_active(session.name)
            return CommandResult(True, f"Resumed session: {session.name}")
        if action == "save":
            session = session_manager.get_active()
            session.status = "paused"
            session_manager.update(session)
            session_manager.set_active(session.name)
            return CommandResult(True, f"Saved session: {session.name}")
        if action == "export":
            if len(parts) < 3 or not parts[2].strip():
                return CommandResult(True, "Usage: /session export <name>")
            try:
                payload = session_manager.export_session(parts[2].strip())
            except KeyError:
                return CommandResult(True, f"Session not found: {parts[2].strip()}")
            return CommandResult(True, payload.get("export_path", ""))
        return CommandResult(True, "Usage: /session new <name> | /session list | /session resume <name> | /session save | /session export <name>")

    def _cmd_route(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=3)
        if len(parts) == 1 or (len(parts) > 1 and parts[1].lower() == "list"):
            rules = routing_rules.list_rules()
            return CommandResult(True, "\n".join(f"{key:16} {value or '-'}" for key, value in rules.items()))
        if len(parts) == 4 and parts[1].lower() == "set":
            task_type = parts[2].strip().lower()
            provider = parts[3].strip().lower()
            routing_rules.set_rule(task_type, provider)
            session = session_manager.get_active()
            session_manager.set_provider_and_routing(session.session_id, session.active_provider, routing_rules.list_rules())
            return CommandResult(True, f"Route set: {task_type} -> {provider}")
        return CommandResult(True, "Usage: /route set <task_type> <provider> | /route list")

    def _cmd_tasks(_raw: str) -> CommandResult:
        rows = task_manager.list(20)
        if not rows:
            return CommandResult(True, "No tasks yet.")
        return CommandResult(True, "\n".join(f"- {row['task_id']} [{row['status']}] {row['objective']}" for row in rows))

    def _cmd_processes(_raw: str) -> CommandResult:
        rows = process_manager.list()
        if not rows:
            return CommandResult(True, "No managed processes.")
        return CommandResult(True, "\n".join(f"- {row['process_id']} pid={row['pid']} [{row['status']}] {row['command']}" for row in rows))

    def _cmd_audit(_raw: str) -> CommandResult:
        rows = audit_logger.tail(30)
        if not rows:
            return CommandResult(True, "No audit entries yet.")
        return CommandResult(True, "\n".join(f"- {row['ts']} [{row['kind']}] {row['message']}" for row in rows))

    def _cmd_git(raw: str) -> CommandResult:
        git = GitAutopilot(str(workspace_path))
        parts = raw.split(maxsplit=2)
        action = parts[1].lower() if len(parts) > 1 else "status"
        try:
            if action == "status":
                return CommandResult(True, json.dumps(git.status(), indent=2))
            if action == "branch":
                name = parts[2] if len(parts) > 2 else "task"
                return CommandResult(True, git.create_task_branch(name))
            if action == "commit":
                message = parts[2] if len(parts) > 2 else "update"
                return CommandResult(True, git.stage_and_commit(message))
            if action == "diff":
                return CommandResult(True, git.diff_summary())
            if action == "log":
                return CommandResult(True, json.dumps(git.get_log(5), indent=2))
            return CommandResult(True, "Usage: /git status|branch <name>|commit <msg>|diff|log")
        except Exception as exc:
            return CommandResult(True, f"Git error: {exc}")

    def _cmd_mcp(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=1)
        action = parts[1].strip().lower() if len(parts) == 2 else "list"
        if action == "install":
            return _run_imos_cli(["mcp", "install"])
        if action == "serve":
            try:
                started, warnings = _start_mcp_server(port=8767, host="127.0.0.1")
                text = "\n".join([started, *warnings]) if warnings else started
                return CommandResult(True, text)
            except Exception as exc:
                return CommandResult(True, f"Failed to start MCP server: {exc}")
        payload = {"servers": mcp_runtime.list_servers(), "tools": mcp_runtime.list_tools()}
        return CommandResult(True, json.dumps(payload, indent=2))

    def _cmd_terminal(_raw: str) -> CommandResult:
        rows = terminal_manager.list()
        if not rows:
            return CommandResult(True, "No terminal sessions.")
        return CommandResult(True, "\n".join(f"- {row['session_id']} pid={row['pid']} cwd={row['cwd']}" for row in rows))

    def _cmd_memory(raw: str) -> CommandResult:
        query = raw.split(maxsplit=1)[1].strip() if len(raw.split(maxsplit=1)) == 2 else ""
        blocks = memory_store.context_blocks(query=query)
        return CommandResult(True, "\n\n".join(blocks) if blocks else "No memory found.")

    def _cmd_integrations(_raw: str) -> CommandResult:
        cfg = load_config()
        payload = {
            "tokens": cfg.get("tokens", {}),
            "messaging": cfg.get("messaging", {}),
            "clerk_publishable_key": bool(_clerk_env()[0]),
            "clerk_secret_key": bool(_clerk_env()[1]),
        }
        return CommandResult(True, json.dumps(payload, indent=2))

    def _cmd_setup(_raw: str) -> CommandResult:
        force_run_setup_wizard(PROJECT_ROOT, workspace)
        updated = get_model_config()
        cfg = load_config()
        return CommandResult(True, "Setup updated.", updated_model_config=updated, updated_workspace=cfg.get("workspace", workspace))

    def _cmd_config(raw: str) -> CommandResult:
        parts = raw.split(maxsplit=3)
        if len(parts) < 3:
            return CommandResult(True, "Usage: /config get <path> | /config set <path> <json-value>")
        action = parts[1].lower()
        path = parts[2]
        cfg = load_config()
        if action == "get":
            try:
                value = _get_nested_value(cfg, path)
            except KeyError:
                return CommandResult(True, f"Config path not found: {path}")
            return CommandResult(True, json.dumps(value, indent=2) if isinstance(value, (dict, list)) else str(value))
        if action == "set":
            if len(parts) != 4:
                return CommandResult(True, "Usage: /config set <path> <json-value>")
            try:
                value = json.loads(parts[3])
            except Exception:
                value = parts[3]
            _set_nested_value(cfg, path, value)
            save_config(cfg)
            updated_model = get_model_config() if path.startswith("model.") or path == "model" else None
            return CommandResult(True, f"Config updated: {path}", updated_model_config=updated_model)
        return CommandResult(True, f"Unknown config action: {action}")

    def _run_skill_direct(name: str, args: dict, *, summary: str) -> CommandResult:
        blocked = _mutation_blocked(name)
        if blocked is not None and name in {"computer_control", "send_email", "open_application", "write_file", "bash", "scaffold_react_app", "scaffold_nextjs"}:
            return blocked
        skill = next((item for item in skill_registry.load_all() if item.name == name), None)
        if skill is None:
            return CommandResult(True, f"Unknown skill: {name}")
        active_session = session_manager.get_active()
        event_bus.tool_start(name, summary, session_id=active_session.session_id)
        started = time.perf_counter()
        try:
            event_bus.tool_progress(name, "Executing tool", session_id=active_session.session_id)
            result = skill.handler(
                args,
                workspace=str(workspace_path),
                memory_store=memory_store,
                session_id=active_session.session_id,
                model_config=get_model_config(),
                shell_runner=shell_runner,
                process_manager=process_manager,
                audit_logger=audit_logger,
            )
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        duration = round(time.perf_counter() - started, 3)
        status = "ok"
        if isinstance(result, dict) and result.get("ok") is False:
            status = "error"
        event_bus.tool_end(name, status, duration, session_id=active_session.session_id)
        session_manager.record_tool_call(
            active_session.session_id,
            name=name,
            input_summary=summary,
            status=status,
            duration=duration,
            metadata={"input": args},
        )
        return CommandResult(True, json.dumps(result, indent=2) if isinstance(result, dict) else str(result))

    def _run_direct_action(name: str, summary: str, action) -> CommandResult:
        blocked = _mutation_blocked(name)
        if blocked is not None and name not in {"describe_screen"}:
            return blocked
        active_session = session_manager.get_active()
        event_bus.tool_start(name, summary, session_id=active_session.session_id)
        started = time.perf_counter()
        try:
            event_bus.tool_progress(name, "Executing action", session_id=active_session.session_id)
            result = action()
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        duration = round(time.perf_counter() - started, 3)
        status = "ok" if not (isinstance(result, dict) and result.get("ok") is False) else "error"
        event_bus.tool_end(name, status, duration, session_id=active_session.session_id)
        session_manager.record_tool_call(
            active_session.session_id,
            name=name,
            input_summary=summary,
            status=status,
            duration=duration,
        )
        if audit_logger is not None:
            audit_logger.append("direct_action", name, {"summary": summary, "result": result})
        return CommandResult(True, json.dumps(result, indent=2) if isinstance(result, dict) else str(result))

    def _draft_email_body(person: str, topic: str) -> str:
        return f"Hi {person},\n\nI wanted to reach out about {topic}.\n\nBest,\nIMOS"

    def _latest_project_dirs() -> list[Path]:
        roots = [Path.home() / "Desktop", Path.home() / "Documents", Path.home() / "Downloads"]
        recent: list[Path] = []
        cutoff = time.time() - (30 * 24 * 60 * 60)
        for root in roots:
            if not root.exists():
                continue
            for item in root.iterdir():
                try:
                    if not item.is_dir():
                        continue
                    markers = [item / ".git", item / "package.json", item / "requirements.txt"]
                    if not any(marker.exists() for marker in markers):
                        continue
                    if item.stat().st_mtime < cutoff:
                        continue
                    recent.append(item)
                except Exception:
                    continue
        return sorted(recent, key=lambda path: path.stat().st_mtime, reverse=True)

    def _create_folder_action(name: str, location: str) -> dict:
        target = Path(location).expanduser() / name
        target.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(target))  # type: ignore[attr-defined]
        except Exception:
            pass
        return {"ok": True, "path": str(target)}

    def _move_files_action(file_type: str, src: str, dst: str) -> dict:
        source = Path(src).expanduser()
        target = Path(dst).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        pattern = f"*.{file_type.lstrip('.').lower()}"
        moved: list[str] = []
        for item in source.glob(pattern):
            destination = target / item.name
            item.replace(destination)
            moved.append(str(destination))
        return {"ok": True, "moved": moved, "count": len(moved), "destination": str(target)}

    def _add_latest_projects_action(dst: str) -> dict:
        target = Path(dst).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        moved: list[str] = []
        for item in _latest_project_dirs():
            destination = target / item.name
            if destination.exists():
                continue
            item.replace(destination)
            moved.append(str(destination))
        return {"ok": True, "moved": moved, "count": len(moved), "destination": str(target)}

    def _delete_path_action(target: str) -> dict:
        path = Path(target).expanduser()
        if not path.exists():
            return {"ok": False, "error": f"Path not found: {path}"}
        if path.is_dir():
            import shutil
            shutil.rmtree(path)
        else:
            path.unlink()
        return {"ok": True, "deleted": str(path)}

    def _power_action(kind: str) -> dict:
        commands = {
            "shutdown": "shutdown /s /t 10",
            "restart": "shutdown /r /t 10",
            "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            "lock": "rundll32.exe user32.dll,LockWorkStation",
        }
        command = commands[kind]
        return {"ok": os.system(command) == 0, "command": command}

    def _whatsapp_action(contact: str, message: str) -> dict:
        resolved = contact_book.resolve(contact)
        target = resolved.get("value") if resolved.get("ok") else _prompt_contact_resolution(contact)
        if not target:
            return {"ok": False, "error": f"Contact not found: {contact}"}
        opened = webbrowser.open(f"https://wa.me/{target}?text={quote(message)}")
        return {"ok": bool(opened), "contact": contact, "target": target}

    def _email_about_action(person: str, topic: str) -> dict:
        resolved = contact_book.resolve(person)
        destination = resolved.get("value") if resolved.get("ok") else _prompt_contact_resolution(person)
        if not destination:
            return {"ok": False, "error": f"Contact not found: {person}"}
        body = _draft_email_body(person, topic)
        return send_email_smtp(destination, f"About {topic}", body)

    def _natural_dispatch(text: str) -> CommandResult | None:
        lowered = text.strip().lower()
        if not lowered:
            return None
        if lowered == "open editor":
            return router.handlers["/ide"]("/ide")
        if lowered in {"screenshot", "take a screenshot"}:
            return _run_skill_direct("computer_control", {"action": "screenshot"}, summary="screenshot()")
        if lowered in {"what's on my screen", "whats on my screen", "what's on screen", "whats on screen"}:
            return _run_direct_action(
                "describe_screen",
                "screenshot() + describe_screen()",
                lambda: {
                    "screenshot": next((item for item in skill_registry.load_all() if item.name == "computer_control"), None).handler(
                        {"action": "screenshot"},
                        workspace=str(workspace_path),
                        memory_store=memory_store,
                        session_id=session_manager.get_active().session_id,
                        model_config=get_model_config(),
                        shell_runner=shell_runner,
                        process_manager=process_manager,
                        audit_logger=audit_logger,
                    ),
                    "description": __import__("core.vision", fromlist=["describe_screen"]).describe_screen(),
                },
            )
        if lowered.startswith("type "):
            return _run_skill_direct("computer_control", {"action": "type_text", "text": text[5:]}, summary=f"type_text({text[5:]})")
        if lowered.startswith("click "):
            payload = text[6:].strip()
            if payload.replace(" ", "").isdigit():
                parts = [part for part in payload.split() if part]
                if len(parts) == 2:
                    return _run_skill_direct("computer_control", {"action": "click", "x": int(parts[0]), "y": int(parts[1])}, summary=f"click({parts[0]}, {parts[1]})")
            return _run_skill_direct("computer_control", {"action": "click_element", "image_path": payload}, summary=f"click_element({payload})")
        if lowered.startswith("open "):
            target = text[5:].strip()
            if target.lower() in {"cursor", "windsurf", "vscode", "vs code", "visual studio code"}:
                command = "/ide " + target
                return router.handlers["/ide"](command)
            return _run_skill_direct("computer_control", {"action": "open_app", "name": target}, summary=f"open_app({target})")
        if lowered.startswith("search ") and " on google" in lowered:
            query = text[7 : lowered.rfind(" on google")].strip()
            return _run_skill_direct("browser_search", {"action": "google", "query": query}, summary=f"google({query})")
        if lowered.startswith("create folder "):
            remainder = text[len("create folder "):].strip()
            if " on " in remainder.lower():
                split_at = remainder.lower().rfind(" on ")
                name = remainder[:split_at].strip()
                location = remainder[split_at + 4 :].strip()
            else:
                name = remainder
                location = str(Path.home() / "Desktop")
            return _run_direct_action("create_folder", f"create_folder({name} on {location})", lambda: _create_folder_action(name, location))
        if lowered.startswith("create a folder ") and " on " in lowered:
            name = text[16: lowered.rfind(" on ")].strip()
            location = text[lowered.rfind(" on ") + 4 :].strip()
            return _run_direct_action("create_folder", f"create_folder({name} on {location})", lambda: _create_folder_action(name, location))
        if lowered.startswith("move all ") and " files from " in lowered and " to " in lowered:
            body = text[9:]
            file_type = body[: body.lower().find(" files from ")].strip()
            remainder = body[body.lower().find(" files from ") + 12 :]
            src = remainder[: remainder.lower().find(" to ")].strip()
            dst = remainder[remainder.lower().find(" to ") + 4 :].strip()
            return _run_direct_action("move_files", f"move_files({file_type}, {src}, {dst})", lambda: _move_files_action(file_type, src, dst))
        if lowered.startswith("add my latest projects to "):
            dst = text[len("add my latest projects to "):].strip()
            return _run_direct_action("add_latest_projects", f"add_latest_projects({dst})", lambda: _add_latest_projects_action(dst))
        if lowered.startswith("delete "):
            target = text[7:].strip()
            decision = confirm_policy.confirm_delete(target)
            if not decision.allowed:
                return CommandResult(True, decision.prompt)
            return _run_direct_action("delete_path", f"delete_path({target})", lambda: _delete_path_action(target))
        if lowered in {"shut down", "shutdown pc"}:
            return _run_direct_action("shutdown_pc", "shutdown_pc()", lambda: _power_action("shutdown"))
        if lowered == "restart":
            return _run_direct_action("restart_pc", "restart_pc()", lambda: _power_action("restart"))
        if lowered == "sleep":
            return _run_direct_action("sleep_pc", "sleep_pc()", lambda: _power_action("sleep"))
        if lowered == "lock":
            return _run_direct_action("lock_pc", "lock_pc()", lambda: _power_action("lock"))
        if lowered.startswith("set volume to "):
            level = "".join(ch for ch in text[len("set volume to "):] if ch.isdigit())
            return _run_direct_action("set_volume", f"set_volume({level})", lambda: {"ok": False, "error": "Volume control dependency not installed."})
        if lowered.startswith("play "):
            query = text[5:].strip()
            return _run_direct_action("play_media", f"play_media({query})", lambda: open_prompt_url("https://www.youtube.com/results?search_query=", query))
        if lowered.startswith("whatsapp "):
            remainder = text[9:].strip()
            if " " in remainder:
                contact, message = remainder.split(" ", 1)
                return _run_direct_action("whatsapp", f"whatsapp({contact})", lambda: _whatsapp_action(contact, message))
        if lowered.startswith("message "):
            remainder = text[8:].strip()
            if " " in remainder:
                contact, message = remainder.split(" ", 1)
                return _run_direct_action("message", f"message({contact})", lambda: _whatsapp_action(contact, message))
        if lowered.startswith("email ") and " about " in lowered:
            person = text[6: lowered.rfind(" about ")].strip()
            topic = text[lowered.rfind(" about ") + 7 :].strip()
            return _run_direct_action("email", f"email({person}, {topic})", lambda: _email_about_action(person, topic))
        if lowered.startswith("find ") and " and email " in lowered:
            return _run_direct_action("prospect_email", text, lambda: {"ok": False, "error": "Prospect flow is not fully configured yet."})
        return None

    handlers = {
            "/help": _cmd_help,
            "/exit": _cmd_exit,
            "/clear": _cmd_clear,
            "/model": _cmd_model,
            "/provider": _cmd_provider,
            "/models": _cmd_models,
            "/use": _cmd_use,
            "/claude-code": _cmd_claude_code,
            "/openai": _cmd_openai,
            "/codex": _cmd_codex,
            "/cursor": _cmd_cursor,
            "/ide": _cmd_ide,
            "/vscode": _cmd_vscode,
            "/windsurf": _cmd_windsurf,
            "/aider": _cmd_aider,
            "/continue": _cmd_continue,
            "/gemini": _cmd_gemini,
            "/email": _cmd_email,
            "/whatsapp": _cmd_whatsapp,
            "/telegram": _cmd_telegram,
            "/v0": _cmd_v0,
            "/lovable": _cmd_lovable,
            "/bolt": _cmd_bolt,
            "/doctor": _cmd_doctor,
            "/setmodel": _cmd_setmodel,
            "/pickmodel": _cmd_pickmodel,
            "/setkey": _cmd_setkey,
            "/settoken": _cmd_settoken,
            "/workspace": _cmd_workspace,
            "/cd": _cmd_cd,
            "/dashboard": _cmd_dashboard,
            "/consent": _cmd_consent,
            "/status": _cmd_status,
            "/history": _cmd_history,
            "/adapters": _cmd_adapters,
            "/wake": _cmd_wake,
            "/palette": _cmd_palette,
            "/imos": _cmd_imos,
            "/login": _cmd_login,
            "/logout": _cmd_logout,
            "/skills": _cmd_skills,
            "/workflows": _cmd_workflows,
            "/runflow": _cmd_runflow,
            "/session": _cmd_session,
            "/sessions": _cmd_sessions,
            "/tasks": _cmd_tasks,
            "/processes": _cmd_processes,
            "/audit": _cmd_audit,
            "/route": _cmd_route,
            "/git": _cmd_git,
            "/mcp": _cmd_mcp,
            "/terminal": _cmd_terminal,
            "/memory": _cmd_memory,
            "/integrations": _cmd_integrations,
            "/setup": _cmd_setup,
            "/config": _cmd_config,
            "/contact": _cmd_contact,
            "/listen": _cmd_listen,
            "/voice": _cmd_voice,
            "/autostart": _cmd_autostart,
        }

    def _wrap_handler(name: str, fn):
        def _wrapped(raw: str) -> CommandResult:
            session = session_manager.get_active()
            event_bus.tool_start(name, raw, session_id=session.session_id)
            started = time.perf_counter()
            try:
                result = fn(raw)
            except Exception as exc:
                duration = round(time.perf_counter() - started, 3)
                event_bus.tool_end(name, "error", duration, session_id=session.session_id, error=str(exc))
                session_manager.record_tool_call(session.session_id, name=name, input_summary=raw[:200], status="error", duration=duration)
                raise
            duration = round(time.perf_counter() - started, 3)
            status = "ok" if getattr(result, "handled", True) else "error"
            event_bus.tool_end(name, status, duration, session_id=session.session_id)
            session_manager.record_tool_call(session.session_id, name=name, input_summary=raw[:200], status=status, duration=duration)
            return result

        return _wrapped

    wrapped_handlers = {name: _wrap_handler(name, fn) for name, fn in handlers.items()}

    router = CommandRouter(
        wrapped_handlers,
        natural_dispatcher=_natural_dispatch,
        routing_rules=routing_rules,
    )
    gateway = ConnectAIGateway(runtime, session_manager, memory_store, router, imos_orchestrator=imos_orchestrator)
    gateway.state_root = state_root
    gateway.event_bus = event_bus
    gateway.routing_rules = routing_rules
    gateway.process_manager = process_manager
    gateway.task_manager = task_manager
    gateway.cost_tracker = cost_tracker
    gateway.mcp_runtime = mcp_runtime
    gateway.workflow_registry = workflow_registry
    gateway.skill_registry = skill_registry
    gateway.session_manager = session_manager
    gateway.memory_store = memory_store
    gateway.workspace_path = workspace_path
    gateway.cli_channel = cli_channel
    gateway.contact_book = contact_book
    gateway.consent_manager = consent_manager
    gateway.listener_service = _LISTENER_SERVICE
    gateway.voice_manager = _VOICE_MANAGER
    gateway.confirm_policy = confirm_policy
    if _LISTENER_SERVICE is not None:
        def _listener_callback(transcript: str) -> str:
            envelope = cli_channel.normalize(
                user_id="voice-user",
                text=transcript,
                session_hint=session_manager.get_active().name,
                source="voice",
            )
            result = gateway.handle_with_meta(envelope, str(workspace_path), get_model_config())
            return str(result.get("output", ""))
        _LISTENER_SERVICE.callback = _listener_callback
    global _DASHBOARD_SERVICE
    if _DASHBOARD_SERVICE is None:
        dashboard_context = DashboardContext(
            workspace=workspace_path,
            state_root=state_root,
            html_path=PROJECT_ROOT / "dashboard" / "jarvis_dashboard.html",
            session_manager=session_manager,
            memory_store=memory_store,
            audit_logger=audit_logger,
            cost_tracker=cost_tracker,
            process_manager=process_manager,
            task_manager=task_manager,
            mcp_runtime=mcp_runtime,
            workflow_registry=workflow_registry,
            skill_registry=skill_registry,
            event_bus=event_bus,
            routing_rules=routing_rules,
            gateway=gateway,
            cli_channel=cli_channel,
            model_config_getter=get_model_config,
            doctor_reporter=_doctor_output,
            listener_service=_LISTENER_SERVICE,
            contact_book=contact_book,
            consent_manager=consent_manager,
        )
        _DASHBOARD_SERVICE = DashboardService(dashboard_context, port=8766)
        _DASHBOARD_SERVICE.start(open_browser=False)
    else:
        _DASHBOARD_SERVICE.context.gateway = gateway
        _DASHBOARD_SERVICE.context.cli_channel = cli_channel
        _DASHBOARD_SERVICE.context.workspace = workspace_path
        _DASHBOARD_SERVICE.context.state_root = state_root
        _DASHBOARD_SERVICE.context.session_manager = session_manager
        _DASHBOARD_SERVICE.context.memory_store = memory_store
        _DASHBOARD_SERVICE.context.audit_logger = audit_logger
        _DASHBOARD_SERVICE.context.cost_tracker = cost_tracker
        _DASHBOARD_SERVICE.context.process_manager = process_manager
        _DASHBOARD_SERVICE.context.task_manager = task_manager
        _DASHBOARD_SERVICE.context.mcp_runtime = mcp_runtime
        _DASHBOARD_SERVICE.context.workflow_registry = workflow_registry
        _DASHBOARD_SERVICE.context.skill_registry = skill_registry
        _DASHBOARD_SERVICE.context.event_bus = event_bus
        _DASHBOARD_SERVICE.context.routing_rules = routing_rules
        _DASHBOARD_SERVICE.context.listener_service = _LISTENER_SERVICE
        _DASHBOARD_SERVICE.context.contact_book = contact_book
        _DASHBOARD_SERVICE.context.consent_manager = consent_manager
    gateway.dashboard_service = _DASHBOARD_SERVICE
    if isinstance(cfg.get("mcp"), dict) and cfg.get("mcp", {}).get("enabled"):
        existing_mcp = any(
            row.get("name") == "imos-mcp-server" and str(row.get("status")) == "running"
            for row in process_manager.list()
        )
        if not existing_mcp:
            try:
                _start_mcp_server(port=int(cfg.get("mcp", {}).get("port", 8765) or 8765), host=str(cfg.get("mcp", {}).get("host", "127.0.0.1")))
            except Exception:
                pass
    return gateway, cli_channel, skill_registry


#  Wizard helpers 

def _select(message, choices, instruction="( arrows, Enter to confirm)"):
    return inquirer.select(
        message=message,
        choices=choices,
        instruction=instruction,
        style=INQUIRER_STYLE,
        qmark="  ",
        amark="  ",
        pointer="",
    ).execute()


def _text(message, default="", completer=None):
    return inquirer.text(
        message=message,
        default=default,
        style=INQUIRER_STYLE,
        qmark="  ",
        amark="  ",
    ).execute().strip()


def _secret(message):
    return inquirer.secret(
        message=message,
        style=INQUIRER_STYLE,
        qmark="  ",
        amark="  ",
    ).execute().strip()


def _confirm(message, default=False):
    return inquirer.confirm(
        message=message,
        default=default,
        style=INQUIRER_STYLE,
        qmark="  ",
        amark="  ",
    ).execute()


def _iter_provider_model_options(preferred_provider: str | None = None):
    ordered = list(PROVIDER_MODELS.keys())
    if preferred_provider in ordered:
        ordered.remove(preferred_provider)
        ordered.insert(0, preferred_provider)
    for idx, provider in enumerate(ordered):
        if idx > 0:
            yield Separator()
        yield Separator(f" {provider.upper()} ")
        for model in PROVIDER_MODELS.get(provider, []):
            yield Choice(value=f"{provider}::{model}", name=f"{provider:<12} {model}")
        yield Choice(value=f"__custom__::{provider}", name=f"{provider:<12} Enter a custom model name")


def pick_provider_model(preferred_provider: str | None = None):
    choice = _select("Choose provider and model", list(_iter_provider_model_options(preferred_provider)))
    provider, model = choice.split("::", 1)
    if provider == "__custom__":
        provider = model
        model = _text(f"Custom model for {provider}")
    return provider, model


#  Setup wizard 

def run_setup_wizard():
    os.system("cls" if os.name == "nt" else "clear")

    console.print()
    console.print("  [bold bright_white]IMOS    Setup[/bold bright_white]")
    console.print("  [dim]Use arrow keys to navigate, Enter to confirm.[/dim]")
    console.print()

    cfg = load_config()

    #  Provider 
    console.print(Rule("  [dim]Step 1 of 6    AI Provider[/dim]", style="dim"))
    console.print()

    provider_choices = [
        Choice(value=k, name=v)
        for k, v in PROVIDER_LABELS.items()
    ]
    provider = _select("Which AI provider do you want to use?", provider_choices)
    console.print(f"  [green][/green]  {PROVIDER_LABELS[provider]}\n")

    #  Model 
    console.print(Rule("  [dim]Step 2 of 6    Model[/dim]", style="dim"))
    console.print()

    provider, chosen_model = pick_provider_model(provider)
    console.print(f"  [green][/green]  {chosen_model}\n")

    #  Credentials 
    console.print(Rule("  [dim]Step 3 of 6    Credentials[/dim]", style="dim"))
    console.print()

    model_cfg = {"provider": provider, "model": chosen_model}

    if provider in ("anthropic", "groq", "openai", "openrouter", "gemini", "huggingface", "nvidia"):
        label_map = {
            "anthropic": "Anthropic API key  (starts with sk-ant-)",
            "groq":      "Groq API key  (starts with gsk_)",
            "openai":    "OpenAI API key  (starts with sk-)",
            "openrouter":"OpenRouter API key  (starts with sk-or-)",
            "gemini":    "Google AI API key",
            "huggingface":"Hugging Face token  (starts with hf_)",
            "nvidia":    "NVIDIA NIM API key",
        }
        key = _secret(label_map.get(provider, "API key"))
        model_cfg["api_key"] = key
        console.print(f"  [green][/green]  Key saved ({key[:8]})\n" if key else "  [yellow][/yellow]  No key entered\n")

    elif provider == "ollama":
        console.print("  [dim]Ollama runs locally  no API key needed.[/dim]")
        base_url = _text("Ollama URL", default="http://localhost:11434")
        model_cfg["base_url"] = base_url
        model_cfg["api_key"] = "ollama"
        console.print(f"  [green][/green]  {base_url}\n")

    elif provider == "azure":
        endpoint = _text("Azure endpoint  (https://your-resource.openai.azure.com)")
        key = _secret("Azure API key")
        version = _text("API version", default="2024-02-01")
        model_cfg.update({"base_url": endpoint, "api_key": key, "api_version": version})
        console.print(f"  [green][/green]  Azure configured\n")

    elif provider == "bedrock":
        key_id = _text("AWS Access Key ID")
        secret = _secret("AWS Secret Access Key")
        region = _text("AWS Region", default="us-east-1")
        model_cfg.update({"aws_access_key_id": key_id, "aws_secret_access_key": secret, "aws_region": region})
        console.print(f"  [green][/green]  Bedrock configured ({region})\n")

    elif provider == "gcp":
        project_id = _text("GCP Project ID")
        location = _text("GCP Location", default="us-east5")
        model_cfg.update({"project_id": project_id, "location": location, "api_key": ""})
        console.print(f"  [green][/green]  GCP configured ({project_id})\n")

    cfg["model"] = model_cfg

    #  Deploy tokens 
    console.print(Rule("  [dim]Step 4 of 6    Deploy tokens  (optional)[/dim]", style="dim"))
    console.print("  [dim]Leave blank to skip. These let IMOS deploy your projects.[/dim]\n")

    cfg.setdefault("tokens", {})
    for svc, label in [("vercel", "Vercel token"), ("netlify", "Netlify token"), ("github", "GitHub personal access token")]:
        val = _text(f"{label}  (Enter to skip)")
        if val:
            cfg["tokens"][svc] = val
            console.print(f"  [green][/green]  {svc} saved")
    console.print()

    #  Messaging 
    console.print(Rule("  [dim]Step 5 of 6    Messaging  (optional)[/dim]", style="dim"))
    console.print("  [dim]IMOS can notify you via Telegram or Slack.[/dim]\n")

    cfg.setdefault("messaging", {})
    tg = _text("Telegram bot token  (Enter to skip)")
    if tg:
        chat_id = _text("Telegram chat ID")
        cfg["messaging"]["telegram"] = {"token": tg, "chat_id": chat_id}
        console.print("  [green][/green]  Telegram configured")

    slack = _text("Slack webhook URL  (Enter to skip)")
    if slack:
        cfg["messaging"]["slack"] = {"webhook": slack}
        console.print("  [green][/green]  Slack configured")
    console.print()

    #  Workspace 
    console.print(Rule("  [dim]Step 6 of 6    Workspace[/dim]", style="dim"))
    console.print("  [dim]Default folder where IMOS reads and writes files.[/dim]\n")

    default_ws = str(Path.home() / "imos_workspace")
    workspace = _text("Workspace path", default=default_ws)
    Path(workspace).mkdir(parents=True, exist_ok=True)
    cfg["workspace"] = workspace
    console.print(f"  [green][/green]  {workspace}\n")

    #  Save 
    save_config(cfg)

    console.print(Rule("  [green]Setup complete[/green]", style="green"))
    console.print(f"\n  Config    [dim]{CONFIG_PATH}[/dim]")
    console.print(f"  Provider    [green]{provider}[/green]")
    console.print(f"  Model       [green]{chosen_model}[/green]")
    console.print(f"  Workspace   [green]{workspace}[/green]")
    console.print()
    input("  Press Enter to start chatting")
    return cfg


#  Models table 

def show_models_table(model_config):
    t = Table(box=box.SIMPLE, show_header=True, header_style="bold dim white", padding=(0, 2))
    t.add_column("Provider", style="dim white", width=12)
    t.add_column("Model", style="white", width=46)
    t.add_column("", width=10)
    active = model_config.get("provider", "")
    cfg = load_config()
    for provider in list_providers():
        stored = cfg.get("model", {}) if cfg.get("model", {}).get("provider") == provider else {}
        model_name = stored.get("model", get_provider_defaults(provider).get("model", ""))
        if provider == "bedrock":
            ready = bool(stored.get("aws_access_key_id"))
        elif provider == "gcp":
            ready = bool(stored.get("project_id"))
        else:
            ready = bool(stored.get("api_key", "").strip())
        if provider == active:
            status = "[green] active[/green]"
        elif ready:
            status = "[dim] ready[/dim]"
        else:
            status = "[dim]  [/dim]"
        t.add_row(provider, model_name, status)
    console.print(t)


#  Bottom toolbar 

def toolbar(model_config, workspace):
    p = model_config.get("provider", "?")
    m = model_config.get("model", "?")
    ws = str(workspace)
    if len(ws) > 40:
        ws = "" + ws[-38:]
    return HTML(f'<style bg="#111111" fg="#444444">  {p}/{m}   {ws}  </style>')


def _git_branch(workspace: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        branch = (result.stdout or "").strip()
        return branch if result.returncode == 0 and branch else ""
    except Exception:
        return ""


def _prompt_message(workspace: str) -> HTML:
    directory = Path(workspace).name or str(workspace)
    branch = _git_branch(workspace)
    header = directory if not branch else f"{directory} ({branch})"
    return HTML(f'<style fg="#8f8f8f">{header}</style>\n<style fg="#f97316">&gt;</style> ')


class ShellEventRenderer:
    def __init__(self):
        self._label_printed = False
        self._streaming = False

    def on_event(self, event) -> None:
        return None

    def emit_text(self, token: str) -> None:
        if not self._streaming:
            self._streaming = True
        if not self._label_printed:
            sys.stdout.write(f"{ORANGE}IMOS:{RESET} {WHITE}")
            self._label_printed = True
        sys.stdout.write(_plain(token))
        sys.stdout.flush()

    def finish_text(self) -> None:
        if self._streaming:
            sys.stdout.write(f"{RESET}\n")
            sys.stdout.flush()
        self._streaming = False
        self._label_printed = False


#  Main 

def main():
    if len(sys.argv) > 1:
        top_command = sys.argv[1].strip().lower()
        if top_command == "--setup":
            cfg = load_config()
            workspace = cfg.get("workspace", os.getcwd())
            force_run_setup_wizard(PROJECT_ROOT, workspace)
            return
        if top_command == "--doctor":
            cfg = load_config()
            workspace = cfg.get("workspace", os.getcwd())
            build_gateway(workspace)
            import asyncio
            from imos.doctor import doctor_report

            if _DASHBOARD_SERVICE is not None:
                print(
                    asyncio.run(
                        doctor_report(
                            session_manager=_DASHBOARD_SERVICE.context.session_manager,
                            dashboard_service=_DASHBOARD_SERVICE,
                            routing_rules=_DASHBOARD_SERVICE.context.routing_rules,
                            event_bus=_DASHBOARD_SERVICE.context.event_bus,
                            process_manager=_DASHBOARD_SERVICE.context.process_manager,
                            listener_service=getattr(_DASHBOARD_SERVICE.context, "listener_service", None),
                            consent_manager=getattr(_DASHBOARD_SERVICE.context, "consent_manager", None),
                            contact_book=getattr(_DASHBOARD_SERVICE.context, "contact_book", None),
                            voice_manager=_VOICE_MANAGER,
                            state_root=getattr(_DASHBOARD_SERVICE.context, "state_root", None),
                        )
                    )
                )
            else:
                print(asyncio.run(doctor_report()))
            return
        if top_command == "imos":
            from imos.cli import main as imos_main

            imos_main(sys.argv[2:])
            return
        if top_command == "--imos":
            from imos.orchestrator import IMOSOrchestrator
            from imos.registry import AdapterRegistry

            prompt = " ".join(sys.argv[2:]).strip()
            if not prompt:
                print("Usage: python ai_assistant.py --imos \"<prompt>\"")
                return

            async def _run_imos():
                registry = AdapterRegistry()
                await registry.auto_discover()
                orchestrator = IMOSOrchestrator(registry)
                result = await orchestrator.run(prompt)
                print(result.final_response)

            import asyncio

            asyncio.run(_run_imos())
            return
        if top_command == "dashboard":
            cfg = load_config()
            workspace = cfg.get("workspace", os.getcwd())
            build_gateway(workspace)
            if _DASHBOARD_SERVICE is not None:
                _open_dashboard_url()
            return
        if top_command == "voice":
            cfg = load_config()
            workspace = cfg.get("workspace", os.getcwd())
            build_gateway(workspace)
            if _VOICE_MANAGER is not None:
                result = _VOICE_MANAGER.speak(_VOICE_MANAGER.test_phrase())
                print(json.dumps(result, indent=2))
            return
        if top_command == "login":
            run_login()
            return
        if top_command == "logout":
            run_logout()
            return

    cfg = load_config()
    workspace = sys.argv[1] if len(sys.argv) > 1 else cfg.get("workspace", os.getcwd())
    ensure_first_run_setup(PROJECT_ROOT, workspace)
    cfg = load_config()
    workspace = cfg.get("workspace", workspace)
    model_config = get_model_config()
    gateway, cli_channel, _skill_registry = build_gateway(workspace)
    event_bus = gateway.event_bus

    os.system("cls" if os.name == "nt" else "clear")
    render_home_screen(model_config, workspace)

    while True:
        renderer = ShellEventRenderer()
        subscription = event_bus.subscribe(renderer.on_event)
        try:
            user_input = input(_imos_prompt()).strip()
        except (EOFError, KeyboardInterrupt):
            event_bus.unsubscribe(subscription)
            print()
            break

        if not user_input:
            event_bus.unsubscribe(subscription)
            continue

        active_session = gateway.session_manager.get_active()
        envelope = cli_channel.normalize(user_id="local-user", text=user_input, session_hint=active_session.name)
        text_chunks = {"count": 0}
        is_command = user_input.startswith("/")

        def _emit_delta(chunk: str) -> None:
            text_chunks["count"] += 1
            if not is_command:
                renderer.emit_text(chunk)

        try:
            result_meta = gateway.handle_with_meta(envelope, workspace, model_config, on_text_delta=_emit_delta)
        except Exception as exc:
            renderer.finish_text()
            event_bus.unsubscribe(subscription)
            print(_plain(exc))
            continue
        finally:
            renderer.finish_text()
        result = CommandResult(
            handled=True,
            output=str(result_meta.get("output", "")),
            should_exit=bool(result_meta.get("should_exit", False)),
            updated_model_config=result_meta.get("updated_model_config"),
            updated_workspace=result_meta.get("updated_workspace"),
        )
        if result.updated_model_config:
            model_config = result.updated_model_config
        if result.updated_workspace:
            workspace = result.updated_workspace
            gateway, cli_channel, _skill_registry = build_gateway(workspace)
            event_bus = gateway.event_bus
        if result.output and text_chunks["count"] == 0:
            if is_command:
                _print_command_output(result.output)
            else:
                _print_assistant_output(result.output)
        if result.should_exit:
            event_bus.unsubscribe(subscription)
            break
        event_bus.unsubscribe(subscription)
        print()


if __name__ == "__main__":
    main()
