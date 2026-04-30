from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml


class WorkflowRegistry:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.workflows_dir = workspace_root / "workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

    def list_workflows(self) -> List[Dict[str, Any]]:
        items = []
        for path in sorted(list(self.workflows_dir.glob("*.yml")) + list(self.workflows_dir.glob("*.yaml"))):
            data = self._read(path)
            items.append(
                {
                    "name": str(data.get("name", path.stem)),
                    "path": str(path),
                    "steps": len(data.get("steps", []) or []),
                    "trigger": ((data.get("triggers") or {}).get("webhook", "") if isinstance(data.get("triggers"), dict) else ""),
                }
            )
        return items

    def _path_for(self, name: str) -> Path:
        direct = self.workflows_dir / name
        if direct.exists():
            return direct
        for suffix in (".yaml", ".yml"):
            candidate = self.workflows_dir / f"{name}{suffix}"
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Workflow not found: {name}")

    def _read(self, path: Path) -> Dict[str, Any]:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Workflow must be a mapping: {path}")
        data.setdefault("name", path.stem)
        data.setdefault("steps", [])
        return data

    def run(self, name: str, *, tool_executor: Callable[[str, Dict[str, Any]], Any], sender: Callable[[str], Any], payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        workflow = self._read(self._path_for(name))
        payload = payload or {}
        context: Dict[str, Any] = {"payload": payload}
        results: List[Dict[str, Any]] = []
        for index, step in enumerate(workflow.get("steps", []), start=1):
            if not isinstance(step, dict):
                raise ValueError(f"Invalid workflow step {index}")
            step_type = str(step.get("type", "tool"))
            step_name = str(step.get("name", f"step_{index}"))
            if step_type == "tool":
                tool_name = str(step.get("tool", ""))
                args = step.get("args", {}) or {}
                result = tool_executor(tool_name, args)
            elif step_type == "message":
                result = sender(str(step.get("content", "")))
            else:
                raise ValueError(f"Unsupported workflow step type: {step_type}")
            context[step_name] = result
            results.append({"step": step_name, "type": step_type, "result": result})
        return {"ok": True, "workflow": workflow.get("name", name), "results": results}
