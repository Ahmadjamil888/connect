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
        src_dir = target / "src"
        return {
            "ok": True,
            "created": False,
            "message": f"Project already exists: {target}",
            "verified": package_json.exists() and src_dir.exists(),
            "path": str(target),
            "verified_files": {
                "package_json": package_json.exists(),
                "src_dir": src_dir.exists(),
            },
        }

    create_command = f"npm.cmd create vite@latest {json.dumps(project_name)} -- --template {json.dumps(template)}"
    shell_runner = _kwargs.get("shell_runner")
    if shell_runner is not None:
        create = shell_runner.run(create_command, cwd=str(root), timeout=1200)
    else:
        create_raw = subprocess.run(
            ["npm.cmd", "create", "vite@latest", project_name, "--", "--template", template],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=1200,
        )
        create = type(
            "ExecutionResult",
            (),
            {
                "ok": create_raw.returncode == 0,
                "command": create_command,
                "cwd": str(root),
                "returncode": create_raw.returncode,
                "stdout": create_raw.stdout,
                "stderr": create_raw.stderr,
                "log_path": "",
            },
        )()

    if create.returncode != 0:
        return {
            "ok": False,
            "step": "create",
            "stdout": create.stdout,
            "stderr": create.stderr,
            "returncode": create.returncode,
            "log_path": getattr(create, "log_path", ""),
        }

    install_command = f"{package_manager}.cmd install" if package_manager == "npm" else f"{package_manager} install"
    if shell_runner is not None:
        install = shell_runner.run(install_command, cwd=str(target), timeout=1200)
    else:
        install_raw = subprocess.run(
            [f"{package_manager}.cmd" if package_manager == "npm" else package_manager, "install"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=1200,
        )
        install = type(
            "ExecutionResult",
            (),
            {
                "ok": install_raw.returncode == 0,
                "command": install_command,
                "cwd": str(target),
                "returncode": install_raw.returncode,
                "stdout": install_raw.stdout,
                "stderr": install_raw.stderr,
                "log_path": "",
            },
        )()

    package_json = target / "package.json"
    src_dir = target / "src"
    app_file = target / "src" / "App.jsx"
    alt_app_file = target / "src" / "App.tsx"
    index_html = target / "index.html"
    verified_files = {
        "package_json": package_json.exists() and package_json.stat().st_size > 0,
        "src_dir": src_dir.exists(),
        "app_file": (app_file.exists() and app_file.stat().st_size > 0) or (alt_app_file.exists() and alt_app_file.stat().st_size > 0),
        "index_html": index_html.exists() and index_html.stat().st_size > 0,
    }
    return {
        "ok": install.returncode == 0 and all(verified_files.values()),
        "created": True,
        "path": str(target),
        "verified_files": verified_files,
        "create_stdout": create.stdout[-1200:],
        "create_stderr": create.stderr[-1200:],
        "install_stdout": install.stdout[-1200:],
        "install_stderr": install.stderr[-1200:],
        "create_returncode": create.returncode,
        "install_returncode": install.returncode,
        "create_log_path": getattr(create, "log_path", ""),
        "install_log_path": getattr(install, "log_path", ""),
    }
