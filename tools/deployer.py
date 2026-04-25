import json
import shutil
import subprocess
from pathlib import Path

import requests


def _ensure_cli(command: str, package: str) -> str:
    if shutil.which(command):
        return ""
    install = subprocess.run(["npm", "install", "-g", package], capture_output=True, text=True, timeout=600)
    if install.returncode != 0:
        raise RuntimeError(install.stderr or install.stdout or f"Failed to install {package}")
    return install.stdout.strip()


def deploy_to_vercel(project_dir: str, project_name: str) -> str:
    target = Path(project_dir).resolve()
    _ensure_cli("vercel", "vercel")
    cmd = ["vercel", "--prod", "--yes", "--name", project_name]
    result = subprocess.run(cmd, cwd=target, capture_output=True, text=True, timeout=1200)
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.returncode != 0:
        return f"Vercel deployment failed: {output.strip()}"
    url = next((line.strip() for line in output.splitlines() if "https://" in line), "")
    return url or output.strip()


def deploy_to_netlify(project_dir: str, site_name: str) -> str:
    target = Path(project_dir).resolve()
    _ensure_cli("netlify", "netlify-cli")
    cmd = ["netlify", "deploy", "--dir", str(target), "--prod", "--site", site_name, "--json"]
    result = subprocess.run(cmd, cwd=target, capture_output=True, text=True, timeout=1200)
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.returncode != 0:
        return f"Netlify deployment failed: {output.strip()}"
    try:
        payload = json.loads(result.stdout)
        return payload.get("deploy_url") or payload.get("url") or output.strip()
    except Exception:
        for line in output.splitlines():
            if "https://" in line:
                return line.strip()
        return output.strip()


def check_deployment_status(url: str) -> str:
    try:
        response = requests.get(url, timeout=20)
        return f"{url} -> {response.status_code}"
    except Exception as exc:
        return f"Deployment check failed for {url}: {exc}"

