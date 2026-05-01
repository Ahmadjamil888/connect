"""
IMOS Netlify deployment skill.
Uses NETLIFY_TOKEN from env. User can also pass their own token.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import requests

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["deploy", "list_sites", "create_site", "get_site"],
        },
        "project_dir": {"type": "string"},
        "site_name": {"type": "string"},
        "site_id": {"type": "string"},
        "token": {"type": "string"},
        "build_dir": {"type": "string"},
    },
    "required": ["action"],
}

NETLIFY_API = "https://api.netlify.com/api/v1"


def _token(inputs: dict) -> str:
    t = str(inputs.get("token", "")).strip()
    if t:
        return t
    t = os.environ.get("NETLIFY_TOKEN", "").strip()
    if t:
        return t
    from config.config import _env_value
    return _env_value("NETLIFY_TOKEN")


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _detect_build_dir(project_dir: Path) -> str:
    for candidate in ["dist", "build", "out", ".next", "public"]:
        if (project_dir / candidate).exists():
            return candidate
    return "dist"


def run(inputs, *, workspace: str, **_kwargs):
    action = str(inputs.get("action", "deploy")).strip().lower()
    token = _token(inputs)
    if not token:
        return {
            "ok": False,
            "error": "NETLIFY_TOKEN not set. Add it in API Keys settings or pass token parameter.",
        }

    if action == "deploy":
        project_dir = Path(workspace) / str(inputs.get("project_dir", "."))
        site_name = str(inputs.get("site_name", project_dir.name)).strip() or project_dir.name
        build_dir = str(inputs.get("build_dir", "")).strip() or _detect_build_dir(project_dir)
        steps = []

        # Build
        r = subprocess.run("npm run build", shell=True, capture_output=True, text=True,
                           cwd=str(project_dir), timeout=300)
        steps.append(f"Build: {'OK' if r.returncode == 0 else 'FAILED'}")
        if r.returncode != 0:
            return {"ok": False, "error": "Build failed", "stderr": r.stderr[-2000:], "steps": steps}

        # Deploy via CLI
        if not subprocess.run("netlify --version", shell=True, capture_output=True).returncode == 0:
            subprocess.run("npm install -g netlify-cli", shell=True, capture_output=True, timeout=120)

        env = {**os.environ, "NETLIFY_AUTH_TOKEN": token}
        build_path = project_dir / build_dir
        cmd = f'netlify deploy --dir "{build_path}" --prod --json'
        r2 = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                            cwd=str(project_dir), env=env, timeout=300)
        output = (r2.stdout + "\n" + r2.stderr).strip()
        url = ""
        try:
            data = json.loads(r2.stdout)
            url = data.get("deploy_url") or data.get("url") or ""
        except Exception:
            for line in output.splitlines():
                if "https://" in line and "netlify" in line:
                    url = line.strip()
                    break

        steps.append(f"Deploy: {'OK' if r2.returncode == 0 else 'FAILED'}")
        if url:
            steps.append(f"URL: {url}")

        return {"ok": r2.returncode == 0, "url": url, "steps": steps, "output": output[-2000:]}

    if action == "list_sites":
        r = requests.get(f"{NETLIFY_API}/sites", headers=_headers(token), timeout=20)
        sites = r.json()
        return {
            "ok": True,
            "sites": [{"name": s.get("name"), "id": s.get("id"), "url": s.get("ssl_url")} for s in sites],
        }

    if action == "create_site":
        name = str(inputs.get("site_name", "")).strip()
        r = requests.post(f"{NETLIFY_API}/sites", headers=_headers(token),
                          json={"name": name}, timeout=20)
        data = r.json()
        return {"ok": r.status_code < 400, "site_id": data.get("id"), "url": data.get("ssl_url")}

    if action == "get_site":
        site_id = str(inputs.get("site_id", "")).strip()
        r = requests.get(f"{NETLIFY_API}/sites/{site_id}", headers=_headers(token), timeout=20)
        return {"ok": r.status_code < 400, "data": r.json()}

    return {"ok": False, "error": f"Unknown action: {action}"}
