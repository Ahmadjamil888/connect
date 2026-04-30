from __future__ import annotations

import subprocess
from pathlib import Path

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "repo_dir": {"type": "string"},
        "commit_message": {"type": "string"},
    },
    "required": ["commit_message"],
}


def run(inputs, *, workspace: str, **_kwargs):
    repo_dir = Path(workspace) / str(inputs.get("repo_dir", "."))
    msg = str(inputs["commit_message"])
    outputs = []
    for cmd in ["git add -A", f'git commit -m "{msg}"', "git push"]:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=repo_dir, timeout=120)
        outputs.append(result.stdout + result.stderr)
    return "\n".join(outputs).strip()
