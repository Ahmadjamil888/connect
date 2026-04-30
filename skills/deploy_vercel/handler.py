from __future__ import annotations

from pathlib import Path

from tools.deployer import deploy_to_vercel

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "project_dir": {"type": "string"},
        "project_name": {"type": "string"},
    },
    "required": ["project_dir", "project_name"],
}


def run(inputs, *, workspace: str, **_kwargs):
    project_dir = Path(workspace) / str(inputs["project_dir"])
    return deploy_to_vercel(str(project_dir), str(inputs["project_name"]))
