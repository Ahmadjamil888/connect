from __future__ import annotations

from pathlib import Path

from config.config import get_model_config, load_config, resolve_runtime_state_root
from connectai.command_router import CommandRouter
from connectai.gateway import ConnectAIGateway
from connectai.memory import ConnectMemoryStore
from connectai.mcp_runtime import MCPRuntime
from connectai.ops import ApprovalPolicy, AuditLogger, CostTracker, ProcessRegistry, ShellRunner, TaskManager
from connectai.runtime import ConnectAIRuntime
from connectai.sessions import ConnectSessionManager
from connectai.skills import SkillRegistry


def _workspace_root() -> Path:
    cfg = load_config()
    return Path(cfg.get("workspace", str(Path.home() / "connectai_workspace")))


def build_jarvis_runtime(workspace: Path | None = None) -> ConnectAIGateway:
    workspace_path = (workspace or _workspace_root()).resolve()
    workspace_path.mkdir(parents=True, exist_ok=True)

    state_root = resolve_runtime_state_root(workspace_path)

    audit_logger = AuditLogger(state_root / "audit")
    approval_policy = ApprovalPolicy(load_config, audit_logger)
    cost_tracker = CostTracker(state_root / "cost")
    process_manager = ProcessRegistry(state_root / "processes", audit_logger)
    shell_runner = ShellRunner(state_root / "commands", audit_logger, approval_policy)
    task_manager = TaskManager(state_root / "tasks", audit_logger)
    memory_store = ConnectMemoryStore(state_root / "memory")
    session_manager = ConnectSessionManager(state_root / "sessions")
    skill_registry = SkillRegistry(workspace_path, bundled_root=Path.cwd() / "skills")
    mcp_runtime = MCPRuntime(state_root / "mcp")
    command_router = CommandRouter({})

    runtime = ConnectAIRuntime(
        skill_registry,
        memory_store,
        shell_runner=shell_runner,
        process_manager=process_manager,
        audit_logger=audit_logger,
        task_manager=task_manager,
        cost_tracker=cost_tracker,
        mcp_runtime=mcp_runtime,
    )
    return ConnectAIGateway(runtime, session_manager, memory_store, command_router)


class JarvisRuntime:
    def __init__(self, workspace: Path | None = None):
        self.workspace = (workspace or _workspace_root()).resolve()
        self.gateway = build_jarvis_runtime(self.workspace)

    def process(self, text: str, *, session_key: str = "jarvis-desktop", user_id: str = "local-user") -> str:
        from connectai.channels import MessageEnvelope

        envelope = MessageEnvelope(
            text=text,
            channel="desktop",
            user_id=user_id,
            session_key=session_key,
            metadata={"surface": "jarvis"},
        )
        result = self.gateway.handle_with_meta(envelope, str(self.workspace), get_model_config())
        return str(result.get("output", ""))
