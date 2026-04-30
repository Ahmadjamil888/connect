import os
import subprocess
from pathlib import Path

from config.config import get_tokens


def execute_tool(name, inputs, workspace, model_config) -> str:
    if name == "bash":
        result = subprocess.run(
            inputs["command"],
            shell=True,
            capture_output=True,
            text=True,
            cwd=workspace,
            timeout=120,
        )
        return result.stdout + result.stderr

    if name == "write_file":
        path = Path(workspace) / inputs["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(inputs["content"], encoding="utf-8")
        return f"Written: {path}"

    if name == "read_file":
        return (Path(workspace) / inputs["path"]).read_text(
            encoding="utf-8", errors="replace"
        )

    if name == "list_dir":
        p = Path(workspace) / inputs.get("path", ".")
        return "\n".join(item.name for item in p.iterdir())

    if name == "web_search":
        try:
            import httpx

            response = httpx.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": inputs["query"],
                    "format": "json",
                    "no_html": 1,
                    "no_redirect": 1,
                },
                timeout=30.0,
            )
            return response.text[:4000]
        except Exception as e:
            return f"Search failed: {e}"

    if name == "browser_action":
        from browser.controller import run_browser

        browser_inputs = dict(inputs)
        browser_inputs.setdefault("workspace", workspace)
        return run_browser(browser_inputs)

    if name == "deploy_vercel":
        token = os.getenv("VERCEL_TOKEN") or get_tokens().get("vercel", "")
        cmd = f"vercel --token {token} --yes --cwd {inputs['project_dir']}"
        if inputs.get("project_name"):
            cmd += f" --name {inputs['project_name']}"
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=workspace,
            timeout=120,
        )
        return result.stdout + result.stderr

    if name == "deploy_netlify":
        token = os.getenv("NETLIFY_TOKEN") or get_tokens().get("netlify", "")
        cmd = f"netlify deploy --dir={inputs['dist_dir']} --auth={token} --prod"
        if inputs.get("site_name"):
            cmd += f" --alias={inputs['site_name']}"
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=workspace,
            timeout=120,
        )
        return result.stdout + result.stderr

    if name == "github_push":
        repo_dir = inputs.get("repo_dir", workspace)
        msg = inputs.get("commit_message", "update")
        outputs = []
        for cmd in ["git add -A", f'git commit -m "{msg}"', "git push"]:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=repo_dir,
                timeout=120,
            )
            outputs.append(result.stdout + result.stderr)
        return "\n".join(outputs)

    if name == "spawn_agent":
        from agents.runner import spawn_agent

        return spawn_agent(
            inputs["agent_type"],
            inputs["task"],
            inputs.get("context", ""),
            workspace,
            model_config,
        )

    raise ValueError(f"Unknown tool: {name}")
