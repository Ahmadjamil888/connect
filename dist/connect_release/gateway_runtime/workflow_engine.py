from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml


class WorkflowEngine:
    def __init__(self, workflows_dir: Path, executor: Callable[[str, Dict[str, Any]], Any], sender: Callable[[str, str], Any]):
        self.workflows_dir = workflows_dir
        self.executor = executor
        self.sender = sender

    def list_workflows(self) -> List[Dict[str, Any]]:
        return [self._summary(path) for path in sorted(self.workflows_dir.glob("*.yml"))] + [
            self._summary(path) for path in sorted(self.workflows_dir.glob("*.yaml"))
        ]

    def webhook_map(self) -> Dict[str, Dict[str, Any]]:
        mapping: Dict[str, Dict[str, Any]] = {}
        for item in self.list_workflows():
            trigger = item.get("trigger")
            if trigger:
                mapping[str(trigger)] = item
        return mapping

    def run_named(self, name: str, payload: Optional[Dict[str, Any]] = None, session_id: str = "") -> Dict[str, Any]:
        path = self._resolve_workflow_path(name)
        workflow = self._load_yaml(path)
        return self._run_workflow(workflow, payload or {}, session_id=session_id)

    def trigger_webhook(self, webhook_name: str, payload: Dict[str, Any], session_id: str = "") -> Dict[str, Any]:
        for item in self.list_workflows():
            if item.get("trigger") == webhook_name:
                return self.run_named(item["name"], payload=payload, session_id=session_id)
        raise KeyError(f"unknown webhook trigger: {webhook_name}")

    def _resolve_workflow_path(self, name: str) -> Path:
        direct = self.workflows_dir / name
        if direct.exists():
            return direct
        for suffix in (".yaml", ".yml"):
            candidate = self.workflows_dir / f"{name}{suffix}"
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"workflow not found: {name}")

    def _summary(self, path: Path) -> Dict[str, Any]:
        workflow = self._load_yaml(path)
        return {
            "name": str(workflow.get("name") or path.stem),
            "path": str(path),
            "trigger": ((workflow.get("triggers") or {}).get("webhook") if isinstance(workflow.get("triggers"), dict) else ""),
            "step_count": len(workflow.get("steps", []) or []),
        }

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"workflow must be a mapping: {path}")
        data.setdefault("name", path.stem)
        data.setdefault("steps", [])
        return data

    def _render(self, value: Any, context: Dict[str, Any]) -> Any:
        if isinstance(value, str):
            try:
                return value.format(**context)
            except Exception:
                return value
        if isinstance(value, list):
            return [self._render(item, context) for item in value]
        if isinstance(value, dict):
            return {key: self._render(item, context) for key, item in value.items()}
        return value

    def _run_workflow(self, workflow: Dict[str, Any], payload: Dict[str, Any], session_id: str = "") -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        context: Dict[str, Any] = {
            "payload": payload,
            "session_id": session_id,
            "workflow_name": workflow.get("name", ""),
            "payload_json": json.dumps(payload, ensure_ascii=True),
        }
        for index, step in enumerate(workflow.get("steps", []) or [], start=1):
            if not isinstance(step, dict):
                raise ValueError(f"workflow step {index} must be a mapping")
            step_type = str(step.get("type", "tool"))
            step_name = str(step.get("name", f"step_{index}"))
            rendered = self._render(step, context)
            if step_type == "tool":
                tool_name = str(rendered.get("tool", "")).strip()
                args = rendered.get("args", {}) or {}
                result = self.executor(tool_name, args)
            elif step_type == "message":
                result = self.sender(str(rendered.get("target", "")), str(rendered.get("content", "")))
            elif step_type == "prompt":
                result = {
                    "queued": True,
                    "session_id": rendered.get("session_id") or session_id,
                    "content": rendered.get("content", ""),
                }
            else:
                raise ValueError(f"unsupported workflow step type: {step_type}")
            context[step_name] = result
            context[f"step_{index}"] = result
            results.append({"name": step_name, "type": step_type, "result": result})
        return {"ok": True, "workflow": workflow.get("name", ""), "steps": results}
