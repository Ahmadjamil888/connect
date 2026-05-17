# IMOS

IMOS has evolved into a controlled operator system for teams that need AI sessions, routing, dashboard visibility, and real execution to stay aligned from prompt to delivery across models, IDEs, apps, browsers, and the local machine.

That stack breaks the moment work spans multiple tools, people, long-running tasks, and machine-level actions. IMOS is the coordination layer that keeps context persistent, execution visible, permissions explicit, and handoffs operational instead of manual.

One prompt can be decomposed into multiple subtasks, routed across models, IDEs, messaging apps, Git providers, browser automation, payments, meeting platforms, OS tooling, and generic REST services, then synthesized back into one response under one shared runtime state.

## Practical example

One launch, multiple models, IDEs, apps, browser actions, and local machine controls, all under one shared operational state:

1. A product lead starts an IMOS session with a shipping goal.
2. The router sends code generation to one model, research to another, and editor work to the best available IDE adapter.
3. Browser automation logs into a service, collects live state, and returns it to the same session context.
4. Local machine controls open apps, manage files, run commands, or capture screenshots with explicit permission boundaries.
5. Long-running tasks remain visible in the dashboard with audit history, handoff state, and resumable context.
6. Final output lands back in one operational thread instead of being split across disconnected tools.

## How IMOS works

1. A user prompt enters the IMOS orchestrator.
2. The router decomposes the request into structured subtasks.
3. Subtasks are assigned to the best available adapters based on capability, health, and preferences.
4. Independent work runs in parallel, dependency chains run sequentially.
5. Results are synthesized into one final answer and optionally pushed to configured messaging outputs.
6. History, audit logs, and project context are persisted under `~/.imos/`.

Core files:

- `imos/adapters/base.py`: canonical adapter protocol
- `imos/models.py`: IMOS task/result dataclasses
- `imos/config.py`: YAML and env-backed config loading
- `imos/registry.py`: adapter registration and autodiscovery
- `imos/router.py`: prompt decomposition and adapter routing
- `imos/orchestrator.py`: execution engine
- `imos/synthesizer.py`: final result synthesis
- `imos/mcp_server.py`: MCP server for IDE integrations
- `imos/cli.py`: CLI entrypoint

## Quick start

10-minute flow:

1. Install dependencies: `pip install -r requirements.txt`
2. Install browser runtime: `playwright install chromium`
3. Create IMOS config home: `python -c "from imos.config import ensure_default_files; ensure_default_files()"`
4. Copy `.env.example` to `.env` and add at least one model provider key.
5. Add three adapters, for example:
   - model: `imos adapters add model openai`
   - ide: `imos adapters add ide cursor`
   - messaging: `imos adapters add messaging slack`
6. Install editor MCP configs if needed: `imos mcp install`
7. Check health: `connect --doctor`
8. Run the first orchestration:
   - `imos run "Write a FastAPI hello world, save it, commit it, and send me the result on Slack"`

## Config

IMOS stores config in:

- `~/.imos/connections.yaml`
- `~/.imos/imos_settings.yaml`
- `~/.imos/context.json`

Default `connections.yaml` shape:

```yaml
connections: []
settings:
  default_model: auto
  parallel_execution: true
  max_concurrent_tasks: 10
  result_synthesis_model: anthropic
  log_level: info
  dashboard_port: 8765
  enable_payments: false
  enable_os_control: true
```

Example adapter entry:

```yaml
connections:
  - name: openai_main
    adapter_type: model
    provider: openai
    model: gpt-4o
  - name: cursor_local
    adapter_type: ide
    provider: cursor
    workspace: C:\Users\Admin\Desktop\connect
  - name: slack_work
    adapter_type: messaging
    provider: slack
```

## Supported adapters

### Models

- OpenAI
- Anthropic
- Google Gemini
- Groq
- Ollama
- OpenRouter
- Hugging Face Inference
- Cohere
- Mistral
- DeepSeek
- xAI Grok
- LM Studio
- Generic OpenAI-compatible endpoints

Example config:

```yaml
- name: openai_main
  adapter_type: model
  provider: openai
  model: gpt-4o
```

### IDEs

- Cursor
- Windsurf
- VS Code
- JetBrains
- Neovim
- Emacs
- Sublime Text
- Zed
- Generic IDE fallback

Example config:

```yaml
- name: cursor_local
  adapter_type: ide
  provider: cursor
  workspace: C:\Users\Admin\Desktop\connect
```

### Messaging

- Slack
- Discord
- Telegram
- WhatsApp
- Email
- Microsoft Teams
- Signal
- Matrix
- IRC
- Mattermost
- Rocket.Chat

Example config:

```yaml
- name: slack_work
  adapter_type: messaging
  provider: slack
```

### Meetings

- Zoom
- Google Meet
- Teams meetings
- Calendly

### Version control

- GitHub
- GitLab
- Bitbucket
- Local Git

### Web apps and APIs

- Playwright browser automation
- Notion
- Airtable
- Google Workspace
- Microsoft 365
- Jira
- Trello
- Linear
- Asana
- Zapier webhooks
- Make webhooks
- Generic REST API

### Payments

- Stripe
- PayPal
- Razorpay
- Crypto payment links

### OS and infrastructure

- OS control
- Docker
- SSH

## Custom adapters

Create a new adapter by extending `IMOSAdapter`:

```python
from imos.adapters.base import IMOSAdapter
from imos.models import IMOSResult, IMOSTask

class MyAdapter(IMOSAdapter):
    def __init__(self, name="my_adapter", config=None):
        super().__init__(name=name, adapter_type="tool", capabilities=["do_work"], config=config)

    async def connect(self) -> bool:
        self.status = "connected"
        return True

    async def disconnect(self) -> None:
        self.status = "disconnected"

    async def send(self, task: IMOSTask) -> IMOSResult:
        return IMOSResult(task.task_id, self.name, True, output="done")

    async def health_check(self) -> bool:
        return True

    async def get_capabilities(self) -> list[str]:
        return self.capabilities
```

Then add it to `connections.yaml` using `module` and `class_name` if needed.

## MCP integration

IMOS exposes a Model Context Protocol server over both stdio and HTTP/SSE.

Install editor configs:

- `imos mcp install`

Generated files:

- `~/.cursor/mcp.json`
- `~/.codeium/windsurf/mcp_config.json`

MCP tools:

- `imos_run`
- `imos_write_file`
- `imos_read_file`
- `imos_run_shell`
- `imos_git_commit`
- `imos_send_message`
- `imos_search_web`
- `imos_list_adapters`

## CLI

Commands:

- `imos run "<prompt>"`
- `imos run "<prompt>" --adapters slack,cursor`
- `imos adapters list`
- `imos adapters add <type> <name>`
- `imos adapters test <name>`
- `imos adapters remove <name>`
- `imos history`
- `imos status`
- `imos mcp install`
- `imos dashboard`

Existing launcher integration:

- `python ai_assistant.py --imos "<prompt>"`
- `connect imos run "<prompt>"`
- `connect --doctor`

## Dashboard

Run or serve the IMOS UI through `nexus.py` and open:

- `http://127.0.0.1:8765/imos`

Dashboard features:

- prompt runner
- adapter status cards
- add adapter modal
- task history feed
- live WebSocket output panel
- settings and capability endpoints

## Security and privacy

- Credentials are intended to stay local in `.env` and `~/.imos`.
- Payment adapters require `confirm=True`.
- OS-destructive actions require confirmation or explicit policy allowance.
- The orchestrator writes audit entries under `~/.imos/logs`.
- Conversation and execution context are stored locally in `~/.imos/context.json`.

## Troubleshooting

### Models

- If a provider reports disconnected, verify the matching API key and model name.
- For Ollama and LM Studio, confirm the local server is actually running on the configured port.

### IDEs

- If Cursor/Windsurf/Zed do not see IMOS, rerun `imos mcp install`.
- If VS Code file opening fails, confirm the `code` CLI is installed in PATH.
- If Neovim integration fails, verify `$NVIM` or the configured socket path.

### Messaging

- Check bot tokens, channel IDs, room IDs, and Graph tenant credentials carefully.
- Email flows require both SMTP and IMAP settings if you want send and receive.

### VCS

- GitHub/GitLab/Bitbucket operations require the expected repository scopes.
- Local Git operations assume the target path is a valid repository.

### Browser

- Install Playwright browsers with `playwright install chromium`.
- Use headed mode by setting `HEADLESS=false` when debugging browser automation.

### Payments

- Financial actions will be blocked unless `confirm=True` is passed.
- Never place raw card data in prompts or config.

### OS / Docker / SSH

- Some OS operations are platform-specific.
- Docker requires a reachable daemon.
- SSH requires valid host credentials in the configured host map.
