from __future__ import annotations

from pathlib import Path

from tools.deployer import deploy_to_netlify

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "project_dir": {"type": "string"},
        "site_name": {"type": "string"},
    },
    "required": ["project_dir", "site_name"],
}


def run(inputs, *, workspace: str, **_kwargs):
    project_dir = Path(workspace) / str(inputs["project_dir"])
    return deploy_to_netlify(str(project_dir), str(inputs["site_name"]))
