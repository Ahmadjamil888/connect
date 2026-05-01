"""
IMOS Vercel deployment skill.
Uses VERCEL_TOKEN from env. User can also pass their own token.
Deploys via Vercel REST API (no CLI required).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import requests

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["deploy", "list", "get_deployment", "delete"],
        },
        "project_dir": {"type": "string"},
        "project_name": {"type": "string"},
        "framework": {"type": "string"},
        "deployment_id": {"type": "string"},
        "token": {"type": "string"},
    },
    "required": ["action"],
}

VERCEL_API = "https://api.vercel.com"


def _token(inputs: dict) -> str:
    t = str(inputs.get("token", "")).strip()
    if t:
        return t
    t = os.environ.get("VERCEL_TOKEN", "").strip()
    if t:
        return t
    from config.config import _env_value
    return _env_value("VERCEL_TOKEN")


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _detect_framework(project_dir: Path) -> str:
    pkg = project_dir / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "next" in deps:
                return "nextjs"
            if "vite" in deps:
                return "vite"
            if "react-scripts" in deps:
                return "create-react-app"
            if "nuxt" in deps:
                return "nuxtjs"
            if "svelte" in deps:
                return "svelte"
        except Exception:
            pass
    return "other"


def _build_project(project_dir: Path, framework: str) -> dict:
    """Run build command and return result."""
    build_cmds = {
        "nextjs": "npm run build",
        "vite": "npm run build",
        "create-react-app": "npm run build",
        "nuxtjs": "npm run build",
        "svelte": "npm run build",
        "other": "npm run build",
    }
    cmd = build_cmds.get(framework, "npm run build")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=str(project_dir), timeout=300)
    return {"ok": r.returncode == 0, "stdout": r.stdout[-2000:], "stderr": r.stderr[-2000:]}


def _deploy_via_cli(project_dir: Path, project_name: str, token: str) -> dict:
    """Deploy using vercel CLI with token."""
    # Install vercel CLI if not present
    if not subprocess.run("vercel --version", shell=True, capture_output=True).returncode == 0:
        subprocess.run("npm install -g vercel", shell=True, capture_output=True, timeout=120)

    env = {**os.environ, "VERCEL_TOKEN": token}
    cmd = f'vercel --prod --yes --name "{project_name}" --token "{token}"'
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       cwd=str(project_dir), env=env, timeout=300)
    output = (r.stdout + "\n" + r.stderr).strip()
    url = ""
    for line in output.splitlines():
        if "https://" in line and "vercel.app" in line:
            url = line.strip()
            break
    return {
        "ok": r.returncode == 0,
        "url": url,
        "output": output[-3000:],
        "returncode": r.returncode,
    }


def run(inputs, *, workspace: str, **_kwargs):
    action = str(inputs.get("action", "deploy")).strip().lower()
    token = _token(inputs)
    if not token:
        return {
            "ok": False,
            "error": "VERCEL_TOKEN not set. Add it in API Keys settings or pass token parameter.",
        }

    if action == "deploy":
        project_dir = Path(workspace) / str(inputs.get("project_dir", "."))
        project_name = str(inputs.get("project_name", project_dir.name)).strip() or project_dir.name
        framework = str(inputs.get("framework", "")).strip() or _detect_framework(project_dir)

        steps = []
        steps.append(f"Detected framework: {framework}")
        steps.append(f"Project: {project_name} at {project_dir}")

        # Build first
        build = _build_project(project_dir, framework)
        steps.append(f"Build: {'OK' if build['ok'] else 'FAILED'}")
        if not build["ok"]:
            return {"ok": False, "error": "Build failed", "build_stderr": build["stderr"], "steps": steps}

        # Deploy via CLI
        result = _deploy_via_cli(project_dir, project_name, token)
        steps.append(f"Deploy: {'OK' if result['ok'] else 'FAILED'}")
        if result["url"]:
            steps.append(f"URL: {result['url']}")

        return {
            "ok": result["ok"],
            "url": result["url"],
            "project_name": project_name,
            "framework": framework,
            "steps": steps,
            "output": result["output"],
        }

    if action == "list":
        r = requests.get(f"{VERCEL_API}/v9/projects", headers=_headers(token), timeout=20)
        data = r.json()
        projects = data.get("projects", [])
        return {
            "ok": True,
            "projects": [
                {"name": p["name"], "id": p["id"], "framework": p.get("framework")}
                for p in projects
            ],
        }

    if action == "get_deployment":
        dep_id = str(inputs.get("deployment_id", "")).strip()
        if not dep_id:
            return {"ok": False, "error": "deployment_id required"}
        r = requests.get(f"{VERCEL_API}/v13/deployments/{dep_id}", headers=_headers(token), timeout=20)
        data = r.json()
        return {"ok": True, "state": data.get("readyState"), "url": data.get("url"), "data": data}

    return {"ok": False, "error": f"Unknown action: {action}"}
