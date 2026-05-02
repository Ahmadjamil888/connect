from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class IMOSTask:
    task_id: str
    prompt: str
    subtask_type: str
    target_adapter: str
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    timeout_seconds: int = 120
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IMOSResult:
    task_id: str
    adapter_name: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IMOSSubtask:
    original_prompt: str
    subtasks: list[IMOSTask] = field(default_factory=list)
    routing_explanation: str = ""


@dataclass(slots=True)
class OrchestratorResult:
    final_response: str
    subtask_results: list[IMOSResult] = field(default_factory=list)
    duration_ms: int = 0
    adapters_used: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
