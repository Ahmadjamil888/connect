import os
import sys
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from InquirerPy import get_style, inquirer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator
from prompt_toolkit import PromptSession
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
from agents.orchestrator import run_orchestrator
from config.config import (
    get_model_config, load_config, save_config, save_model_config,
    list_providers, get_provider_defaults, is_configured, CONFIG_PATH,
    PROVIDER_DEFAULTS,
)

console = Console(highlight=False)

HISTORY_PATH = Path.home() / ".connectai" / "history"

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
    "questionmark":  "fg:#00ff88 bold",
    "answermark":    "fg:#00ff88 bold",
    "answer":        "fg:#00ff88 bold",
    "input":         "fg:#ffffff",
    "question":      "fg:#ffffff bold",
    "instruction":   "fg:#555555",
    "long_instruction": "fg:#555555",
    "pointer":       "fg:#00ff88 bold",
    "checkbox":      "fg:#00ff88",
    "separator":     "fg:#333333",
    "skipped":       "fg:#555555",
    "validator":     "fg:#ff4444",
    "marker":        "fg:#00ff88 bold",
    "fuzzy_prompt":  "fg:#ffffff",
    "fuzzy_info":    "fg:#555555",
    "fuzzy_border":  "fg:#333333",
    "fuzzy_match":   "fg:#00ff88",
})

PROMPT_STYLE = Style.from_dict({
    "bottom-toolbar": "bg:#111111 fg:#555555",
    "prompt":         "fg:#00ff88 bold",
})

WELCOME_ART = [
    "   _________  _   _ _   _ _   _ ______ _____ _______     ___  _____ ",
    "  / ____/ _ \\| \\ | | \\ | | \\ | |  ____/ ____|__   __|   / _ \\|_   _|",
    " | |   | | | |  \\| |  \\| |  \\| | |__ | |       | |     / /_\\ \\ | |  ",
    " | |   | | | | . ` | . ` | . ` |  __|| |       | |     |  _  | | |  ",
    " | |___| |_| | |\\  | |\\  | |\\  | |___| |____    | |     | | | |_| |_ ",
    "  \\_____\\___/|_| \\_|_| \\_|_| \\_|______\\_____|   |_|     \\_| |_/_____|",
]

HELP = """
  [bold bright_white]Commands[/bold bright_white]

  [green]/setup[/green]              re-run the setup wizard
  [green]/model[/green]              show current model config
  [green]/provider[/green]           show active provider and model
  [green]/models[/green]             list all providers and status
  [green]/use[/green] [dim]<provider>[/dim]       switch provider interactively
  [green]/setmodel[/green] [dim]<model>[/dim]     set a new model name for current provider
  [green]/pickmodel[/green]         pick any provider/model pair interactively
  [green]/setkey[/green] [dim]<provider> <key>[/dim]  set API key directly
  [green]/settoken[/green] [dim]<svc> <tok>[/dim]    set deploy token (vercel/netlify/github)
  [green]/skills[/green]            list installed skills
  [green]/workflows[/green]         list YAML workflows
  [green]/runflow[/green] [dim]<name>[/dim]       run a workflow by name
  [green]/sessions[/green]          list local gateway sessions
  [green]/tasks[/green]             list long-running task records
  [green]/processes[/green]         list managed background processes
  [green]/audit[/green]             show recent audit log entries
  [green]/git[/green] [dim]status|branch|commit|diff|log[/dim]
  [green]/mcp[/green]               list MCP servers and discovered tools
  [green]/terminal[/green]          list managed terminal sessions
  [green]/memory[/green] [dim]<query>[/dim]       search local memory index
  [green]/config[/green] [dim]get <path>[/dim]    inspect YAML config
  [green]/config[/green] [dim]set <path> <json>[/dim] update YAML config path
  [green]/integrations[/green]      show configured integration keys
  [green]/workspace[/green]          show workspace path
  [green]/cd[/green] [dim]<path>[/dim]            change workspace
  [green]/dashboard[/green]         launch local dashboard
  [green]connect voice[/green]      launch the Jarvis voice loop
  [green]/login[/green]             run Clerk login flow
  [green]/logout[/green]            clear Clerk session
  [green]/clear[/green]             clear screen
  [green]/help[/green]              show this
  [green]/exit[/green]              quit
"""


def _home_title():
    title = Text()
    for line in WELCOME_ART:
        title.append(line + "\n", style="bold bright_cyan")
    return title


def render_home_screen(model_config, workspace):
    provider = model_config.get("provider", "?")
    model = model_config.get("model", "?")
    welcome = Text()
    welcome.append("* ", style="bold #ff9b73")
    welcome.append("Welcome to ", style="bold white")
    welcome.append("Connect AI // JARVIS", style="bold bright_cyan")

    console.print()
    console.print(
        Panel(
            welcome,
            border_style="#ff9b73",
            padding=(0, 2),
            expand=False,
            style="on #111111",
        )
    )
    console.print(Align.left(_home_title()))
    console.print(f"  [bright_cyan]{provider}/{model}[/bright_cyan]")
    console.print(f"  [dim]{workspace}[/dim]")
    console.print("  [dim]Type /help for commands[/dim]")
    console.print()


def _workspace_root_from_cfg(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    return Path(cfg.get("workspace", str(Path.home() / "connectai_workspace")))


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
  <title>Connect AI Dashboard</title>
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
  <div class="welcome"><span class="mark">*</span>Welcome to <strong>Connect AI</strong></div>
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
  <title>Connect AI Dashboard</title>
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
      <div class="brand">* Welcome to <strong>Connect AI</strong></div>
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
    cfg = load_config()
    workspace = _workspace_root_from_cfg(cfg)
    model_config = get_model_config()
    auth = _auth_manager_for_workspace(workspace)
    if not ensure_authenticated(workspace):
        return
    gateway, cli_channel, skill_registry = build_gateway(str(workspace))
    state_root = workspace / ".connectai"
    session_manager = ConnectSessionManager(state_root / "sessions")
    memory_store = ConnectMemoryStore(state_root / "memory")
    audit_logger = AuditLogger(state_root / "audit")
    cost_tracker = CostTracker(state_root / "cost")
    approval_policy = ApprovalPolicy(load_config, audit_logger)
    shell_runner = ShellRunner(state_root / "commands", audit_logger, approval_policy)
    process_manager = ProcessRegistry(state_root / "processes", audit_logger)
    task_manager = TaskManager(state_root / "tasks", audit_logger)
    terminal_manager = TerminalSessionManager(state_root / "terminals", audit_logger)
    mcp_runtime = MCPRuntime()
    for row in load_config().get("mcp", {}).get("servers", []):
        try:
            mcp_runtime.register_server(MCPServer(name=row["name"], url=row["url"], enabled=bool(row.get("enabled", True))))
        except Exception:
            continue
    workflow_registry = WorkflowRegistry(workspace)

    class Handler(BaseHTTPRequestHandler):
        def _run_skill(self, name: str, args: dict):
            skill = next((item for item in skill_registry.load_all() if item.name == name), None)
            if skill is None:
                return {"ok": False, "error": f"Unknown skill: {name}"}
            try:
                return skill.handler(
                    args,
                    workspace=str(workspace),
                    memory_store=memory_store,
                    session_id="dashboard",
                    model_config=get_model_config(),
                    shell_runner=shell_runner,
                    process_manager=process_manager,
                    audit_logger=audit_logger,
                )
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        def _send_json(self, payload: dict, status: int = 200):
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_html(self, html: str, status: int = 200):
            raw = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_sse_headers(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

        def _send_sse_event(self, payload: dict):
            raw = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
            self.wfile.write(raw)
            self.wfile.flush()

        def _read_json(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except Exception:
                return {}

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/status":
                self._send_json({
                    "provider": model_config.get("provider", ""),
                    "model": model_config.get("model", ""),
                    "workspace": str(workspace),
                    "auth": auth.current_user(),
                    "providers": list_providers(),
                })
                return
            if parsed.path == "/api/skills":
                self._send_json({
                    "items": [
                        {
                            "name": item.name,
                            "description": item.description,
                            "source": item.source,
                        }
                        for item in skill_registry.load_all()
                    ]
                })
                return
            if parsed.path == "/api/workflows":
                self._send_json({"items": workflow_registry.list_workflows()})
                return
            if parsed.path == "/api/sessions":
                self._send_json({
                    "items": [
                        {
                            "session_id": item.session_id,
                            "session_key": item.session_key,
                            "title": item.title,
                            "channel": item.channel,
                            "message_count": item.message_count,
                            "updated_at": item.updated_at,
                        }
                        for item in session_manager.list_sessions()
                    ]
                })
                return
            if parsed.path.startswith("/api/sessions/"):
                requested = parsed.path.rsplit("/", 1)[-1]
                if requested == "default":
                    items = []
                else:
                    items = session_manager.history_by_id(requested, limit=200)
                self._send_json({"items": items})
                return
            if parsed.path == "/api/memory":
                self._send_json({"items": memory_store.recent_entries(40)})
                return
            if parsed.path == "/api/tasks":
                self._send_json({"items": task_manager.list(50)})
                return
            if parsed.path == "/api/processes":
                items = process_manager.list()
                for item in items:
                    item["log_tail"] = process_manager.tail_log(item["process_id"], 1200)
                self._send_json({"items": items})
                return
            if parsed.path == "/api/terminals":
                self._send_json({"items": terminal_manager.list()})
                return
            if parsed.path == "/api/mcp":
                self._send_json({"servers": mcp_runtime.list_servers(), "tools": mcp_runtime.list_tools()})
                return
            if parsed.path == "/api/audit":
                self._send_json({"items": audit_logger.tail(80)})
                return
            if parsed.path == "/api/cost":
                self._send_json(cost_tracker.summary())
                return
            if parsed.path == "/api/weather":
                self._send_json(self._run_skill("weather", {}))
                return
            if parsed.path == "/api/news":
                self._send_json(self._run_skill("news", {"limit": 4}))
                return
            if parsed.path == "/api/stream":
                self._send_sse_headers()
                path = audit_logger.path
                path.touch(exist_ok=True)
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    handle.seek(0, os.SEEK_END)
                    try:
                        while True:
                            line = handle.readline()
                            if not line:
                                time.sleep(0.4)
                                continue
                            try:
                                payload = json.loads(line)
                            except Exception:
                                continue
                            if payload.get("kind") in {"command_output", "process_output", "command_start", "command_end", "process_start", "process_end", "task_create", "task_complete"}:
                                self._send_sse_event(payload)
                    except (BrokenPipeError, ConnectionResetError):
                        return
            if parsed.path == "/api/integrations":
                cfg_local = load_config()
                publishable, secret = _clerk_env()
                self._send_json(
                    {
                        "tokens": cfg_local.get("tokens", {}),
                        "messaging": cfg_local.get("messaging", {}),
                        "clerk_publishable_key": bool(publishable),
                        "clerk_secret_key": bool(secret),
                    }
                )
                return
            self._send_html(_jarvis_dashboard_html())

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/chat":
                payload = self._read_json()
                text = str(payload.get("text", "")).strip()
                if not text:
                    self._send_json({"ok": False, "error": "Missing text"}, status=400)
                    return
                session_id = str(payload.get("session_id", "")).strip()
                session_hint = ""
                if session_id and session_manager.get_by_id(session_id):
                    existing = session_manager.get_by_id(session_id)
                    session_hint = existing.session_key if existing else ""
                envelope = cli_channel.normalize(
                    user_id="dashboard-user",
                    text=text,
                    session_hint=session_hint,
                    source="dashboard",
                )
                result = gateway.handle(envelope, str(workspace), get_model_config())
                selected_id = session_id
                if session_hint:
                    existing = session_manager.get_or_create(session_hint, "cli", "dashboard-user")
                    selected_id = existing.session_id
                elif session_manager.list_sessions():
                    selected_id = session_manager.list_sessions()[-1].session_id
                self._send_json({"ok": True, "response": result.output, "session_id": selected_id})
                return
            if parsed.path == "/api/chat/stream":
                payload = self._read_json()
                text = str(payload.get("text", "")).strip()
                if not text:
                    self.send_response(400)
                    self.end_headers()
                    return
                session_id = str(payload.get("session_id", "")).strip()
                session_hint = ""
                if session_id and session_manager.get_by_id(session_id):
                    existing = session_manager.get_by_id(session_id)
                    session_hint = existing.session_key if existing else ""
                envelope = cli_channel.normalize(
                    user_id="dashboard-user",
                    text=text,
                    session_hint=session_hint,
                    source="dashboard",
                )
                self._send_sse_headers()

                def emit_token(token: str):
                    self._send_sse_event({"type": "token", "text": token})

                try:
                    result = gateway.handle_with_meta(envelope, str(workspace), get_model_config(), on_text_delta=emit_token)
                    selected_id = session_id
                    if session_hint:
                        existing = session_manager.get_or_create(session_hint, "cli", "dashboard-user")
                        selected_id = existing.session_id
                    elif session_manager.list_sessions():
                        selected_id = session_manager.list_sessions()[-1].session_id
                    self._send_sse_event({
                        "type": "done",
                        "response": result.get("output", ""),
                        "session_id": selected_id,
                        "usage": result.get("usage", {}),
                        "cost": cost_tracker.summary(),
                    })
                except Exception as exc:
                    self._send_sse_event({"type": "error", "error": str(exc)})
                return
            if parsed.path == "/api/workflows/run":
                payload = self._read_json()
                name = str(payload.get("name", "")).strip()
                if not name:
                    self._send_json({"ok": False, "error": "Missing workflow name"}, status=400)
                    return
                try:
                    result = workflow_registry.run(
                        name,
                        tool_executor=lambda tool_name, args: next(
                            item for item in skill_registry.load_all() if item.name == tool_name
                        ).handler(args, workspace=str(workspace), memory_store=memory_store, session_id="workflow", model_config=get_model_config()),
                        sender=lambda content: content,
                    )
                    self._send_json({"ok": True, "result": result})
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path == "/api/model":
                payload = self._read_json()
                provider = str(payload.get("provider", "")).strip().lower()
                model = str(payload.get("model", "")).strip()
                if not provider or not model:
                    self._send_json({"ok": False, "error": "Missing provider or model"}, status=400)
                    return
                cfg_local = load_config()
                selected = get_provider_defaults(provider)
                existing = cfg_local.get("model", {})
                if existing.get("provider") == provider:
                    selected.update(existing)
                selected["provider"] = provider
                selected["model"] = model
                cfg_local["model"] = selected
                save_config(cfg_local)
                self._send_json({"ok": True})
                return
            if parsed.path == "/api/terminal/open":
                payload = self._read_json()
                cwd = str(payload.get("cwd", workspace)).strip() or str(workspace)
                self._send_json(terminal_manager.open(cwd))
                return
            if parsed.path == "/api/terminal/read":
                payload = self._read_json()
                self._send_json(terminal_manager.read(str(payload.get("session_id", "")).strip()))
                return
            if parsed.path == "/api/terminal/write":
                payload = self._read_json()
                self._send_json(terminal_manager.write(str(payload.get("session_id", "")).strip(), str(payload.get("data", ""))))
                return
            if parsed.path == "/api/terminal/close":
                payload = self._read_json()
                self._send_json(terminal_manager.close(str(payload.get("session_id", "")).strip()))
                return
            if parsed.path == "/api/mcp/register":
                payload = self._read_json()
                name = str(payload.get("name", "")).strip()
                url = str(payload.get("url", "")).strip()
                if not name or not url:
                    self._send_json({"ok": False, "error": "Missing MCP name or url"}, status=400)
                    return
                server = MCPServer(name=name, url=url, enabled=True)
                try:
                    mcp_runtime.register_server(server)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                    return
                cfg_local = load_config()
                cfg_local.setdefault("mcp", {}).setdefault("servers", [])
                cfg_local["mcp"]["servers"] = [row for row in cfg_local["mcp"]["servers"] if row.get("name") != name]
                cfg_local["mcp"]["servers"].append({"name": name, "url": url, "enabled": True})
                save_config(cfg_local)
                self._send_json({"ok": True})
                return
            self._send_json({"ok": False, "error": "Not found"}, status=404)

        def log_message(self, format, *args):
            return

    host = "127.0.0.1"
    preferred_port = 18890
    try:
        server = ThreadingHTTPServer((host, preferred_port), Handler)
    except OSError:
        server = ThreadingHTTPServer((host, 0), Handler)
    url = f"http://{host}:{server.server_address[1]}/"
    console.print(f"  [bright_cyan]Dashboard[/bright_cyan]  [dim]{url}[/dim]")
    console.print("  [dim]Press Ctrl+C to stop the dashboard server.[/dim]\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n  [dim]dashboard stopped[/dim]")
    finally:
        server.server_close()


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


def _save_provider(provider: str, preserve_model: bool = False) -> dict:
    cfg = load_config()
    defaults = get_provider_defaults(provider)
    current = cfg.get("model", {}) if preserve_model else {}
    merged = dict(defaults)
    merged.update(current)
    merged["provider"] = provider
    if not preserve_model:
        merged["model"] = defaults.get("model", merged.get("model", ""))
    cfg["model"] = merged
    save_config(cfg)
    return get_model_config()


def _save_model_name(model_name: str) -> dict:
    cfg = load_config()
    current = get_model_config()
    current["model"] = model_name
    cfg["model"] = current
    save_config(cfg)
    return get_model_config()


def build_gateway(workspace: str):
    workspace_path = Path(workspace)
    state_root = workspace_path / ".connectai"
    session_manager = ConnectSessionManager(state_root / "sessions")
    memory_store = ConnectMemoryStore(state_root / "memory")
    audit_logger = AuditLogger(state_root / "audit")
    cost_tracker = CostTracker(state_root / "cost")
    approval_policy = ApprovalPolicy(load_config, audit_logger)
    shell_runner = ShellRunner(state_root / "commands", audit_logger, approval_policy)
    process_manager = ProcessRegistry(state_root / "processes", audit_logger)
    task_manager = TaskManager(state_root / "tasks", audit_logger)
    terminal_manager = TerminalSessionManager(state_root / "terminals", audit_logger)
    mcp_runtime = MCPRuntime()
    for row in load_config().get("mcp", {}).get("servers", []):
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
    )
    cli_channel = CLIChannel()

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

    def _cmd_help(_raw: str) -> CommandResult:
        return CommandResult(True, HELP)

    def _cmd_exit(_raw: str) -> CommandResult:
        return CommandResult(True, should_exit=True)

    def _cmd_clear(_raw: str) -> CommandResult:
        os.system("cls" if os.name == "nt" else "clear")
        render_home_screen(get_model_config(), workspace)
        return CommandResult(True, "")

    def _cmd_model(_raw: str) -> CommandResult:
        safe = dict(get_model_config())
        for key in ("api_key", "aws_secret_access_key"):
            if safe.get(key):
                safe[key] = str(safe[key])[:8]
        return CommandResult(True, json.dumps(safe, indent=2))

    def _cmd_provider(_raw: str) -> CommandResult:
        cfg = get_model_config()
        return CommandResult(True, f"{cfg.get('provider')}/{cfg.get('model')}")

    def _cmd_models(_raw: str) -> CommandResult:
        show_models_table(get_model_config())
        return CommandResult(True, "")

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
        if not ensure_authenticated(workspace_path):
            return CommandResult(True, "")
        launch_dashboard()
        return CommandResult(True, "")

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

    def _cmd_mcp(_raw: str) -> CommandResult:
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
        run_setup_wizard()
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

    router = CommandRouter(
        {
            "/help": _cmd_help,
            "/exit": _cmd_exit,
            "/clear": _cmd_clear,
            "/model": _cmd_model,
            "/provider": _cmd_provider,
            "/models": _cmd_models,
            "/use": _cmd_use,
            "/setmodel": _cmd_setmodel,
            "/pickmodel": _cmd_pickmodel,
            "/setkey": _cmd_setkey,
            "/settoken": _cmd_settoken,
            "/workspace": _cmd_workspace,
            "/cd": _cmd_cd,
            "/dashboard": _cmd_dashboard,
            "/login": _cmd_login,
            "/logout": _cmd_logout,
            "/skills": _cmd_skills,
            "/workflows": _cmd_workflows,
            "/runflow": _cmd_runflow,
            "/sessions": _cmd_sessions,
            "/tasks": _cmd_tasks,
            "/processes": _cmd_processes,
            "/audit": _cmd_audit,
            "/git": _cmd_git,
            "/mcp": _cmd_mcp,
            "/terminal": _cmd_terminal,
            "/memory": _cmd_memory,
            "/integrations": _cmd_integrations,
            "/setup": _cmd_setup,
            "/config": _cmd_config,
        }
    )
    gateway = ConnectAIGateway(runtime, session_manager, memory_store, router)
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
    console.print("  [bold bright_white]Connect AI    Setup[/bold bright_white]")
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
    console.print("  [dim]Leave blank to skip. These let Connect AI deploy your projects.[/dim]\n")

    cfg.setdefault("tokens", {})
    for svc, label in [("vercel", "Vercel token"), ("netlify", "Netlify token"), ("github", "GitHub personal access token")]:
        val = _text(f"{label}  (Enter to skip)")
        if val:
            cfg["tokens"][svc] = val
            console.print(f"  [green][/green]  {svc} saved")
    console.print()

    #  Messaging 
    console.print(Rule("  [dim]Step 5 of 6    Messaging  (optional)[/dim]", style="dim"))
    console.print("  [dim]Connect AI can notify you via Telegram or Slack.[/dim]\n")

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
    console.print("  [dim]Default folder where Connect AI reads and writes files.[/dim]\n")

    default_ws = str(Path.home() / "connectai_workspace")
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


#  Main 

def main():
    if len(sys.argv) > 1:
        top_command = sys.argv[1].strip().lower()
        if top_command == "--doctor":
            import asyncio
            from imos.doctor import doctor_report

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
            launch_dashboard()
            return
        if top_command == "voice":
            from jarvis import voice_loop
            voice_loop()
            return
        if top_command == "login":
            run_login()
            return
        if top_command == "logout":
            run_logout()
            return

    if not is_configured():
        run_setup_wizard()

    cfg = load_config()
    workspace = sys.argv[1] if len(sys.argv) > 1 else cfg.get("workspace", os.getcwd())
    model_config = get_model_config()
    if not ensure_authenticated(Path(workspace)):
        return
    gateway, cli_channel, _skill_registry = build_gateway(workspace)

    os.system("cls" if os.name == "nt" else "clear")
    render_home_screen(model_config, workspace)

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    session = PromptSession(
        history=FileHistory(str(HISTORY_PATH)),
        style=PROMPT_STYLE,
    )

    while True:
        try:
            user_input = session.prompt(
                HTML("<prompt>></prompt> "),
                bottom_toolbar=lambda: toolbar(model_config, workspace),
                refresh_interval=0.5,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]bye[/dim]")
            break

        if not user_input:
            continue

        envelope = cli_channel.normalize(user_id="local-user", text=user_input)
        console.print()
        result = gateway.handle(envelope, workspace, model_config)
        if result.updated_model_config:
            model_config = result.updated_model_config
        if result.updated_workspace:
            workspace = result.updated_workspace
            gateway, cli_channel, _skill_registry = build_gateway(workspace)
        if result.output:
            if result.output.lstrip().startswith("{"):
                try:
                    console.print_json(result.output)
                except Exception:
                    console.print(result.output)
            else:
                console.print(result.output)
        if result.should_exit:
            console.print("\n  [dim]bye[/dim]")
            break
        console.print()


if __name__ == "__main__":
    main()
