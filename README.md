
## IMOS

**Intelligent Machine Operating System** — unifies AI models, IDEs, terminals, browser automation, apps, and local machine execution into one persistent runtime.

Stop losing context across ChatGPT, Claude, Cursor, browsers, and automation workflows. IMOS provides a visible coordination layer with shared memory, routing, permissions, auditability, and execution control across your entire workflow stack.

Run `imos` for the CLI operator, open the dashboard at http://127.0.0.1:7070, and see [IMOS_README.md](IMOS_README.md) for architecture, adapters, MCP, and setup.

## Setup

1. `pip install -r requirements.txt`
2. `playwright install chromium`
3. Create `~/.openclaw/config.json` using the config example below.

## Config example

```json
{
  "model": {
    "provider": "anthropic",
    "model": "claude-opus-4-5",
    "api_key": "sk-ant-..."
  },
  "tokens": {
    "vercel": "vercel-token",
    "netlify": "netlify-token",
    "github": "github-token"
  }
}
```

## Usage

Run `python connect.py` for the new audited real-action REPL, or `python main.py [workspace_dir]` for the older workspace runner.

## Example goals

1. Build a landing page for an AI startup and save it in the current workspace.
2. Research the latest authentication patterns for SaaS apps and summarize them in a markdown file.
3. Create a FastAPI backend with a health check endpoint and test it locally.
4. Deploy the current frontend project to Vercel and report the deployment URL.
5. Open a browser, navigate to a site, and capture a screenshot.
