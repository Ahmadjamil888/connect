from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from autonomous_agent import PolicyEngine
from connectai.ops import AuditLogger

from imos.config import merged_settings
from imos.context import IMOSContextManager
from imos.models import IMOSResult, IMOSTask, OrchestratorResult
from imos.registry import AdapterRegistry
from imos.router import TaskRouter
from imos.synthesizer import ResultSynthesizer


class IMOSOrchestrator:
    def __init__(self, registry: AdapterRegistry | None = None) -> None:
        self.registry = registry or AdapterRegistry()
        self.settings = merged_settings()
        self.audit = self._build_audit_logger()
        self.policy = PolicyEngine()
        self.context_manager = IMOSContextManager()
        synthesis_name = self.settings.get("result_synthesis_model")
        self.synthesis_adapter = self.registry.get(synthesis_name) if synthesis_name and synthesis_name != "auto" else None
        if self.synthesis_adapter is None:
            models = self.registry.get_by_type("model")
            self.synthesis_adapter = models[0] if models else None
        self.router = TaskRouter(self.registry, self.settings, synthesis_adapter=self.synthesis_adapter)
        self.synthesizer = ResultSynthesizer(self.synthesis_adapter)

    def _build_audit_logger(self) -> AuditLogger:
        for root in (Path.home() / ".imos" / "logs", Path.cwd() / ".imos" / "logs"):
            try:
                logger = AuditLogger(root)
                logger.append("imos_bootstrap", "audit_ready", {})
                return logger
            except Exception:
                continue
        return AuditLogger(Path.cwd() / "imos_logs")

    async def run(self, user_prompt: str, context: dict | None = None) -> OrchestratorResult:
        started = time.perf_counter()
        context = context or {}
        self.audit.append("imos_prompt", user_prompt, {"context": context})
        if self._is_high_risk(user_prompt) and not context.get("confirm"):
            raise PermissionError("High-risk IMOS task requires context['confirm']=True")

        routed_groups = await self.router.decompose(user_prompt, context=context)
        ordered_tasks = [task for group in routed_groups for task in group.subtasks]
        results: list[IMOSResult] = []
        completed: dict[str, IMOSResult] = {}

        remaining = list(ordered_tasks)
        while remaining:
            ready = [task for task in remaining if all(dep in completed for dep in task.metadata.get("depends_on", []))]
            if not ready:
                ready = [remaining[0]]
            parallel = [task for task in ready if task.metadata.get("can_run_parallel")]
            sequential = [task for task in ready if not task.metadata.get("can_run_parallel")]
            if parallel:
                batch_results = await asyncio.gather(*(self._execute_task(task, completed) for task in parallel))
                for task, result in zip(parallel, batch_results):
                    results.append(result)
                    completed[task.task_id] = result
                    remaining.remove(task)
            for task in sequential:
                result = await self._execute_task(task, completed)
                results.append(result)
                completed[task.task_id] = result
                remaining.remove(task)

        final_response = await self.synthesizer.synthesize_results(results)
        self.audit.append("imos_result", final_response, {"adapters": sorted({item.adapter_name for item in results})})
        self.context_manager.add_entry(user_prompt, [asdict(result) for result in results], context)
        if self.settings.get("auto_notify"):
            await self._fan_out_notifications(final_response)
        return OrchestratorResult(
            final_response=final_response,
            subtask_results=results,
            duration_ms=int((time.perf_counter() - started) * 1000),
            adapters_used=sorted({result.adapter_name for result in results}),
        )

    async def _execute_task(self, task: IMOSTask, completed: dict[str, IMOSResult]) -> IMOSResult:
        adapter = self.registry.get(task.target_adapter)
        if adapter is None:
            resolved_name = self.router.resolve_target_adapter(task.target_adapter, task.subtask_type, task.prompt)
            adapter = self.registry.get(resolved_name)
            if adapter is None:
                return IMOSResult(task.task_id, task.target_adapter, False, error=f"Adapter not found: {task.target_adapter}")
            task.target_adapter = adapter.name
        merged_context = dict(task.context)
        merged_context["dependency_results"] = {key: value.output for key, value in completed.items()}
        task.context = merged_context
        return await adapter.send(task)

    def _is_high_risk(self, prompt: str) -> bool:
        lowered = prompt.lower()
        return any(token in lowered for token in ["delete", "shutdown", "restart", "charge", "pay", "kill process", "registry"])

    async def _fan_out_notifications(self, message: str) -> None:
        outputs = self.registry.get_by_type("messaging")
        for adapter in outputs:
            await adapter.send(
                IMOSTask(
                    task_id=f"notify-{int(time.time()*1000)}",
                    prompt=message,
                    subtask_type="send_message",
                    target_adapter=adapter.name,
                    metadata={"action": "send_message"},
                )
            )
