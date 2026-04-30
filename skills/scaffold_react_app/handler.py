from __future__ import annotations

import json
import subprocess
from pathlib import Path

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "project_name": {"type": "string"},
        "template": {"type": "string"},
        "package_manager": {"type": "string"},
    },
    "required": ["project_name"],
}


def run(inputs, *, workspace: str, **_kwargs):
    project_name = str(inputs["project_name"]).strip()
    template = str(inputs.get("template", "react")).strip() or "react"
    package_manager = str(inputs.get("package_manager", "npm")).strip().lower() or "npm"
    root = Path(workspace)
    target = root / project_name
    if target.exists():
        package_json = target / "package.json"
        return {
            "ok": True,
            "created": False,
            "message": f"Project already exists: {target}",
            "verified": package_json.exists(),
            "path": str(target),
        }

    create_cmd = ["npm.cmd", "create", "vite@latest", project_name, "--", "--template", template]
    create = subprocess.run(create_cmd, cwd=root, capture_output=True, text=True, timeout=1200)
    if create.returncode != 0:
        return {
            "ok": False,
            "step": "create",
            "stdout": create.stdout,
            "stderr": create.stderr,
        }

    install_cmd = [f"{package_manager}.cmd" if package_manager == "npm" else package_manager, "install"]
    install = subprocess.run(install_cmd, cwd=target, capture_output=True, text=True, timeout=1200)
    package_json = target / "package.json"
    src_dir = target / "src"
    return {
        "ok": install.returncode == 0 and package_json.exists() and src_dir.exists(),
        "created": True,
        "path": str(target),
        "verified_files": {
            "package_json": package_json.exists(),
            "src_dir": src_dir.exists(),
        },
        "create_stdout": create.stdout[-1200:],
        "create_stderr": create.stderr[-1200:],
        "install_stdout": install.stdout[-1200:],
        "install_stderr": install.stderr[-1200:],
    }
