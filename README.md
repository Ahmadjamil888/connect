# Open Claw

Open Claw is an autonomous agentic AI CLI that uses a configurable model backend to orchestrate coding, design, research, browser automation, deployment, and specialist sub-agents from a single workspace.

## IMOS

This repository now also includes IMOS, the Intelligent Multi-agent Operating System, which layers a universal adapter-based orchestration runtime on top of the existing assistant stack. See [IMOS_README.md](IMOS_README.md) for the full architecture, adapter catalog, CLI, MCP integration, dashboard, and setup details.

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

Run `python main.py [workspace_dir]` and type a goal at the prompt.

## Example goals

1. Build a landing page for an AI startup and save it in the current workspace.
2. Research the latest authentication patterns for SaaS apps and summarize them in a markdown file.
3. Create a FastAPI backend with a health check endpoint and test it locally.
4. Deploy the current frontend project to Vercel and report the deployment URL.
5. Open a browser, navigate to a site, and capture a screenshot.
