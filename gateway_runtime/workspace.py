from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict


DEFAULT_FILES: Dict[str, str] = {
    "AGENTS.md": """# AGENTS

- `default`: General operator for coding, research, and execution.
- `work`: Use for code and project tasks.
- `personal`: Use for personal admin tasks with tighter permissions.
""",
    "SOUL.md": """# SOUL

Name: CONNECT
Style: Direct, calm, tool-driven, and explicit about actions.
Rules:
- Prefer typed tools over free-form shelling when possible.
- Ask before sensitive external actions.
- Keep responses concise and operational.
""",
    "TOOLS.md": """# TOOLS

The runtime exposes typed tool groups:
- `ui`: browser, canvas
- `automation`: cron, gateway
- `fs`: file system
- `runtime`: shell, process
- `sessions`: session routing and subagents
- `memory`: search and recall
- `web`: web search and fetch
- `nodes`: paired devices
- `messaging`: outbound messaging
- `media`: image, video, audio
""",
    "HEARTBEAT.md": """# HEARTBEAT

Recurring automation notes go here.
- Review pending tasks
- Summarize active sessions
- Check scheduled jobs
""",
}


@dataclass
class WorkspaceLayout:
    root: Path

    @property
    def skills_dir(self) -> Path:
        return self.root / "skills"

    @property
    def sessions_dir(self) -> Path:
        return self.root / "sessions"

    @property
    def memory_dir(self) -> Path:
        return self.root / "memory"

    @property
    def cron_dir(self) -> Path:
        return self.root / "cron"

    @property
    def nodes_dir(self) -> Path:
        return self.root / "nodes"

    @property
    def canvas_dir(self) -> Path:
        return self.root / "canvas"

    @property
    def orchestration_dir(self) -> Path:
        return self.root / "orchestration"

    @property
    def messaging_dir(self) -> Path:
        return self.root / "messaging"

    @property
    def workflows_dir(self) -> Path:
        return self.root / "workflows"

    def bootstrap(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.cron_dir.mkdir(parents=True, exist_ok=True)
        self.nodes_dir.mkdir(parents=True, exist_ok=True)
        self.canvas_dir.mkdir(parents=True, exist_ok=True)
        self.orchestration_dir.mkdir(parents=True, exist_ok=True)
        self.messaging_dir.mkdir(parents=True, exist_ok=True)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        for name, content in DEFAULT_FILES.items():
            path = self.root / name
            if not path.exists():
                path.write_text(content.strip() + "\n", encoding="utf-8")
