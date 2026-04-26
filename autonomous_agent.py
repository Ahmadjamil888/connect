#!/usr/bin/env python3
"""
Autonomous operator loop for the AI assistant.

Architecture:
    goal -> planner -> task graph -> executor -> verifier -> reflection -> memory
"""

from __future__ import annotations

import json
import hashlib
import hmac
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class AgentConfig:
    DATA_DIR = Path.home() / ".ai_assistant" / "agent"
    RUNS_DIR = DATA_DIR / "runs"
    STM_FILE = DATA_DIR / "stm.json"
    LTM_FILE = DATA_DIR / "ltm.json"
    FAILURES_FILE = DATA_DIR / "failures.json"
    RUNS_INDEX_FILE = DATA_DIR / "runs_index.json"
    POLICY_FILE = DATA_DIR / "policy.json"
    AUDIT_LOG_FILE = DATA_DIR / "audit.log.jsonl"
    WORLD_STATE_FILE = Path.home() / ".ai_assistant" / "world_state.json"

    MAX_PLAN_STEPS = 12
    MAX_RETRIES_PER_TASK = 1
    MAX_REPLANS = 2
    MAX_CONTEXT_EVENTS = 200

    ENABLE_REFLECTION = True
    REQUIRE_DANGEROUS_CONFIRMATION = True
    AUDIT_SECRET = os.getenv("AI_ASSISTANT_AUDIT_SECRET", "local-dev-audit-secret")


def _rebase_agent_storage(base_dir: Path):
    AgentConfig.DATA_DIR = base_dir
    AgentConfig.RUNS_DIR = AgentConfig.DATA_DIR / "runs"
    AgentConfig.STM_FILE = AgentConfig.DATA_DIR / "stm.json"
    AgentConfig.LTM_FILE = AgentConfig.DATA_DIR / "ltm.json"
    AgentConfig.FAILURES_FILE = AgentConfig.DATA_DIR / "failures.json"
    AgentConfig.RUNS_INDEX_FILE = AgentConfig.DATA_DIR / "runs_index.json"
    AgentConfig.POLICY_FILE = AgentConfig.DATA_DIR / "policy.json"
    AgentConfig.AUDIT_LOG_FILE = AgentConfig.DATA_DIR / "audit.log.jsonl"
    AgentConfig.WORLD_STATE_FILE = Path.cwd() / ".ai_assistant_runtime" / "world_state.json"


try:
    AgentConfig.DATA_DIR.mkdir(parents=True, exist_ok=True)
    AgentConfig.RUNS_DIR.mkdir(parents=True, exist_ok=True)
except PermissionError:
    _rebase_agent_storage(Path.cwd() / ".ai_assistant_agent")
    AgentConfig.DATA_DIR.mkdir(parents=True, exist_ok=True)
    AgentConfig.RUNS_DIR.mkdir(parents=True, exist_ok=True)


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class Task:
    id: str
    name: str
    description: str
    tool_name: str
    tool_args: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    verification: str = ""
    rationale: str = ""
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    result: str = ""
    error: str = ""
    started_at: str = ""
    completed_at: str = ""


@dataclass
class Plan:
    id: str
    goal: str
    tasks: List[Task]
    revision: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RunState:
    run_id: str
    goal: str
    status: RunStatus
    plan: Plan
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str = ""
    summary: str = ""
    events: List[Dict[str, Any]] = field(default_factory=list)
    replan_count: int = 0


@dataclass
class DecisionTrace:
    thought: str
    next_action: str
    plan: List[str] = field(default_factory=list)


@dataclass
class ToolSpec:
    name: str
    required_args: List[str]
    properties: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    description: str = ""


class MemorySystem:
    def __init__(self):
        self.stm = self._load_json(AgentConfig.STM_FILE, default={"session": {}, "context": []})
        self.ltm = self._load_json(
            AgentConfig.LTM_FILE,
            default={"facts": [], "patterns": [], "skills": [], "project_memories": []},
        )
        self.failures = self._load_json(AgentConfig.FAILURES_FILE, default=[])
        self.runs_index = self._load_json(AgentConfig.RUNS_INDEX_FILE, default=[])

    def _load_json(self, path: Path, default: Any) -> Any:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return default
        return default

    def _save_json(self, path: Path, data: Any):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except PermissionError:
            _rebase_agent_storage(Path.cwd() / ".ai_assistant_agent")
            AgentConfig.DATA_DIR.mkdir(parents=True, exist_ok=True)
            AgentConfig.RUNS_DIR.mkdir(parents=True, exist_ok=True)
            fallback_map = {
                "stm.json": AgentConfig.STM_FILE,
                "ltm.json": AgentConfig.LTM_FILE,
                "failures.json": AgentConfig.FAILURES_FILE,
                "runs_index.json": AgentConfig.RUNS_INDEX_FILE,
            }
            target = fallback_map.get(path.name, AgentConfig.DATA_DIR / path.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save(self):
        self.stm["context"] = self.stm.get("context", [])[-AgentConfig.MAX_CONTEXT_EVENTS :]
        self._save_json(AgentConfig.STM_FILE, self.stm)
        self._save_json(AgentConfig.LTM_FILE, self.ltm)
        self.failures = self.failures[-300:]
        self._save_json(AgentConfig.FAILURES_FILE, self.failures)
        self.runs_index = self.runs_index[-500:]
        self._save_json(AgentConfig.RUNS_INDEX_FILE, self.runs_index)

    def add_context(self, event: Dict[str, Any]):
        event["ts"] = datetime.now().isoformat()
        self.stm.setdefault("context", []).append(event)
        self.save()

    def add_fact(self, content: str, tags: Optional[List[str]] = None):
        self.ltm["facts"].append(
            {
                "id": self._short_id(content),
                "content": content,
                "tags": tags or [],
                "ts": datetime.now().isoformat(),
            }
        )
        self.ltm["facts"] = self.ltm["facts"][-300:]
        self.save()

    def add_pattern(self, content: str, success_rate: float):
        self.ltm["patterns"].append(
            {
                "id": self._short_id(content),
                "content": content,
                "success_rate": success_rate,
                "ts": datetime.now().isoformat(),
            }
        )
        self.ltm["patterns"] = self.ltm["patterns"][-200:]
        self.save()

    def add_skill(self, name: str, description: str):
        self.ltm["skills"].append(
            {
                "id": self._short_id(name),
                "name": name,
                "description": description,
                "ts": datetime.now().isoformat(),
            }
        )
        self.ltm["skills"] = self.ltm["skills"][-120:]
        self.save()

    def add_project_memory(self, goal: str, payload: Dict[str, Any]):
        self.ltm["project_memories"].append(
            {
                "id": self._short_id(goal),
                "goal": goal,
                "payload": payload,
                "ts": datetime.now().isoformat(),
            }
        )
        self.ltm["project_memories"] = self.ltm["project_memories"][-200:]
        self.save()

    def log_failure(self, task: Task, error: str, run_id: str):
        self.failures.append(
            {
                "id": self._short_id(task.name + error),
                "run_id": run_id,
                "task_name": task.name,
                "tool_name": task.tool_name,
                "error": error,
                "args": task.tool_args,
                "ts": datetime.now().isoformat(),
            }
        )
        self.save()

    def remember_run(self, run: RunState):
        self.runs_index.append(
            {
                "run_id": run.run_id,
                "goal": run.goal,
                "status": run.status.value,
                "created_at": run.created_at,
                "updated_at": run.updated_at,
            }
        )
        self.save()

    def update_run_index(self, run: RunState):
        for row in self.runs_index:
            if row.get("run_id") == run.run_id:
                row["status"] = run.status.value
                row["updated_at"] = run.updated_at
                break
        self.save()

    def search(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        tokens = [t for t in re.split(r"\W+", query.lower()) if t]
        pool = self.ltm.get("facts", []) + self.ltm.get("patterns", []) + self.ltm.get("project_memories", [])
        scored: List[Tuple[int, Dict[str, Any]]] = []
        for item in pool:
            txt = json.dumps(item).lower()
            score = sum(1 for tok in tokens if tok and tok in txt)
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [x[1] for x in scored[:limit]]

    @property
    def failure_log(self) -> List[Dict[str, Any]]:
        return self.failures

    def clear_context(self):
        self.stm["context"] = []
        self.save()

    def _short_id(self, text: str) -> str:
        return hashlib.md5((text + datetime.now().isoformat()).encode("utf-8")).hexdigest()[:12]


class WorldStateStore:
    def __init__(self):
        self.path = AgentConfig.WORLD_STATE_FILE
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.path = Path.cwd() / ".ai_assistant_runtime" / "world_state.json"
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _default(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "last_action": {},
            "recent_actions": [],
            "goal_progress": {},
            "projects": {},
            "services": {},
            "browser": {"current_url": "", "title": "", "tabs": [], "errors": {}},
            "workflows": {},
            "helpers": {},
            "updated_at": "",
        }

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    merged = self._default()
                    merged.update(data)
                    return merged
            except Exception:
                pass
        return self._default()

    def save(self):
        try:
            self.path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        except Exception:
            pass

    def snapshot(self, limit: int = 5) -> Dict[str, Any]:
        return {
            "last_action": self.state.get("last_action", {}),
            "goal_progress": self.state.get("goal_progress", {}),
            "browser": self.state.get("browser", {}),
            "workflows": list(self.state.get("workflows", {}).keys())[:20],
            "helpers": list(self.state.get("helpers", {}).keys())[:20],
            "recent_actions": self.state.get("recent_actions", [])[-limit:],
        }

    def snapshot_text(self, limit: int = 5) -> str:
        return json.dumps(self.snapshot(limit), indent=2, ensure_ascii=True)

    def _goal_key(self, goal: str) -> str:
        return hashlib.md5(goal.lower().strip().encode("utf-8")).hexdigest()[:12]

    def record_action(self, goal: str, run_id: str, tool_name: str, args: Dict[str, Any], result: Any, status: str, metadata: Optional[Dict[str, Any]] = None):
        entry = {
            "ts": datetime.now().isoformat(),
            "goal": goal,
            "goal_key": self._goal_key(goal),
            "run_id": run_id,
            "tool_name": tool_name,
            "args": args,
            "result": result[:1000] if isinstance(result, str) else str(result)[:1000],
            "status": status,
            "metadata": metadata or {},
        }
        self.state["last_action"] = entry
        self.state.setdefault("recent_actions", []).append(entry)
        self.state["recent_actions"] = self.state["recent_actions"][-100:]

        if tool_name in {"browser_open", "browser_click", "browser_type", "browser_wait", "open_browser"}:
            browser = self.state.setdefault("browser", {})
            browser["last_tool"] = tool_name
            if isinstance(args, dict) and args.get("url"):
                browser["current_url"] = args.get("url", browser.get("current_url", ""))
        if tool_name == "browser_snapshot":
            try:
                snap = json.loads(result) if isinstance(result, str) else result
                if isinstance(snap, dict):
                    browser = self.state.setdefault("browser", {})
                    browser["current_url"] = snap.get("url", browser.get("current_url", ""))
                    browser["title"] = snap.get("title", browser.get("title", ""))
                    browser["tabs"] = snap.get("tabs", browser.get("tabs", []))
                    browser["errors"] = {
                        "console": snap.get("console_errors", []),
                        "page": snap.get("page_errors", []),
                        "network": snap.get("network_failures", []),
                    }
            except Exception:
                pass
        if tool_name in {"save_workflow", "generate_workflow", "mutate_workflow", "run_workflow"} and isinstance(args, dict) and args.get("name"):
            self.state.setdefault("workflows", {})[args["name"]] = {
                "last_tool": tool_name,
                "updated_at": datetime.now().isoformat(),
                "last_result": entry["result"],
            }
        if tool_name in {"synthesize_helper", "run_helper"} and isinstance(args, dict) and args.get("name"):
            self.state.setdefault("helpers", {}).setdefault(args["name"], {})
            self.state["helpers"][args["name"]].update(
                {
                    "last_tool": tool_name,
                    "updated_at": datetime.now().isoformat(),
                    "last_result": entry["result"],
                }
            )

        self.state["updated_at"] = datetime.now().isoformat()
        self.save()

    def update_goal_progress(self, goal: str, progress: Dict[str, Any]):
        key = self._goal_key(goal)
        self.state.setdefault("goal_progress", {})[key] = {
            "goal": goal,
            "updated_at": datetime.now().isoformat(),
            **progress,
        }
        self.state["updated_at"] = datetime.now().isoformat()
        self.save()


class ToolRegistry:
    COMMON_ARG_ALIASES = {
        "cmd": "command",
        "shell_command": "command",
        "workdir": "cwd",
        "directory": "path",
        "dir": "path",
        "filepath": "path",
        "file_path": "path",
        "pathname": "path",
        "link": "url",
        "href": "url",
        "website": "url",
        "address": "url",
        "css": "selector",
        "locator": "selector",
        "element": "selector",
        "value": "text",
        "message": "text",
        "script": "code",
        "python": "code",
    }

    TOOL_ARG_ALIASES = {
        "run_shell_command": {
            "cmdline": "command",
            "shell": "command",
        },
        "browser_open": {
            "target": "url",
        },
        "open_browser": {
            "target": "url",
        },
        "read_file": {
            "file": "path",
            "filename": "path",
        },
        "write_file": {
            "file": "path",
            "filename": "path",
            "text": "content",
            "body": "content",
        },
        "browser_type": {
            "input": "text",
        },
        "fill_form_field": {
            "input": "value",
        },
    }

    def __init__(self, tools: Any):
        self.tools = tools
        self.specs = self._build_specs(tools.get_definitions())

    def _build_specs(self, definitions: List[Dict[str, Any]]) -> Dict[str, ToolSpec]:
        specs: Dict[str, ToolSpec] = {}
        for d in definitions:
            fn = d.get("function", {})
            name = fn.get("name")
            params = fn.get("parameters", {})
            required = params.get("required", []) if isinstance(params, dict) else []
            properties = params.get("properties", {}) if isinstance(params, dict) else {}
            if name:
                specs[name] = ToolSpec(
                    name=name,
                    required_args=required,
                    properties=properties if isinstance(properties, dict) else {},
                    description=fn.get("description", ""),
                )
        return specs

    def list_names(self) -> List[str]:
        return sorted(self.specs.keys())

    def validate(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
        if tool_name not in self.specs:
            return False, f"Unknown tool: {tool_name}"
        if not isinstance(args, dict):
            return False, f"Tool args for {tool_name} must be an object"
        spec = self.specs[tool_name]
        unexpected = [k for k in args if spec.properties and k not in spec.properties]
        if unexpected:
            return False, f"Unexpected args for {tool_name}: {', '.join(sorted(unexpected))}"
        missing = [k for k in spec.required_args if k not in args]
        if missing:
            return False, f"Missing required args for {tool_name}: {', '.join(missing)}"
        mismatched = []
        for key, schema in spec.properties.items():
            if key not in args:
                continue
            expected_type = schema.get("type")
            if expected_type and not self._matches_type(args[key], expected_type):
                mismatched.append(f"{key} should be {expected_type}")
        if mismatched:
            return False, f"Invalid arg types for {tool_name}: {', '.join(mismatched)}"
        return True, ""

    def describe_schema(self, tool_name: str) -> str:
        spec = self.specs.get(tool_name)
        if not spec:
            return f"Unknown tool: {tool_name}"
        properties = []
        for key, schema in spec.properties.items():
            type_name = schema.get("type", "any")
            suffix = " required" if key in spec.required_args else " optional"
            properties.append(f"{key}:{type_name}{suffix}")
        return f"{tool_name}({', '.join(properties)})"

    def repair_args(self, tool_name: str, args: Any) -> Tuple[Dict[str, Any], List[str]]:
        if tool_name not in self.specs:
            return args if isinstance(args, dict) else {}, []

        spec = self.specs[tool_name]
        repaired = dict(args) if isinstance(args, dict) else {}
        notes: List[str] = []
        aliases = dict(self.COMMON_ARG_ALIASES)
        aliases.update(self.TOOL_ARG_ALIASES.get(tool_name, {}))

        renamed: Dict[str, Any] = {}
        for key, value in repaired.items():
            canonical = aliases.get(key, key)
            if canonical != key:
                notes.append(f"mapped {key} -> {canonical}")
            if canonical not in renamed:
                renamed[canonical] = value
        repaired = renamed

        missing = [k for k in spec.required_args if k not in repaired]
        unexpected = [k for k in repaired if spec.properties and k not in spec.properties]

        if len(missing) == 1 and len(unexpected) == 1:
            source_key = unexpected[0]
            target_key = missing[0]
            source_value = repaired.get(source_key)
            if self._can_coerce_required_value(spec, target_key, source_value):
                repaired[target_key] = source_value
                notes.append(f"inferred {source_key} -> {target_key}")
                del repaired[source_key]

        if spec.properties:
            extra = [k for k in repaired if k not in spec.properties]
            for key in extra:
                repaired.pop(key, None)
                notes.append(f"dropped unexpected arg {key}")

        for key, schema in spec.properties.items():
            if key not in repaired:
                continue
            coerced, changed = self._coerce_value(repaired[key], schema.get("type"))
            if changed:
                repaired[key] = coerced
                notes.append(f"coerced {key} to {schema.get('type')}")

        return repaired, notes

    def _can_coerce_required_value(self, spec: ToolSpec, arg_name: str, value: Any) -> bool:
        expected_type = spec.properties.get(arg_name, {}).get("type")
        if not expected_type:
            return True
        return self._matches_type(value, expected_type) or self._coerce_value(value, expected_type)[1]

    def _coerce_value(self, value: Any, expected_type: Optional[str]) -> Tuple[Any, bool]:
        if not expected_type:
            return value, False
        if self._matches_type(value, expected_type):
            return value, False
        try:
            if expected_type == "string":
                return str(value), True
            if expected_type == "integer" and isinstance(value, str):
                return int(value), True
            if expected_type == "number" and isinstance(value, str):
                return float(value), True
            if expected_type == "boolean" and isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "false"}:
                    return lowered == "true", True
        except (TypeError, ValueError):
            return value, False
        return value, False

    def _matches_type(self, value: Any, expected_type: str) -> bool:
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "number":
            return (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "object":
            return isinstance(value, dict)
        if expected_type == "array":
            return isinstance(value, list)
        return True


class PolicyEngine:
    DEFAULT_POLICY = {
        "filesystem": True,
        "terminal": True,
        "browser": True,
        "network": True,
        "workflow": True,
        "helpers": True,
        "auth": False,
        "github_pr": False,
        "os_control": False,
        "secrets": False,
    }

    TOOL_SCOPE = {
        "read_file": "filesystem",
        "write_file": "filesystem",
        "create_directory": "filesystem",
        "list_directory": "filesystem",
        "search_files": "filesystem",
        "run_shell_command": "terminal",
        "open_browser": "browser",
        "browser_open": "browser",
        "browser_click": "browser",
        "browser_type": "browser",
        "browser_wait": "browser",
        "browser_snapshot": "browser",
        "browser_close": "browser",
        "manage_browser_tabs": "browser",
        "click_element": "browser",
        "fill_form_field": "browser",
        "browser_login": "auth",
        "save_workflow": "workflow",
        "list_workflows": "workflow",
        "run_workflow": "workflow",
        "generate_workflow": "workflow",
        "mutate_workflow": "workflow",
        "synthesize_helper": "helpers",
        "run_helper": "helpers",
        "list_helpers": "helpers",
        "web_scrape": "network",
        "download_file": "network",
        "network_operations": "network",
        "check_website_status": "network",
        "github_get_pull_request": "github_pr",
        "github_list_pull_requests": "github_pr",
        "github_submit_pull_review": "github_pr",
        "github_merge_pull_request": "github_pr",
        "manage_processes": "os_control",
        "registry_operations": "os_control",
        "control_media": "os_control",
        "schedule_task": "os_control",
        "take_screenshot": "os_control",
        "save_user_preference": "secrets",
        "get_user_preference": "secrets",
        "send_email": "secrets",
        "install_package": "os_control",
    }

    def __init__(self):
        self.policy = self._load_policy()

    def _load_policy(self) -> Dict[str, bool]:
        if AgentConfig.POLICY_FILE.exists():
            try:
                stored = json.loads(AgentConfig.POLICY_FILE.read_text(encoding="utf-8"))
                base = dict(self.DEFAULT_POLICY)
                for k, v in stored.items():
                    if k in base:
                        base[k] = bool(v)
                return base
            except Exception:
                pass
        self._save_policy(dict(self.DEFAULT_POLICY))
        return dict(self.DEFAULT_POLICY)

    def _save_policy(self, policy: Dict[str, bool]):
        try:
            AgentConfig.POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
            AgentConfig.POLICY_FILE.write_text(json.dumps(policy, indent=2), encoding="utf-8")
        except PermissionError:
            _rebase_agent_storage(Path.cwd() / ".ai_assistant_agent")
            AgentConfig.DATA_DIR.mkdir(parents=True, exist_ok=True)
            AgentConfig.RUNS_DIR.mkdir(parents=True, exist_ok=True)
            AgentConfig.POLICY_FILE.write_text(json.dumps(policy, indent=2), encoding="utf-8")

    def get_policy(self) -> Dict[str, bool]:
        return dict(self.policy)

    def set_scope(self, scope: str, enabled: bool) -> Tuple[bool, str]:
        if scope not in self.policy:
            return False, f"Unknown scope: {scope}"
        self.policy[scope] = bool(enabled)
        self._save_policy(self.policy)
        return True, f"Scope '{scope}' set to {'on' if enabled else 'off'}"

    def scope_for_task(self, task: Task) -> str:
        if task.tool_name in self.TOOL_SCOPE:
            return self.TOOL_SCOPE[task.tool_name]
        if task.tool_name.startswith("github_"):
            return "github_pr"
        return "terminal" if task.tool_name == "run_shell_command" else "filesystem"

    def allow_task(self, task: Task) -> Tuple[bool, str, str]:
        scope = self.scope_for_task(task)
        if not self.policy.get(scope, False):
            return False, f"Blocked by policy scope '{scope}'", scope
        return True, "", scope


class AuditLogger:
    def __init__(self, secret: str):
        self.secret = secret.encode("utf-8")
        self.last_sig = self._load_last_signature()

    def _load_last_signature(self) -> str:
        if not AgentConfig.AUDIT_LOG_FILE.exists():
            return ""
        try:
            lines = AgentConfig.AUDIT_LOG_FILE.read_text(encoding="utf-8").splitlines()
            if not lines:
                return ""
            last = json.loads(lines[-1])
            return str(last.get("sig", ""))
        except Exception:
            return ""

    def log(
        self,
        run_id: str,
        event_type: str,
        task: Optional[Task] = None,
        payload: Optional[Dict[str, Any]] = None,
    ):
        record = {
            "ts": datetime.now().isoformat(),
            "run_id": run_id,
            "event": event_type,
            "task_id": task.id if task else "",
            "task_name": task.name if task else "",
            "tool_name": task.tool_name if task else "",
            "args": task.tool_args if task else {},
            "payload": payload or {},
            "prev_sig": self.last_sig,
        }
        raw = json.dumps(record, sort_keys=True, ensure_ascii=True).encode("utf-8")
        sig = hmac.new(self.secret, raw, hashlib.sha256).hexdigest()
        record["sig"] = sig
        try:
            AgentConfig.AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with AgentConfig.AUDIT_LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")
        except PermissionError:
            _rebase_agent_storage(Path.cwd() / ".ai_assistant_agent")
            AgentConfig.DATA_DIR.mkdir(parents=True, exist_ok=True)
            AgentConfig.RUNS_DIR.mkdir(parents=True, exist_ok=True)
            with AgentConfig.AUDIT_LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")
        self.last_sig = sig

    def tail(self, limit: int = 30) -> List[Dict[str, Any]]:
        if not AgentConfig.AUDIT_LOG_FILE.exists():
            return []
        try:
            lines = AgentConfig.AUDIT_LOG_FILE.read_text(encoding="utf-8").splitlines()
            return [json.loads(x) for x in lines[-limit:]]
        except Exception:
            return []


class SafetyManager:
    DANGEROUS_TOOLS = {
        "registry_operations",
        "manage_processes",
        "file_operations",
        "run_shell_command",
        "execute_python",
        "browser_login",
        "run_workflow",
        "run_helper",
    }
    DANGEROUS_SHELL_PATTERNS = [
        r"\brm\s+-rf\b",
        r"\bdel\s+/f\b",
        r"\bformat\b",
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bRemove-Item\b",
        r"\bSet-ItemProperty\b",
    ]

    def __init__(self, confirm_callback: Optional[Callable[[Task], bool]] = None):
        self.confirm_callback = confirm_callback

    def needs_confirmation(self, task: Task) -> bool:
        if task.tool_name not in self.DANGEROUS_TOOLS:
            return False
        if task.tool_name == "file_operations":
            return task.tool_args.get("operation") in {"delete", "move"}
        if task.tool_name == "manage_processes":
            return task.tool_args.get("action") == "kill"
        if task.tool_name == "run_shell_command":
            cmd = str(task.tool_args.get("command", ""))
            return any(re.search(p, cmd, flags=re.IGNORECASE) for p in self.DANGEROUS_SHELL_PATTERNS)
        if task.tool_name == "run_workflow":
            return True
        return True

    def confirm(self, task: Task) -> bool:
        if not AgentConfig.REQUIRE_DANGEROUS_CONFIRMATION:
            return True
        if self.confirm_callback:
            return self.confirm_callback(task)
        prompt = (
            f"\n[Safety] Confirm dangerous action?\n"
            f"Tool: {task.tool_name}\nArgs: {json.dumps(task.tool_args, ensure_ascii=True)}\n"
            f"Type 'yes' to continue: "
        )
        return input(prompt).strip().lower() == "yes"


class Planner:
    def __init__(self, ai_model: Any, memory: MemorySystem, world_state: Optional[WorldStateStore] = None):
        self.ai = ai_model
        self.memory = memory
        self.world_state = world_state or WorldStateStore()

    def create_plan(self, goal: str, registry: ToolRegistry, run_id: str, revision: int = 0) -> Plan:
        related = self.memory.search(goal, limit=6)
        prompt = self._planner_prompt(goal, registry.list_names(), related)
        tasks_data = self._ask_ai_for_tasks(prompt)
        if not tasks_data:
            tasks_data = self._heuristic_plan(goal, registry.list_names())

        tasks = self._normalize_tasks(tasks_data, run_id=run_id, revision=revision, tool_names=registry.list_names())
        if not tasks:
            tasks = self._normalize_tasks(self._heuristic_plan(goal, registry.list_names()), run_id, revision, registry.list_names())

        self.memory.add_context({"type": "plan_created", "goal": goal, "task_count": len(tasks), "revision": revision})
        return Plan(id=f"{run_id}_r{revision}", goal=goal, tasks=tasks, revision=revision)

    def replan(self, run: RunState, failed_task: Task, error: str, registry: ToolRegistry) -> Plan:
        prompt = f"""
Goal: {run.goal}
Failed task: {failed_task.name}
Tool: {failed_task.tool_name}
Error: {error}

Create an updated JSON task array that avoids the failed approach.
Only use these tools: {', '.join(registry.list_names())}
"""
        tasks_data = self._ask_ai_for_tasks(prompt)
        if not tasks_data:
            tasks_data = self._heuristic_plan(run.goal, registry.list_names(), failed_task=failed_task)
        revision = run.replan_count + 1
        tasks = self._normalize_tasks(tasks_data, run.run_id, revision, registry.list_names())
        return Plan(id=f"{run.run_id}_r{revision}", goal=run.goal, tasks=tasks, revision=revision)

    def _planner_prompt(self, goal: str, tool_names: List[str], related_memories: List[Dict[str, Any]]) -> str:
        memories = json.dumps(related_memories[:4], ensure_ascii=True)
        environment = self._environment_context()
        world_state = self.world_state.snapshot_text()
        return f"""
You are planning executable tasks for an autonomous operator.
Goal: {goal}
Available tools: {', '.join(tool_names)}
Related memory: {memories}
Environment snapshot:
{environment}
World state:
{world_state}

Return ONLY JSON array. Each item:
{{
  "name": "...",
  "description": "...",
  "rationale": "...",
  "tool_name": "...",
  "tool_args": {{}},
  "dependencies": [0, 1],
  "verification": "file_exists:path OR output_contains:text OR done"
}}

Rules:
- 2 to {AgentConfig.MAX_PLAN_STEPS} tasks.
- Dependencies are indices of earlier tasks.
- Prefer deterministic verification checks.
- Use primitive actions only. Do not invent task-specific tools like create_website or deploy_app.
- Plans should follow an action loop: inspect current state, create or change an artifact, execute or preview it, observe the result, then adjust.
- Prefer reading files, listing directories, running shell commands, and writing concrete files over placeholders.
- For product or website goals, infer the intended artifact structure first: brand, navigation, shared layout, core sections, and coherent cross-page relationships.
- If no direct tool fits, prefer execute_python to synthesize a targeted solution instead of giving up.
- For multi-step reusable work, you may generate a workflow first and then run it.
- If a capability is missing, synthesize a helper tool first, then use it.
"""

    def _environment_context(self) -> str:
        root = Path.cwd()
        markers = []
        for name in ["package.json", "requirements.txt", "pyproject.toml", ".env", "README.md"]:
            if (root / name).exists():
                markers.append(name)

        entries = []
        try:
            for item in sorted(root.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))[:20]:
                entries.append(f"{'[D]' if item.is_dir() else '[F]'} {item.name}")
        except Exception:
            entries.append("(unavailable)")

        return (
            f"cwd={root}\n"
            f"markers={', '.join(markers) if markers else '(none)'}\n"
            "entries:\n" + "\n".join(entries)
        )

    def _ask_ai_for_tasks(self, prompt: str) -> List[Dict[str, Any]]:
        messages = [
            {"role": "system", "content": "Return strict JSON. No markdown."},
            {"role": "user", "content": prompt},
        ]
        try:
            response = self.ai.chat(messages)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            return self._extract_json_array(content)
        except Exception:
            return []

    def _extract_json_array(self, content: str) -> List[Dict[str, Any]]:
        if not content:
            return []
        match = re.search(r"\[[\s\S]*\]", content)
        if not match:
            return []
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, list) else []
        except Exception:
            return []

    def _heuristic_plan(
        self,
        goal: str,
        tool_names: List[str],
        failed_task: Optional[Task] = None,
    ) -> List[Dict[str, Any]]:
        g = goal.lower()
        tasks: List[Dict[str, Any]] = []

        complex_markers = ["startup", "dashboard", "service", "workflow", "automation", "post on", "social", "ads", "campaign"]
        if any(marker in g for marker in complex_markers) and "generate_workflow" in tool_names and "run_workflow" in tool_names:
            workflow_name = re.sub(r"[^a-z0-9]+", "_", g)[:40].strip("_") or "generated_workflow"
            tasks = [
                {
                    "name": "Observe environment",
                    "description": "Inspect current state before building a reusable workflow.",
                    "rationale": "Ground workflow generation in the real workspace.",
                    "tool_name": "observe_environment" if "observe_environment" in tool_names else "list_directory",
                    "tool_args": {"path": ".", "depth": 2} if "observe_environment" in tool_names else {"path": "."},
                    "dependencies": [],
                    "verification": "output_contains:",
                },
                {
                    "name": "Generate workflow",
                    "description": "Create a reusable workflow for the goal.",
                    "rationale": "Let the agent synthesize the action sequence instead of depending on a hand-authored flow.",
                    "tool_name": "generate_workflow",
                    "tool_args": {"name": workflow_name, "goal": goal, "description": f"Workflow for: {goal}"},
                    "dependencies": [0],
                    "verification": "output_contains:Saved workflow",
                },
                {
                    "name": "Run generated workflow",
                    "description": "Execute the workflow and allow dynamic mutation if steps are wrong.",
                    "rationale": "Turn the workflow into a living strategy rather than a fixed script.",
                    "tool_name": "run_workflow",
                    "tool_args": {"name": workflow_name, "loop_count": 1, "inputs": {}},
                    "dependencies": [1],
                    "verification": "output_contains:status",
                },
            ]
            return tasks[: AgentConfig.MAX_PLAN_STEPS]

        if ("next.js" in g or "nextjs" in g or "next js" in g or "create-next-app" in g) and "run_shell_command" in tool_names:
            tasks = [
                {
                    "name": "Observe environment",
                    "description": "Inspect the workspace before initializing the app repo.",
                    "rationale": "Ground the run in the current repo and project state.",
                    "tool_name": "observe_environment" if "observe_environment" in tool_names else "list_directory",
                    "tool_args": {"path": ".", "depth": 2} if "observe_environment" in tool_names else {"path": "."},
                    "dependencies": [],
                    "verification": "output_contains:",
                },
                {
                    "name": "Create Next.js app",
                    "description": "Initialize a real Next.js application with npm.",
                    "rationale": "Use the framework-native scaffold instead of inventing app structure by hand.",
                    "tool_name": "run_shell_command",
                    "tool_args": {
                        "command": "npx create-next-app@latest project_site --ts --eslint --app --src-dir --use-npm --yes",
                        "session_id": "dev",
                    },
                    "dependencies": [0],
                    "verification": "repo_marker:project_site/package.json",
                },
                {
                    "name": "Move shell into app directory",
                    "description": "Persist the working directory for the dev session.",
                    "rationale": "A real engineering agent keeps execution state instead of re-sending stateless cd calls.",
                    "tool_name": "run_shell_command",
                    "tool_args": {
                        "command": "cd project_site",
                        "session_id": "dev",
                    },
                    "dependencies": [1],
                    "verification": "shell_cwd:project_site",
                },
                {
                    "name": "Verify project installs cleanly",
                    "description": "Run a deterministic project command inside the app directory.",
                    "rationale": "Ground success in a real framework command, not a fake loop.",
                    "tool_name": "run_shell_command",
                    "tool_args": {
                        "command": "npm run lint",
                        "session_id": "dev",
                    },
                    "dependencies": [2],
                    "verification": "shell_success",
                },
                {
                    "name": "Initialize git history",
                    "description": "Create a real repository with an initial commit.",
                    "rationale": "Repo state is a first-class part of a coding agent runtime.",
                    "tool_name": "run_shell_command",
                    "tool_args": {
                        "command": "git init; git add .; git commit -m \"init next app\"",
                        "session_id": "dev",
                    },
                    "dependencies": [3],
                    "verification": "shell_success",
                },
            ]
            return tasks[: AgentConfig.MAX_PLAN_STEPS]

        if "website" in g or "landing page" in g:
            site_name = "project_site"
            brief = self._website_brief(goal)
            tasks.extend(
                [
                    {
                        "name": "Observe environment",
                        "description": "Inspect the workspace and project markers before creating files.",
                        "rationale": "Avoid blind writes and let the plan adapt to what already exists.",
                        "tool_name": "observe_environment" if "observe_environment" in tool_names else "list_directory",
                        "tool_args": {"path": ".", "depth": 2} if "observe_environment" in tool_names else {"path": "."},
                        "dependencies": [],
                        "verification": "output_contains:",
                    },
                    {
                        "name": "Create website folder",
                        "description": "Create a folder for the site source files.",
                        "rationale": "Establish a concrete workspace for generated assets.",
                        "tool_name": "create_directory" if "create_directory" in tool_names else tool_names[0],
                        "tool_args": {"path": site_name},
                        "dependencies": [0],
                        "verification": f"dir_exists:{site_name}",
                    },
                    {
                        "name": "Write shared stylesheet",
                        "description": "Create a shared design system stylesheet for all pages.",
                        "rationale": "A coherent site needs one visual system instead of isolated page styling.",
                        "tool_name": "write_file" if "write_file" in tool_names else tool_names[0],
                        "tool_args": {
                            "path": f"{site_name}/styles.css",
                            "content": self._website_stylesheet(brief),
                        },
                        "dependencies": [1],
                        "verification": f"file_exists:{site_name}/styles.css",
                    },
                    {
                        "name": "Write landing page",
                        "description": "Create the main landing page with hero, proof, feature grid, and calls to action.",
                        "rationale": "The home page should express the product story, not just exist as a placeholder file.",
                        "tool_name": "write_file" if "write_file" in tool_names else tool_names[0],
                        "tool_args": {
                            "path": f"{site_name}/index.html",
                            "content": self._website_index_html(brief),
                        },
                        "dependencies": [2],
                        "verification": f"file_exists:{site_name}/index.html",
                    },
                    {
                        "name": "Write about page",
                        "description": "Create a supporting page that explains the company and links back into the site.",
                        "rationale": "Supporting pages should share navigation and reinforce the brand system.",
                        "tool_name": "write_file" if "write_file" in tool_names else tool_names[0],
                        "tool_args": {
                            "path": f"{site_name}/about.html",
                            "content": self._website_about_html(brief),
                        },
                        "dependencies": [2],
                        "verification": f"file_exists:{site_name}/about.html",
                    },
                    {
                        "name": "Write contact page",
                        "description": "Create a conversion-oriented contact page with the same navigation and styling.",
                        "rationale": "A real site needs connected pathways for visitors to take action.",
                        "tool_name": "write_file" if "write_file" in tool_names else tool_names[0],
                        "tool_args": {
                            "path": f"{site_name}/contact.html",
                            "content": self._website_contact_html(brief),
                        },
                        "dependencies": [2],
                        "verification": f"file_exists:{site_name}/contact.html",
                    },
                ]
            )
            browser_open_tool = "browser_open" if "browser_open" in tool_names else ("open_browser" if "open_browser" in tool_names else "")
            if browser_open_tool:
                tasks.append(
                    {
                        "name": "Preview website",
                        "description": "Open the generated HTML file in the browser.",
                        "rationale": "Observe the real output and keep the loop grounded in execution.",
                        "tool_name": browser_open_tool,
                        "tool_args": {"url": str((Path.cwd() / site_name / "index.html").resolve().as_uri())},
                        "dependencies": [3, 4, 5],
                        "verification": "output_contains:Opened",
                    }
                )
                if "browser_snapshot" in tool_names:
                    tasks.append(
                        {
                            "name": "Inspect rendered page",
                            "description": "Capture structured browser context after opening the page.",
                            "rationale": "Use DOM and error context, not just a file path, to judge the result.",
                            "tool_name": "browser_snapshot",
                            "tool_args": {"include_screenshot": True},
                            "dependencies": [6],
                            "verification": "output_contains:title",
                        }
                    )

        if "script" in g or "python" in g:
            tasks = [
                {
                    "name": "Observe environment",
                    "description": "Inspect the workspace before generating code.",
                    "rationale": "Avoid overwriting blindly and capture the current project state.",
                    "tool_name": "observe_environment" if "observe_environment" in tool_names else "list_directory",
                    "tool_args": {"path": ".", "depth": 2} if "observe_environment" in tool_names else {"path": "."},
                    "dependencies": [],
                    "verification": "output_contains:",
                },
                {
                    "name": "Write script file",
                    "description": "Generate script skeleton in workspace.",
                    "rationale": "Produce runnable artifact.",
                    "tool_name": "write_file" if "write_file" in tool_names else "run_shell_command",
                    "tool_args": {
                        "path": "generated_script.py",
                        "content": "print('hello from autonomous agent')\n",
                    },
                    "dependencies": [0],
                    "verification": "file_exists:generated_script.py",
                },
                {
                    "name": "Run script",
                    "description": "Execute generated script and check output.",
                    "rationale": "Close loop with execution check.",
                    "tool_name": "run_shell_command",
                    "tool_args": {"command": "python generated_script.py"},
                    "dependencies": [1],
                    "verification": "output_contains:hello",
                },
            ]

        if ("scrape" in g or "crawl" in g) and ("website" in g or "site" in g or "http" in g):
            target_url = self._extract_url(goal) or "https://example.com"
            if "execute_python" in tool_names:
                tasks = [
                    {
                        "name": "Observe environment",
                        "description": "Inspect the workspace before generating scraping logic.",
                        "rationale": "Capture the current state before synthesizing a custom approach.",
                        "tool_name": "observe_environment" if "observe_environment" in tool_names else "list_directory",
                        "tool_args": {"path": ".", "depth": 2} if "observe_environment" in tool_names else {"path": "."},
                        "dependencies": [],
                        "verification": "output_contains:",
                    },
                    {
                        "name": "Synthesize scraping code",
                        "description": "Generate Python code to fetch and summarize the target page.",
                        "rationale": "No single fixed tool is as flexible as generated code for arbitrary pages.",
                        "tool_name": "execute_python",
                        "tool_args": {
                            "code": self._scrape_summary_code(target_url),
                        },
                        "dependencies": [0],
                        "verification": "output_contains:SUMMARY:",
                    },
                ]

        if not tasks:
            if "synthesize_helper" in tool_names and "run_helper" in tool_names:
                helper_name = "helper_" + re.sub(r"\W+", "_", goal.lower())[:32].strip("_") or "helper_generic"
                tasks = [
                    {
                        "name": "Observe environment",
                        "description": "Inspect the workspace before synthesizing a helper.",
                        "rationale": "Ground the helper in real state.",
                        "tool_name": "observe_environment" if "observe_environment" in tool_names else "list_directory",
                        "tool_args": {"path": ".", "depth": 2} if "observe_environment" in tool_names else {"path": "."},
                        "dependencies": [],
                        "verification": "output_contains:",
                    },
                    {
                        "name": "Synthesize helper",
                        "description": "Create a narrow helper for the missing capability.",
                        "rationale": "Expand capability in a bounded way instead of forcing an awkward existing tool.",
                        "tool_name": "synthesize_helper",
                        "tool_args": {
                            "name": helper_name,
                            "purpose": goal,
                            "signature": "run(payload) -> JSON/text",
                        },
                        "dependencies": [0],
                        "verification": "output_contains:Synthesized helper",
                    },
                    {
                        "name": "Run helper",
                        "description": "Execute the synthesized helper with minimal input.",
                        "rationale": "Verify the new capability and capture its behavior.",
                        "tool_name": "run_helper",
                        "tool_args": {
                            "name": helper_name,
                            "payload": {"goal": goal},
                        },
                        "dependencies": [1],
                        "verification": "output_contains:",
                    },
                ]
            elif "execute_python" in tool_names:
                tasks = [
                    {
                        "name": "Observe environment",
                        "description": "Inspect the workspace before synthesizing a solution.",
                        "rationale": "Ground the fallback in actual environment state.",
                        "tool_name": "observe_environment" if "observe_environment" in tool_names else "list_directory",
                        "tool_args": {"path": ".", "depth": 2} if "observe_environment" in tool_names else {"path": "."},
                        "dependencies": [],
                        "verification": "output_contains:",
                    },
                    {
                        "name": "Generate custom Python solution",
                        "description": "Write and run a targeted Python snippet for the goal.",
                        "rationale": "Break out of the fixed tool boundary when no direct action fits.",
                        "tool_name": "execute_python",
                        "tool_args": {
                            "code": self._generic_goal_code(goal, failed_task),
                        },
                        "dependencies": [0],
                        "verification": "output_contains:GOAL:",
                    },
                ]
            else:
                safe_goal = goal.replace('"', "").replace("'", "")[:120]
                cmd = f"echo {safe_goal}"
                if failed_task and failed_task.tool_name == "run_shell_command":
                    cmd = "echo fallback execution"
                tasks = [
                    {
                        "name": "Execute goal with shell",
                        "description": "Fallback execution pathway for unsupported goals.",
                        "rationale": "Guarantees progress.",
                        "tool_name": "run_shell_command" if "run_shell_command" in tool_names else tool_names[0],
                        "tool_args": {"command": cmd},
                        "dependencies": [],
                        "verification": "output_contains:",
                    }
                ]

        return tasks[: AgentConfig.MAX_PLAN_STEPS]

    def _website_brief(self, goal: str) -> Dict[str, str]:
        lowered = goal.lower()
        brand = self._extract_brand_name(goal)
        audience = "product and operations teams"
        if "startup" in lowered or "saas" in lowered:
            audience = "modern software teams"
        elif "agency" in lowered:
            audience = "clients and internal teams"
        tone = "confident, technical, and credible"
        value_prop = f"{brand} helps {audience} automate execution without losing operational control."
        if "labs" in brand.lower():
            value_prop = f"{brand} turns autonomous workflows into a clean operating layer for modern teams."
        return {
            "brand": brand,
            "tagline": "Autonomous systems with operational discipline",
            "value_prop": value_prop,
            "audience": audience,
            "primary_cta": "Book a walkthrough",
            "secondary_cta": "See how it works",
            "title": f"{brand} | Autonomous Operations Platform",
        }

    def _extract_brand_name(self, goal: str) -> str:
        quoted = re.search(r"['\"]([^'\"]{2,40})['\"]", goal)
        if quoted:
            return quoted.group(1).strip()
        match = re.search(r"(?:for|named)\s+([A-Za-z0-9][A-Za-z0-9\s&-]{1,40})", goal, flags=re.IGNORECASE)
        if match:
            candidate = re.split(r"\b(?:website|landing page|site|home page|startup)\b", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
            candidate = candidate.strip(" .,-")
            if candidate:
                return " ".join(word.capitalize() if word.islower() else word for word in candidate.split())
        title_case = re.findall(r"\b[A-Z][a-zA-Z0-9]+\b", goal)
        if title_case:
            return " ".join(title_case[:2])
        return "AI Labs"

    def _website_nav(self, brand: str) -> str:
        return (
            "      <header class=\"site-header\">\n"
            f"        <a class=\"brand\" href=\"index.html\">{brand}</a>\n"
            "        <nav class=\"site-nav\">\n"
            "          <a href=\"index.html#platform\">Platform</a>\n"
            "          <a href=\"index.html#workflow\">Workflow</a>\n"
            "          <a href=\"about.html\">About</a>\n"
            "          <a href=\"contact.html\">Contact</a>\n"
            "        </nav>\n"
            "      </header>\n"
        )

    def _website_shell(self, brief: Dict[str, str], body: str, page_title: str) -> str:
        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            f"  <title>{page_title}</title>\n"
            "  <link rel=\"stylesheet\" href=\"styles.css\">\n"
            "</head>\n"
            "<body>\n"
            "  <div class=\"site-shell\">\n"
            f"{self._website_nav(brief['brand'])}"
            f"{body}"
            "    <footer class=\"site-footer\">\n"
            f"      <p>{brief['brand']} builds autonomous systems that stay legible to operators.</p>\n"
            "      <div class=\"footer-links\">\n"
            "        <a href=\"about.html\">About</a>\n"
            "        <a href=\"contact.html\">Contact</a>\n"
            "      </div>\n"
            "    </footer>\n"
            "  </div>\n"
            "</body>\n"
            "</html>\n"
        )

    def _website_index_html(self, brief: Dict[str, str]) -> str:
        body = (
            "    <main>\n"
            "      <section class=\"hero\">\n"
            "        <p class=\"eyebrow\">Autonomous Operations OS</p>\n"
            f"        <h1>{brief['brand']} gives teams a command layer for autonomous execution.</h1>\n"
            f"        <p class=\"lede\">{brief['value_prop']}</p>\n"
            "        <div class=\"hero-actions\">\n"
            f"          <a class=\"button primary\" href=\"contact.html\">{brief['primary_cta']}</a>\n"
            f"          <a class=\"button secondary\" href=\"#platform\">{brief['secondary_cta']}</a>\n"
            "        </div>\n"
            "      </section>\n"
            "      <section class=\"proof-strip\">\n"
            "        <div><strong>Plan</strong><span>Translate intent into concrete workflows</span></div>\n"
            "        <div><strong>Execute</strong><span>Run tools, browsers, and files in sequence</span></div>\n"
            "        <div><strong>Adapt</strong><span>Observe failures and replan with context</span></div>\n"
            "      </section>\n"
            "      <section id=\"platform\" class=\"content-grid\">\n"
            "        <article class=\"card\">\n"
            "          <h2>Goal-aware planning</h2>\n"
            "          <p>Interpret product intent before choosing tasks, files, and architecture.</p>\n"
            "        </article>\n"
            "        <article class=\"card\">\n"
            "          <h2>Stable execution contracts</h2>\n"
            "          <p>Validate and repair tool calls so autonomy survives schema drift.</p>\n"
            "        </article>\n"
            "        <article class=\"card\">\n"
            "          <h2>Visible operations</h2>\n"
            "          <p>Keep browser snapshots, world state, and audit traces attached to the loop.</p>\n"
            "        </article>\n"
            "      </section>\n"
            "      <section id=\"workflow\" class=\"workflow-panel\">\n"
            "        <div>\n"
            "          <p class=\"eyebrow\">From task runner to product builder</p>\n"
            "          <h2>One system for planning, execution, observation, and refinement.</h2>\n"
            "        </div>\n"
            "        <ol class=\"workflow-list\">\n"
            "          <li>Capture product intent and operating constraints.</li>\n"
            "          <li>Generate a coherent artifact structure and shared design system.</li>\n"
            "          <li>Preview the result, score quality, and iterate if the output is weak.</li>\n"
            "        </ol>\n"
            "      </section>\n"
            "    </main>\n"
        )
        return self._website_shell(brief, body, brief["title"])

    def _website_about_html(self, brief: Dict[str, str]) -> str:
        body = (
            "    <main class=\"inner-page\">\n"
            "      <section class=\"page-intro\">\n"
            "        <p class=\"eyebrow\">About</p>\n"
            f"        <h1>Why {brief['brand']} exists</h1>\n"
            "        <p class=\"lede\">Autonomous execution becomes useful only when strategy, tooling, and human oversight stay connected.</p>\n"
            "      </section>\n"
            "      <section class=\"content-grid two-up\">\n"
            "        <article class=\"card\">\n"
            "          <h2>Design principle</h2>\n"
            "          <p>Every action should trace back to product intent, not just a checklist of tool calls.</p>\n"
            "        </article>\n"
            "        <article class=\"card\">\n"
            "          <h2>Operating model</h2>\n"
            "          <p>Shared memory, strict contracts, and post-run evaluation keep the system coherent as it scales.</p>\n"
            "        </article>\n"
            "      </section>\n"
            "    </main>\n"
        )
        return self._website_shell(brief, body, f"About | {brief['brand']}")

    def _website_contact_html(self, brief: Dict[str, str]) -> str:
        body = (
            "    <main class=\"inner-page\">\n"
            "      <section class=\"page-intro\">\n"
            "        <p class=\"eyebrow\">Contact</p>\n"
            f"        <h1>Talk to the {brief['brand']} team</h1>\n"
            "        <p class=\"lede\">Use this page as the primary conversion path from the landing experience.</p>\n"
            "      </section>\n"
            "      <section class=\"contact-card card\">\n"
            "        <h2>Start a walkthrough</h2>\n"
            "        <p>Email hello@example.com or adapt this page with your real inbox and booking flow.</p>\n"
            "        <a class=\"button primary\" href=\"index.html\">Back to overview</a>\n"
            "      </section>\n"
            "    </main>\n"
        )
        return self._website_shell(brief, body, f"Contact | {brief['brand']}")

    def _website_stylesheet(self, brief: Dict[str, str]) -> str:
        return (
            ":root {\n"
            "  --bg: #f2efe8;\n"
            "  --paper: rgba(255, 252, 247, 0.92);\n"
            "  --ink: #182126;\n"
            "  --muted: #51606b;\n"
            "  --accent: #0f766e;\n"
            "  --accent-strong: #115e59;\n"
            "  --line: rgba(24, 33, 38, 0.12);\n"
            "  --shadow: 0 24px 60px rgba(24, 33, 38, 0.08);\n"
            "}\n"
            "* { box-sizing: border-box; }\n"
            "html { scroll-behavior: smooth; }\n"
            "body {\n"
            "  margin: 0;\n"
            "  font-family: Georgia, 'Times New Roman', serif;\n"
            "  color: var(--ink);\n"
            "  background:\n"
            "    radial-gradient(circle at top left, rgba(15, 118, 110, 0.14), transparent 30%),\n"
            "    linear-gradient(180deg, #fbf7f0 0%, var(--bg) 100%);\n"
            "}\n"
            "a { color: inherit; text-decoration: none; }\n"
            ".site-shell { width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 24px 0 48px; }\n"
            ".site-header, .site-footer {\n"
            "  display: flex;\n"
            "  align-items: center;\n"
            "  justify-content: space-between;\n"
            "  gap: 16px;\n"
            "}\n"
            ".site-header {\n"
            "  position: sticky;\n"
            "  top: 12px;\n"
            "  z-index: 10;\n"
            "  margin-bottom: 24px;\n"
            "  padding: 16px 20px;\n"
            "  border: 1px solid var(--line);\n"
            "  border-radius: 18px;\n"
            "  background: rgba(255, 252, 247, 0.85);\n"
            "  backdrop-filter: blur(12px);\n"
            "}\n"
            ".brand { font-size: 1.15rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }\n"
            ".site-nav { display: flex; flex-wrap: wrap; gap: 18px; color: var(--muted); }\n"
            ".hero, .workflow-panel, .page-intro, .contact-card {\n"
            "  border: 1px solid var(--line);\n"
            "  border-radius: 28px;\n"
            "  background: var(--paper);\n"
            "  box-shadow: var(--shadow);\n"
            "}\n"
            ".hero { padding: 72px 56px; }\n"
            ".eyebrow { margin: 0 0 12px; color: var(--accent-strong); text-transform: uppercase; letter-spacing: 0.14em; font-size: 0.8rem; }\n"
            "h1, h2 { line-height: 1.05; margin: 0 0 16px; }\n"
            "h1 { font-size: clamp(2.8rem, 8vw, 5.6rem); max-width: 11ch; }\n"
            "h2 { font-size: clamp(1.6rem, 3vw, 2.4rem); }\n"
            ".lede { max-width: 60ch; font-size: 1.1rem; color: var(--muted); }\n"
            ".hero-actions, .footer-links { display: flex; flex-wrap: wrap; gap: 12px; }\n"
            ".button {\n"
            "  display: inline-flex;\n"
            "  align-items: center;\n"
            "  justify-content: center;\n"
            "  min-height: 48px;\n"
            "  padding: 0 18px;\n"
            "  border-radius: 999px;\n"
            "  border: 1px solid var(--line);\n"
            "}\n"
            ".button.primary { background: var(--accent); color: #f8fffd; border-color: var(--accent); }\n"
            ".button.secondary { background: transparent; }\n"
            ".proof-strip, .content-grid { display: grid; gap: 18px; margin-top: 24px; }\n"
            ".proof-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }\n"
            ".content-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }\n"
            ".content-grid.two-up { grid-template-columns: repeat(2, minmax(0, 1fr)); }\n"
            ".proof-strip > div, .card {\n"
            "  padding: 22px;\n"
            "  border: 1px solid var(--line);\n"
            "  border-radius: 22px;\n"
            "  background: rgba(255, 255, 255, 0.65);\n"
            "}\n"
            ".proof-strip strong, .workflow-list li::marker { color: var(--accent-strong); }\n"
            ".proof-strip span, .card p, .workflow-list { color: var(--muted); }\n"
            ".workflow-panel, .page-intro, .contact-card { padding: 36px; margin-top: 24px; }\n"
            ".workflow-list { margin: 0; padding-left: 20px; display: grid; gap: 10px; }\n"
            ".site-footer { margin-top: 28px; padding: 8px 4px 0; color: var(--muted); }\n"
            "@media (max-width: 820px) {\n"
            "  .hero { padding: 40px 24px; }\n"
            "  .proof-strip, .content-grid, .content-grid.two-up { grid-template-columns: 1fr; }\n"
            "  .site-header, .site-footer { flex-direction: column; align-items: flex-start; }\n"
            "}\n"
        )

    def _extract_url(self, goal: str) -> str:
        match = re.search(r"https?://[^\s]+", goal)
        return match.group(0) if match else ""

    def _scrape_summary_code(self, url: str) -> str:
        safe_url = json.dumps(url)
        return (
            "import re\n"
            "import urllib.request\n"
            "from html import unescape\n"
            f"url = {safe_url}\n"
            "html = urllib.request.urlopen(url, timeout=15).read().decode('utf-8', errors='ignore')\n"
            "title_match = re.search(r'<title[^>]*>(.*?)</title>', html, flags=re.I | re.S)\n"
            "title = unescape(re.sub(r'\\s+', ' ', title_match.group(1)).strip()) if title_match else 'Untitled'\n"
            "text = re.sub(r'<script[\\s\\S]*?</script>', ' ', html, flags=re.I)\n"
            "text = re.sub(r'<style[\\s\\S]*?</style>', ' ', text, flags=re.I)\n"
            "text = re.sub(r'<[^>]+>', ' ', text)\n"
            "text = unescape(re.sub(r'\\s+', ' ', text)).strip()\n"
            "summary = text[:800]\n"
            "print('TITLE:', title)\n"
            "print('SUMMARY:', summary)\n"
        )

    def _generic_goal_code(self, goal: str, failed_task: Optional[Task]) -> str:
        safe_goal = json.dumps(goal)
        failure = json.dumps(failed_task.error if failed_task else '')
        return (
            f"goal = {safe_goal}\n"
            f"prior_failure = {failure}\n"
            "print('GOAL:', goal)\n"
            "if prior_failure:\n"
            "    print('PRIOR_FAILURE:', prior_failure)\n"
            "print('NEXT_STEP: analyze the goal, inspect the workspace, and synthesize the smallest useful artifact or command for it.')\n"
        )

    def _normalize_tasks(
        self,
        tasks_data: List[Dict[str, Any]],
        run_id: str,
        revision: int,
        tool_names: List[str],
    ) -> List[Task]:
        normalized: List[Task] = []
        for idx, row in enumerate(tasks_data[: AgentConfig.MAX_PLAN_STEPS]):
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", f"Task {idx + 1}"))
            tool_name = str(row.get("tool_name", "run_shell_command"))
            if tool_name not in tool_names:
                tool_name = "run_shell_command" if "run_shell_command" in tool_names else tool_names[0]
            args = row.get("tool_args", {})
            if not isinstance(args, dict):
                args = {}
            dep_indexes = row.get("dependencies", [])
            if not isinstance(dep_indexes, list):
                dep_indexes = []
            deps = [f"{run_id}_r{revision}_t{d}" for d in dep_indexes if isinstance(d, int) and d < idx]

            normalized.append(
                Task(
                    id=f"{run_id}_r{revision}_t{idx}",
                    name=name,
                    description=str(row.get("description", "")),
                    rationale=str(row.get("rationale", "")),
                    tool_name=tool_name,
                    tool_args=args,
                    dependencies=deps,
                    verification=str(row.get("verification", "done")),
                )
            )
        return normalized


class Verifier:
    def __init__(self, ai_model: Any):
        self.ai = ai_model

    def verify(self, task: Task, result: str) -> Tuple[bool, str]:
        if result is None:
            return False, "no result"
        if "Error executing" in result or result.strip().lower().startswith("error"):
            return False, "tool returned error"

        rule = task.verification.strip() if task.verification else "done"
        if rule in {"", "done"}:
            return True, "default pass"

        if rule.startswith("file_exists:"):
            path = Path(rule.split(":", 1)[1].strip())
            return path.exists(), f"file exists={path.exists()}"

        if rule.startswith("dir_exists:"):
            path = Path(rule.split(":", 1)[1].strip())
            return (path.exists() and path.is_dir()), f"dir exists={path.exists() and path.is_dir()}"

        if rule.startswith("output_contains:"):
            text = rule.split(":", 1)[1].strip().lower()
            if not text:
                return bool(result.strip()), "non-empty output"
            return text in result.lower(), f"output contains={text in result.lower()}"

        if rule == "shell_success":
            shell = self._parse_shell_result(result)
            ok = shell.get("ok") is True and int(shell.get("exit_code", 1)) == 0
            return ok, f"shell exit_code={shell.get('exit_code', 'unknown')}"

        if rule.startswith("shell_cwd:"):
            expected = rule.split(":", 1)[1].strip()
            shell = self._parse_shell_result(result)
            actual = str(shell.get("cwd", ""))
            return actual.endswith(expected) or actual == expected, f"shell cwd={actual}"

        if rule.startswith("repo_marker:"):
            marker = Path(rule.split(":", 1)[1].strip())
            return marker.exists(), f"repo marker exists={marker.exists()}"

        return self._ai_verify(task, result)

    def _parse_shell_result(self, result: str) -> Dict[str, Any]:
        parsed: Dict[str, Any] = {}
        if not isinstance(result, str) or not result.startswith("[SHELL_RESULT]"):
            return parsed
        for line in result.splitlines():
            if "=" in line and not line.endswith(":"):
                key, value = line.split("=", 1)
                parsed[key.strip()] = value.strip()
        if "exit_code" in parsed:
            try:
                parsed["exit_code"] = int(parsed["exit_code"])
            except Exception:
                pass
        if "ok" in parsed:
            parsed["ok"] = str(parsed["ok"]).lower() == "true"
        return parsed

    def _ai_verify(self, task: Task, result: str) -> Tuple[bool, str]:
        prompt = f"""
Task: {task.name}
Description: {task.description}
Tool: {task.tool_name}
Args: {json.dumps(task.tool_args, ensure_ascii=True)}
Result: {result}

Respond strictly as JSON: {{"success": true/false, "reason": "..."}}.
"""
        try:
            response = self.ai.chat(
                [
                    {"role": "system", "content": "You evaluate execution success."},
                    {"role": "user", "content": prompt},
                ]
            )
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            match = re.search(r"\{[\s\S]*\}", content)
            if not match:
                return True, "ai verifier fallback pass"
            payload = json.loads(match.group(0))
            return bool(payload.get("success")), str(payload.get("reason", "ai verification"))
        except Exception:
            return True, "ai verifier unavailable"


class Executor:
    def __init__(
        self,
        ai_model: Any,
        tools: Any,
        registry: ToolRegistry,
        verifier: Verifier,
        memory: MemorySystem,
        safety: SafetyManager,
        policy: PolicyEngine,
        audit: AuditLogger,
        world_state: WorldStateStore,
        emit_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        self.ai = ai_model
        self.tools = tools
        self.registry = registry
        self.verifier = verifier
        self.memory = memory
        self.safety = safety
        self.policy = policy
        self.audit = audit
        self.world_state = world_state
        self.emit_callback = emit_callback

    def run_plan(self, run: RunState) -> Tuple[RunState, Optional[Task]]:
        completed_ids = {t.id for t in run.plan.tasks if t.status == TaskStatus.COMPLETED}
        for task in self._sorted_tasks(run.plan.tasks):
            if task.status == TaskStatus.COMPLETED:
                continue
            if any(dep not in completed_ids for dep in task.dependencies):
                continue

            task.started_at = datetime.now().isoformat()
            task.status = TaskStatus.IN_PROGRESS
            decision = self._deliberate(run, task)
            self._emit_reasoning(run, task, decision)
            self._emit_action(run, task)
            self._event(run, "task_start", {"task_id": task.id, "name": task.name, "tool": task.tool_name})
            self.audit.log(run.run_id, "task_start", task, {"plan_revision": run.plan.revision})

            ok, err = self.registry.validate(task.tool_name, task.tool_args)
            if not ok:
                repaired, repair_reason = self._repair_invalid_tool_call(task, err)
                if repaired:
                    self._event(
                        run,
                        "task_schema_repaired",
                        {"task_id": task.id, "tool": task.tool_name, "reason": repair_reason, "args": task.tool_args},
                    )
                    self.audit.log(
                        run.run_id,
                        "task_schema_repaired",
                        task,
                        {"reason": repair_reason, "args": task.tool_args},
                    )
                    ok, err = self.registry.validate(task.tool_name, task.tool_args)
            if not ok:
                task.status = TaskStatus.FAILED
                task.error = err
                self._event(run, "task_failed", {"task_id": task.id, "error": err})
                self.audit.log(run.run_id, "task_failed", task, {"reason": err, "stage": "registry_validate"})
                return run, task

            allowed, deny_reason, scope = self.policy.allow_task(task)
            if not allowed:
                task.status = TaskStatus.FAILED
                task.error = deny_reason
                self._event(run, "task_blocked_policy", {"task_id": task.id, "scope": scope, "reason": deny_reason})
                self.audit.log(run.run_id, "task_blocked_policy", task, {"scope": scope, "reason": deny_reason})
                return run, task

            if self.safety.needs_confirmation(task):
                confirmed = self.safety.confirm(task)
                if not confirmed:
                    task.status = TaskStatus.FAILED
                    task.error = "User denied dangerous action"
                    self._event(run, "task_blocked", {"task_id": task.id, "reason": task.error})
                    self.audit.log(run.run_id, "task_blocked_confirmation", task, {"reason": task.error})
                    return run, task

            done = self._execute_with_retries(task, run.run_id, run.goal)
            if not done:
                self._emit_retry_reasoning(run, task)
                self._event(run, "task_failed", {"task_id": task.id, "error": task.error})
                self.audit.log(run.run_id, "task_failed", task, {"reason": task.error, "stage": "execute"})
                return run, task

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            completed_ids.add(task.id)
            self._emit_result(run, task)
            self._emit_patch(run, task)
            self._event(run, "task_done", {"task_id": task.id, "name": task.name})
            self.audit.log(run.run_id, "task_done", task, {"result_excerpt": task.result[:200]})
            self.world_state.record_action(run.goal, run.run_id, task.tool_name, task.tool_args, task.result, "completed", {"task_name": task.name})
            self._capture_observation(run, task)
            self.memory.add_pattern(f"{task.tool_name} succeeded for {task.name}", success_rate=1.0)

        return run, None

    def _execute_with_retries(self, task: Task, run_id: str, goal: str) -> bool:
        while task.retry_count < AgentConfig.MAX_RETRIES_PER_TASK:
            task.retry_count += 1
            self.audit.log(run_id, "task_attempt", task, {"attempt": task.retry_count})
            try:
                result = self.tools.execute(task.tool_name, task.tool_args)
                task.result = result if isinstance(result, str) else json.dumps(result, ensure_ascii=True)
            except Exception as exc:
                task.result = ""
                task.error = f"exception: {exc}"
                self.audit.log(run_id, "task_exception", task, {"error": str(exc), "attempt": task.retry_count})

            ok, reason = self.verifier.verify(task, task.result)
            if ok:
                task.error = ""
                return True

            task.error = reason
            self.memory.log_failure(task, reason, run_id)
            correction = self._request_correction(task, reason)
            task.tool_name = correction.get("tool_name", task.tool_name)
            tool_args = correction.get("tool_args", task.tool_args)
            if isinstance(tool_args, dict):
                task.tool_args = tool_args
            repaired, repair_reason = self._repair_invalid_tool_call(task, reason)
            if repaired:
                self.audit.log(run_id, "task_schema_repaired", task, {"reason": repair_reason, "stage": "retry"})
            self.audit.log(run_id, "task_correction", task, {"reason": reason, "suggested": correction})
            self.world_state.record_action(goal, run_id, task.tool_name, task.tool_args, task.result, "failed", {"reason": reason, "task_name": task.name})
        return False

    def _repair_invalid_tool_call(self, task: Task, error: str) -> Tuple[bool, str]:
        deterministic_args, notes = self.registry.repair_args(task.tool_name, task.tool_args)
        if deterministic_args != task.tool_args:
            task.tool_args = deterministic_args
            ok, _ = self.registry.validate(task.tool_name, task.tool_args)
            if ok:
                detail = "; ".join(notes) if notes else "deterministic schema repair"
                return True, detail

        correction = self._request_correction(task, error)
        new_tool_name = correction.get("tool_name", task.tool_name)
        if isinstance(new_tool_name, str) and new_tool_name in self.registry.specs:
            task.tool_name = new_tool_name
        new_args = correction.get("tool_args", task.tool_args)
        if isinstance(new_args, dict):
            task.tool_args = new_args
        task.tool_args, notes = self.registry.repair_args(task.tool_name, task.tool_args)
        ok, final_error = self.registry.validate(task.tool_name, task.tool_args)
        if ok:
            detail = correction.get("reason") or "; ".join(notes) or "model-assisted schema repair"
            return True, str(detail)
        return False, final_error

    def _request_correction(self, task: Task, error: str) -> Dict[str, Any]:
        prompt = f"""
Task failed.
Task name: {task.name}
Tool: {task.tool_name}
Schema: {self.registry.describe_schema(task.tool_name)}
Args: {json.dumps(task.tool_args, ensure_ascii=True)}
Error: {error}

Return JSON only:
{{"tool_name": "...", "tool_args": {{...}}, "reason": "..."}}
"""
        try:
            response = self.ai.chat(
                [
                    {"role": "system", "content": "Fix failed tool executions with minimal changes."},
                    {"role": "user", "content": prompt},
                ]
            )
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            match = re.search(r"\{[\s\S]*\}", content)
            if not match:
                return {}
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _sorted_tasks(self, tasks: List[Task]) -> List[Task]:
        task_map = {t.id: t for t in tasks}
        visiting: set[str] = set()
        visited: set[str] = set()
        order: List[Task] = []

        def dfs(task_id: str):
            if task_id in visited or task_id in visiting:
                return
            visiting.add(task_id)
            task = task_map.get(task_id)
            if task:
                for dep in task.dependencies:
                    dfs(dep)
                order.append(task)
            visiting.remove(task_id)
            visited.add(task_id)

        for t in tasks:
            dfs(t.id)
        return order

    def _event(self, run: RunState, event_type: str, payload: Dict[str, Any]):
        run.events.append({"ts": datetime.now().isoformat(), "type": event_type, "payload": payload})

    def _emit(self, event_type: str, payload: Dict[str, Any]):
        if self.emit_callback:
            self.emit_callback(event_type, payload)

    def _emit_action(self, run: RunState, task: Task):
        payload = {
            "run_id": run.run_id,
            "task_id": task.id,
            "task_name": task.name,
            "intent": self._infer_intent(task),
            "tool": task.tool_name,
            "action": self._render_action(task),
        }
        self._emit("action", payload)

    def _emit_result(self, run: RunState, task: Task):
        payload = {
            "run_id": run.run_id,
            "task_id": task.id,
            "task_name": task.name,
            "intent": self._infer_intent(task),
            "tool": task.tool_name,
            "summary": self._summarize_result(task),
        }
        self._emit("result", payload)

    def _emit_patch(self, run: RunState, task: Task):
        changes = self._patch_summary(task)
        if not changes:
            return
        payload = {
            "run_id": run.run_id,
            "task_id": task.id,
            "task_name": task.name,
            "intent": self._infer_intent(task),
            "target": self._patch_target(task),
            "changes": changes,
        }
        self.audit.log(run.run_id, "patch", task, {"changes": changes, "target": payload["target"]})
        self._emit("patch", payload)

    def _deliberate(self, run: RunState, task: Task) -> DecisionTrace:
        completed = [t.name for t in run.plan.tasks if t.status == TaskStatus.COMPLETED][-3:]
        pending = [t.name for t in run.plan.tasks if t.status == TaskStatus.PENDING][:3]
        latest_observation = self._latest_observation(run)
        prompt = f"""
You are deciding the next action for an autonomous operator.
Goal: {run.goal}
Current task: {task.name}
Task description: {task.description}
Tool: {task.tool_name}
Args: {json.dumps(task.tool_args, ensure_ascii=True)}
Completed tasks: {json.dumps(completed, ensure_ascii=True)}
Upcoming tasks: {json.dumps(pending, ensure_ascii=True)}
Latest observation: {latest_observation}

Return strict JSON:
{{
  "thought": "...",
  "plan": ["...", "..."],
  "next_action": "tool_name(args)"
}}
Keep the thought concrete and operational, not abstract.
"""
        try:
            response = self.ai.chat(
                [
                    {"role": "system", "content": "Think before acting. Return strict JSON only."},
                    {"role": "user", "content": prompt},
                ]
            )
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                parsed = json.loads(match.group(0))
                plan = parsed.get("plan", [])
                if not isinstance(plan, list):
                    plan = []
                return DecisionTrace(
                    thought=str(parsed.get("thought", "")).strip() or self._fallback_thought(run, task),
                    plan=[str(item) for item in plan[:4] if str(item).strip()],
                    next_action=str(parsed.get("next_action", "")).strip() or self._render_action(task),
                )
        except Exception:
            pass

        return DecisionTrace(
            thought=self._fallback_thought(run, task),
            plan=self._fallback_plan(run, task),
            next_action=self._render_action(task),
        )

    def _emit_reasoning(self, run: RunState, task: Task, decision: DecisionTrace):
        payload = {
            "run_id": run.run_id,
            "task_id": task.id,
            "task_name": task.name,
            "thought": decision.thought,
            "plan": decision.plan,
            "next_action": decision.next_action,
        }
        self._event(run, "reasoning", payload)
        self.audit.log(run.run_id, "reasoning", task, payload)
        self._emit("reasoning", payload)

    def _emit_retry_reasoning(self, run: RunState, task: Task):
        latest_observation = self._latest_observation(run)
        payload = {
            "run_id": run.run_id,
            "task_id": task.id,
            "task_name": task.name,
            "thought": f"The last action did not verify successfully. I need to adjust the approach based on the failure: {task.error}.",
            "plan": [
                "Inspect the failure signal",
                "Minimally adjust the tool or arguments",
                "Retry and verify again",
            ],
            "next_action": self._render_action(task),
            "observation": latest_observation,
        }
        self._event(run, "reasoning_retry", payload)
        self.audit.log(run.run_id, "reasoning_retry", task, payload)
        self._emit("reasoning_retry", payload)

    def _fallback_thought(self, run: RunState, task: Task) -> str:
        if task.tool_name == "observe_environment":
            return "I need current workspace state before changing anything so later actions are based on reality."
        if task.tool_name == "write_file":
            return "I have enough context to create or update a concrete artifact, so the next step is to write the file needed for progress."
        if task.tool_name == "run_shell_command":
            return "The next step requires execution to validate the artifact or gather a direct runtime signal."
        if task.tool_name in {"open_browser", "browser_open", "browser_click", "browser_type", "browser_wait"}:
            return "I need a visible preview to verify that the generated output actually opens as expected."
        return f"I need to execute '{task.name}' to move the goal forward while keeping the plan grounded in the current state."

    def _fallback_plan(self, run: RunState, task: Task) -> List[str]:
        steps = []
        if task.dependencies:
            steps.append("Use the outputs from completed dependencies")
        steps.append(task.name)
        remaining = [t.name for t in run.plan.tasks if t.status == TaskStatus.PENDING and t.id != task.id][:2]
        steps.extend(remaining)
        return steps[:4]

    def _render_action(self, task: Task) -> str:
        return f"{task.tool_name}({json.dumps(task.tool_args, ensure_ascii=True)})"

    def _latest_observation(self, run: RunState) -> str:
        for event in reversed(run.events):
            if event.get("type") == "observation":
                payload = event.get("payload", {})
                return str(payload.get("snapshot", ""))[:600]
        return "(none)"

    def _infer_intent(self, task: Task) -> str:
        tool = task.tool_name
        if tool == "create_directory":
            return "create_structure"
        if tool == "write_file":
            lowered = str(task.tool_args.get("path", "")).lower()
            if lowered.endswith(".css"):
                return "design_system"
            if lowered.endswith(".html"):
                return "build_ui"
            return "edit_code"
        if tool == "run_shell_command":
            return "execute_code"
        if tool in {"browser_open", "open_browser", "browser_click", "browser_type", "browser_wait"}:
            return "observe_ui"
        if tool == "browser_snapshot":
            return "capture_state"
        if tool == "observe_environment":
            return "inspect_workspace"
        return "advance_goal"

    def _summarize_result(self, task: Task) -> str:
        result = str(task.result or "").strip()
        if task.tool_name == "write_file":
            path = str(task.tool_args.get("path", ""))
            content = str(task.tool_args.get("content", ""))
            return f"updated {path} with {len(content.splitlines())} lines"
        if task.tool_name == "create_directory":
            return f"created {task.tool_args.get('path', '')}"
        if task.tool_name == "run_shell_command":
            shell = self.verifier._parse_shell_result(result)
            exit_code = shell.get("exit_code", "unknown")
            cwd = shell.get("cwd", "")
            stdout = str(result)
            if shell:
                stdout = str(shell.get("stdout", "") or shell.get("stderr", "") or "").strip()
            preview = " | ".join([line.strip() for line in stdout.splitlines() if line.strip()][:2]) if stdout else "(no output)"
            return f"exit={exit_code} cwd={cwd} {preview}".strip()
        if task.tool_name == "browser_snapshot":
            try:
                data = json.loads(result) if result.startswith("{") else {}
                title = data.get("title", "")
                url = data.get("url", "")
                return f"captured {title or 'page'} at {url}".strip()
            except Exception:
                pass
        return result[:180] if result else "(done)"

    def _patch_target(self, task: Task) -> str:
        if task.tool_name in {"write_file", "create_directory"}:
            return str(task.tool_args.get("path", ""))
        return task.tool_name

    def _patch_summary(self, task: Task) -> List[str]:
        if task.tool_name == "create_directory":
            target = str(task.tool_args.get("path", ""))
            return [f"+ Created workspace `{target}`"] if target else []
        if task.tool_name == "run_shell_command":
            shell = self.verifier._parse_shell_result(str(task.result or ""))
            lines = [f"+ Ran `{task.tool_args.get('command', '')}`"]
            if shell.get("cwd"):
                lines.append(f"+ Session cwd `{shell.get('cwd')}`")
            if shell.get("exit_code") == 0:
                lines.append("+ Command exited successfully")
            return lines[:4]
        if task.tool_name != "write_file":
            return []

        path = str(task.tool_args.get("path", ""))
        content = str(task.tool_args.get("content", ""))
        suffix = Path(path).suffix.lower()
        lines: List[str] = []
        if isinstance(task.result, str) and task.result.startswith("[WRITE_RESULT]"):
            diff_started = False
            for raw_line in task.result.splitlines():
                if raw_line == "diff:":
                    diff_started = True
                    continue
                if not diff_started:
                    continue
                if raw_line.startswith(("---", "+++", "@@")):
                    continue
                if raw_line.startswith("+") or raw_line.startswith("-"):
                    lines.append(raw_line)
                if len(lines) >= 8:
                    break
        if path and not any(line.startswith(("+", "-")) for line in lines):
            lines.append(f"+ Updated `{path}`")
        if content and len(lines) < 8:
            lines.append(f"+ Wrote {len(content.splitlines())} lines")

        if suffix == ".html":
            if "<nav" in content:
                lines.append("+ Added navigation structure")
            if "<h1" in content:
                lines.append("+ Added page headline")
            if "class=\"hero" in content or "class='hero" in content:
                lines.append("+ Added hero section")
            if "styles.css" in content:
                lines.append("+ Connected shared stylesheet")
            link_targets = sorted(set(re.findall(r'href=\"([^\"]+\\.html(?:#[^\"]+)?)\"', content)))
            if link_targets:
                lines.append(f"+ Linked pages: {', '.join(link_targets[:4])}")
        elif suffix == ".css":
            if ":root" in content:
                lines.append("+ Defined design tokens")
            if "@media" in content:
                lines.append("+ Added responsive rules")
            if "background" in content:
                lines.append("+ Added visual styling system")
        elif suffix in {".py", ".js", ".ts"}:
            funcs = re.findall(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)", content, flags=re.MULTILINE)
            if funcs:
                lines.append(f"+ Added functions: {', '.join(funcs[:4])}")

        return lines[:5]

    def _capture_observation(self, run: RunState, task: Task):
        if not self._should_capture_observation(task):
            return
        if "observe_environment" not in self.registry.list_names() and "browser_snapshot" not in self.registry.list_names():
            return

        target_path = "."
        for key in ["path", "cwd", "directory"]:
            value = task.tool_args.get(key)
            if isinstance(value, str) and value.strip():
                target_path = value
                break
        if "path" in task.tool_args and isinstance(task.tool_args["path"], str):
            path_value = Path(task.tool_args["path"])
            if path_value.suffix:
                target_path = str(path_value.parent or Path("."))

        try:
            if task.tool_name in {"open_browser", "browser_open", "browser_click", "browser_type", "browser_wait"} and "browser_snapshot" in self.registry.list_names():
                observation = self.tools.execute("browser_snapshot", {"include_screenshot": True})
            else:
                if "observe_environment" not in self.registry.list_names():
                    return
            observation = self.tools.execute("observe_environment", {"path": target_path, "depth": 2})
            self._event(
                run,
                "observation",
                {
                    "task_id": task.id,
                    "after_tool": task.tool_name,
                    "path": target_path,
                    "snapshot": observation[:2000],
                },
            )
            self.audit.log(
                run.run_id,
                "observation",
                task,
                {"path": target_path, "snapshot_excerpt": observation[:500]},
            )
            self.world_state.record_action(run.goal, run.run_id, "observe_environment", {"path": target_path, "depth": 2}, observation, "completed", {"after_tool": task.tool_name})
            if task.tool_name in {"browser_open", "open_browser", "browser_click", "browser_type", "browser_wait"} and "browser_snapshot" in self.registry.list_names():
                browser_snapshot = self.tools.execute("browser_snapshot", {"include_screenshot": True})
                self.world_state.record_action(run.goal, run.run_id, "browser_snapshot", {"include_screenshot": True}, browser_snapshot, "completed", {"after_tool": task.tool_name})
            self._emit(
                "observation",
                {
                    "run_id": run.run_id,
                    "task_id": task.id,
                    "task_name": task.name,
                    "path": target_path,
                    "snapshot": observation[:1000],
                },
            )
        except Exception:
            return

    def _should_capture_observation(self, task: Task) -> bool:
        if task.tool_name == "observe_environment":
            return False
        if task.tool_name in {"write_file", "create_directory", "install_package", "execute_python"}:
            return True
        if task.tool_name in {"open_browser", "browser_open", "browser_click", "browser_type", "browser_wait"}:
            return True
        if task.tool_name == "run_shell_command":
            command = str(task.tool_args.get("command", "")).lower()
            interesting = ["python", "npm", "pip", "uv", "node", "git", "mkdir", "touch", "start", "serve", "build"]
            return any(token in command for token in interesting)
        return False


class Reflector:
    def __init__(self, ai_model: Any, memory: MemorySystem):
        self.ai = ai_model
        self.memory = memory

    def reflect(self, run: RunState):
        if not AgentConfig.ENABLE_REFLECTION:
            return
        done = [t for t in run.plan.tasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in run.plan.tasks if t.status == TaskStatus.FAILED]

        summary = (
            f"Goal: {run.goal}\n"
            f"Completed: {len(done)}\n"
            f"Failed: {len(failed)}\n"
            f"Tools: {', '.join(sorted({t.tool_name for t in run.plan.tasks}))}"
        )
        self.memory.add_fact(summary, tags=["run_summary"])

        if run.status == RunStatus.COMPLETED:
            skill_name = "workflow_" + re.sub(r"\W+", "_", run.goal.lower())[:40].strip("_")
            self.memory.add_skill(skill_name or "workflow", f"Reusable workflow for goal: {run.goal}")
            self.memory.add_project_memory(
                run.goal,
                {
                    "tasks": [t.name for t in run.plan.tasks],
                    "tools": [t.tool_name for t in run.plan.tasks],
                    "status": run.status.value,
                },
            )


class GoalEvaluator:
    def __init__(self, ai_model: Any):
        self.ai = ai_model

    def evaluate(self, run: RunState) -> Dict[str, Any]:
        completed = [
            {
                "name": t.name,
                "tool": t.tool_name,
                "result": t.result[:500],
            }
            for t in run.plan.tasks
            if t.status == TaskStatus.COMPLETED
        ]
        failed = [
            {
                "name": t.name,
                "tool": t.tool_name,
                "error": t.error,
            }
            for t in run.plan.tasks
            if t.status == TaskStatus.FAILED
        ]
        observations = [
            e.get("payload", {}).get("snapshot", "")
            for e in run.events
            if e.get("type") == "observation"
        ][-2:]

        prompt = f"""
You are evaluating whether an autonomous run actually achieved the goal.
Goal: {run.goal}
Completed task outputs: {json.dumps(completed, ensure_ascii=True)}
Failed tasks: {json.dumps(failed, ensure_ascii=True)}
Latest observations: {json.dumps(observations, ensure_ascii=True)}

Return strict JSON:
{{
  "goal_achieved": true/false,
  "reason": "...",
  "next_steps": ["...", "..."]
}}
Be strict. Finishing the current task list does not automatically mean success.
"""
        try:
            response = self.ai.chat(
                [
                    {"role": "system", "content": "Evaluate goal completion strictly. Return JSON only."},
                    {"role": "user", "content": prompt},
                ]
            )
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                parsed = json.loads(match.group(0))
                steps = parsed.get("next_steps", [])
                if not isinstance(steps, list):
                    steps = []
                return {
                    "goal_achieved": bool(parsed.get("goal_achieved")),
                    "reason": str(parsed.get("reason", "")),
                    "next_steps": [str(step) for step in steps[:4] if str(step).strip()],
                }
        except Exception:
            pass

        return {
            "goal_achieved": not any(t.status == TaskStatus.FAILED for t in run.plan.tasks),
            "reason": "Fallback evaluator used.",
            "next_steps": [],
        }


class GoalProgressEvaluator:
    def __init__(self, ai_model: Any, world_state: WorldStateStore):
        self.ai = ai_model
        self.world_state = world_state

    def evaluate(self, run: RunState) -> Dict[str, Any]:
        completed = [t for t in run.plan.tasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in run.plan.tasks if t.status == TaskStatus.FAILED]
        snapshot = self.world_state.snapshot_text()
        product_rubric = ""
        if self._is_website_goal(run.goal):
            product_rubric = """
Website quality rubric:
- Do not mark success if the output is only placeholder files.
- Look for a shared stylesheet, navigation, clear branding, responsive meta viewport, and cross-page links.
- A landing page should include a hero/value proposition and at least one clear call to action.
- If the site exists but lacks coherence or usability, mark goal_achieved=false and strategy_bad=true.
"""
        prompt = f"""
You are judging goal progress, not just task success.
Goal: {run.goal}
Completed tasks: {json.dumps([t.name for t in completed], ensure_ascii=True)}
Failed tasks: {json.dumps([t.name for t in failed], ensure_ascii=True)}
Recent world state:
{snapshot}
{product_rubric}

Return strict JSON:
{{
  "goal_achieved": true/false,
  "progress_score": 0-100,
  "on_track": true/false,
  "strategy_bad": true/false,
  "reason": "...",
  "blockers": ["..."],
  "next_steps": ["..."]
}}

Be strict. A run can be technically successful yet still on the wrong strategy.
"""
        try:
            response = self.ai.chat(
                [
                    {"role": "system", "content": "Evaluate goal progress strictly. Return JSON only."},
                    {"role": "user", "content": prompt},
                ]
            )
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                parsed = json.loads(match.group(0))
                progress = {
                    "goal": run.goal,
                    "goal_achieved": bool(parsed.get("goal_achieved")),
                    "progress_score": int(parsed.get("progress_score", 0)),
                    "on_track": bool(parsed.get("on_track", True)),
                    "strategy_bad": bool(parsed.get("strategy_bad", False)),
                    "reason": str(parsed.get("reason", "")),
                    "blockers": parsed.get("blockers", []) if isinstance(parsed.get("blockers", []), list) else [],
                    "next_steps": parsed.get("next_steps", []) if isinstance(parsed.get("next_steps", []), list) else [],
                }
                self.world_state.update_goal_progress(run.goal, progress)
                return progress
        except Exception:
            pass

        if self._is_website_goal(run.goal):
            website_eval = self._evaluate_website_quality(run, failed)
            self.world_state.update_goal_progress(run.goal, website_eval)
            return website_eval

        fallback = {
            "goal": run.goal,
            "goal_achieved": not failed,
            "progress_score": 100 if not failed else max(10, 100 - len(failed) * 25),
            "on_track": not failed,
            "strategy_bad": bool(failed),
            "reason": "Fallback goal-progress evaluator used.",
            "blockers": [t.error for t in failed if t.error][:5],
            "next_steps": [],
        }
        self.world_state.update_goal_progress(run.goal, fallback)
        return fallback

    def _is_website_goal(self, goal: str) -> bool:
        lowered = goal.lower()
        return "website" in lowered or "landing page" in lowered or "home page" in lowered

    def _evaluate_website_quality(self, run: RunState, failed: List[Task]) -> Dict[str, Any]:
        written_files = {
            str(task.tool_args.get("path", "")): str(task.tool_args.get("content", ""))
            for task in run.plan.tasks
            if task.status == TaskStatus.COMPLETED
            and task.tool_name == "write_file"
            and isinstance(task.tool_args, dict)
            and task.tool_args.get("path")
        }
        index_html = next((content for path, content in written_files.items() if path.endswith("index.html")), "")
        styles_css = next((content for path, content in written_files.items() if path.endswith("styles.css")), "")
        quality_checks = {
            "shared_stylesheet": bool(styles_css),
            "responsive_meta": "meta name=\"viewport\"" in index_html,
            "navigation": "<nav" in index_html and "about.html" in index_html and "contact.html" in index_html,
            "branding": "<title>" in index_html and ("AI Labs" in index_html or re.search(r"<title>[^<]{3,}</title>", index_html)),
            "hero_section": "<h1>" in index_html and ("button" in index_html or "href=\"contact.html\"" in index_html),
            "multi_page_structure": any(path.endswith("about.html") for path in written_files) and any(path.endswith("contact.html") for path in written_files),
        }
        passed = sum(1 for ok in quality_checks.values() if ok)
        blockers = [name.replace("_", " ") for name, ok in quality_checks.items() if not ok]
        strategy_bad = bool(failed) or passed < 5
        goal_achieved = not failed and passed >= 5
        progress_score = min(100, passed * 16 + (4 if not failed else 0))
        reason = "Website quality rubric passed." if goal_achieved else "Website exists but lacks enough product structure."
        if failed:
            blockers.extend([task.error for task in failed if task.error])
        result = {
            "goal": run.goal,
            "goal_achieved": goal_achieved,
            "progress_score": progress_score,
            "on_track": passed >= 3 and not failed,
            "strategy_bad": strategy_bad,
            "reason": reason,
            "blockers": blockers[:6],
            "next_steps": self._website_next_steps(quality_checks),
        }
        return result

    def _website_next_steps(self, quality_checks: Dict[str, bool]) -> List[str]:
        suggestions = {
            "shared_stylesheet": "Create a shared stylesheet so every page uses the same visual system.",
            "responsive_meta": "Add responsive metadata and mobile-safe layout rules.",
            "navigation": "Add a navigation bar with links between the core site pages.",
            "branding": "Make the title and top-level copy reflect the actual brand and offer.",
            "hero_section": "Add a real hero section with value proposition and a visible call to action.",
            "multi_page_structure": "Add supporting pages so the site has a coherent conversion path.",
        }
        return [suggestions[name] for name, ok in quality_checks.items() if not ok][:4]


class AutonomousAgent:
    def __init__(
        self,
        ai_model: Any,
        tools: Any,
        memory: Optional[MemorySystem] = None,
        confirm_callback: Optional[Callable[[Task], bool]] = None,
        emit_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        self.ai = ai_model
        self.tools = tools
        self.memory = memory or MemorySystem()
        self.emit_callback = emit_callback
        self.world_state = WorldStateStore()

        self.registry = ToolRegistry(tools)
        self.policy = PolicyEngine()
        self.audit = AuditLogger(AgentConfig.AUDIT_SECRET)
        self.safety = SafetyManager(confirm_callback=confirm_callback)
        self.planner = Planner(ai_model, self.memory, self.world_state)
        self.verifier = Verifier(ai_model)
        self.executor = Executor(
            ai_model,
            tools,
            self.registry,
            self.verifier,
            self.memory,
            self.safety,
            self.policy,
            self.audit,
            self.world_state,
            emit_callback=self._emit,
        )
        self.reflector = Reflector(ai_model, self.memory)
        self.goal_evaluator = GoalProgressEvaluator(ai_model, self.world_state)

        self.active_runs: Dict[str, RunState] = {}
        self.completed_runs: Dict[str, RunState] = {}

    def execute_goal(self, goal: str) -> str:
        run = self._new_run(goal)
        self.audit.log(run.run_id, "run_started", payload={"goal": goal})
        self._persist_run(run)

        run = self._execute_existing_run(run)
        return run.summary

    def resume_run(self, run_id: str) -> str:
        run = self._load_run(run_id)
        if not run:
            return f"Run not found: {run_id}"
        if run.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
            return self._summary_text(run)

        self.active_runs[run_id] = run
        run.status = RunStatus.RUNNING
        self.audit.log(run.run_id, "run_resumed", payload={"goal": run.goal})
        self._persist_run(run)

        run = self._execute_existing_run(run)
        return f"[Resumed {run_id}]\n{run.summary}"

    def list_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        rows = self.memory.runs_index[-limit:]
        return list(reversed(rows))

    def get_status(self) -> Dict[str, Any]:
        return {
            "active_plans": len(self.active_runs),
            "completed_plans": len(self.completed_runs),
            "memory_facts": len(self.memory.ltm.get("facts", [])),
            "memory_patterns": len(self.memory.ltm.get("patterns", [])),
            "memory_skills": len(self.memory.ltm.get("skills", [])),
            "failure_log_size": len(self.memory.failure_log),
            "stored_runs": len(self.memory.runs_index),
            "policy": self.policy.get_policy(),
        }

    def reset(self):
        self.active_runs = {}
        self.completed_runs = {}
        self.memory.clear_context()

    def get_policy(self) -> Dict[str, bool]:
        return self.policy.get_policy()

    def set_policy_scope(self, scope: str, enabled: bool) -> str:
        ok, message = self.policy.set_scope(scope, enabled)
        return message if ok else f"Policy update failed: {message}"

    def get_audit_tail(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.audit.tail(limit)

    def _new_run(self, goal: str) -> RunState:
        run_id = hashlib.md5((goal + datetime.now().isoformat()).encode("utf-8")).hexdigest()[:12]
        plan = self.planner.create_plan(goal, self.registry, run_id=run_id, revision=0)
        run = RunState(run_id=run_id, goal=goal, status=RunStatus.RUNNING, plan=plan)
        self.active_runs[run_id] = run
        self.memory.remember_run(run)
        self._emit(
            "plan_created",
            {
                "run_id": run_id,
                "goal": goal,
                "plan": [task.name for task in plan.tasks],
            },
        )
        return run

    def _execute_existing_run(self, run: RunState) -> RunState:
        while True:
            run, failed_task = self.executor.run_plan(run)
            run.updated_at = datetime.now().isoformat()

            if failed_task is None:
                evaluation = self.goal_evaluator.evaluate(run)
                self._emit(
                    "evaluation",
                    {
                        "run_id": run.run_id,
                        "goal_achieved": evaluation.get("goal_achieved", False),
                        "progress_score": evaluation.get("progress_score", 0),
                        "on_track": evaluation.get("on_track", True),
                        "strategy_bad": evaluation.get("strategy_bad", False),
                        "reason": evaluation.get("reason", ""),
                        "next_steps": evaluation.get("next_steps", []),
                        "blockers": evaluation.get("blockers", []),
                    },
                )
                self.audit.log(run.run_id, "evaluation", payload=evaluation)
                if evaluation.get("goal_achieved") and evaluation.get("on_track", True):
                    run.status = RunStatus.COMPLETED
                    run.completed_at = datetime.now().isoformat()
                    self.audit.log(run.run_id, "run_completed", payload={"replans": run.replan_count})
                    break

                if run.replan_count >= AgentConfig.MAX_REPLANS:
                    run.status = RunStatus.FAILED
                    run.completed_at = datetime.now().isoformat()
                    self.audit.log(
                        run.run_id,
                        "run_failed",
                        payload={"reason": evaluation.get("reason", "goal not achieved"), "replans": run.replan_count},
                    )
                    break

                run.replan_count += 1
                pseudo_failed_task = Task(
                    id=f"{run.run_id}_eval_{run.replan_count}",
                    name="Goal evaluation requested more work",
                    description=f"{evaluation.get('reason', '')} | blockers: {', '.join(evaluation.get('blockers', []))}",
                    tool_name="observe_environment" if "observe_environment" in self.registry.list_names() else self.registry.list_names()[0],
                    tool_args={"path": ".", "depth": 2} if "observe_environment" in self.registry.list_names() else {},
                    error=evaluation.get("reason", "goal not achieved"),
                )
                run.plan = self.planner.replan(run, pseudo_failed_task, pseudo_failed_task.error, self.registry)
                self._emit(
                    "replan",
                    {
                        "run_id": run.run_id,
                        "failed_task": pseudo_failed_task.name,
                        "error": pseudo_failed_task.error,
                        "plan": [task.name for task in run.plan.tasks],
                    },
                )
                self._persist_run(run)
                continue

            if run.replan_count >= AgentConfig.MAX_REPLANS:
                failed_task.status = TaskStatus.SKIPPED
                if any(task.status == TaskStatus.PENDING for task in run.plan.tasks):
                    self._persist_run(run)
                    continue
                run.status = RunStatus.FAILED
                run.completed_at = datetime.now().isoformat()
                self.audit.log(
                    run.run_id,
                    "run_failed",
                    payload={"task_id": failed_task.id, "error": failed_task.error, "replans": run.replan_count},
                )
                break

            run.replan_count += 1
            failed_task.status = TaskStatus.SKIPPED
            self.memory.add_context(
                {
                    "type": "replan",
                    "run_id": run.run_id,
                    "failed_task": failed_task.name,
                    "error": failed_task.error,
                    "replan_count": run.replan_count,
                }
            )
            self.audit.log(
                run.run_id,
                "run_replan",
                failed_task,
                {"error": failed_task.error, "replan_count": run.replan_count},
            )
            revised_plan = self.planner.replan(run, failed_task, failed_task.error, self.registry)
            preserved = [task for task in run.plan.tasks if task.status in {TaskStatus.COMPLETED, TaskStatus.SKIPPED}]
            replanned = revised_plan.tasks
            for task in replanned:
                task.dependencies = [dep for dep in task.dependencies if dep not in {failed_task.id}]
            run.plan = Plan(
                id=revised_plan.id,
                goal=run.goal,
                tasks=preserved + replanned,
                revision=revised_plan.revision,
                created_at=revised_plan.created_at,
            )
            self._emit(
                "replan",
                {
                    "run_id": run.run_id,
                    "failed_task": failed_task.name,
                    "error": failed_task.error,
                    "plan": [task.name for task in run.plan.tasks],
                },
            )
            self._persist_run(run)

        self.reflector.reflect(run)
        run.summary = self._summary_text(run)
        self._finish_run(run)
        return run

    def _persist_run(self, run: RunState):
        payload = self._serialize_run(run)
        path = AgentConfig.RUNS_DIR / f"{run.run_id}.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except PermissionError:
            _rebase_agent_storage(Path.cwd() / ".ai_assistant_agent")
            AgentConfig.DATA_DIR.mkdir(parents=True, exist_ok=True)
            AgentConfig.RUNS_DIR.mkdir(parents=True, exist_ok=True)
            path = AgentConfig.RUNS_DIR / f"{run.run_id}.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.memory.update_run_index(run)

    def _load_run(self, run_id: str) -> Optional[RunState]:
        path = AgentConfig.RUNS_DIR / f"{run_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return self._deserialize_run(data)
        except Exception:
            return None

    def _finish_run(self, run: RunState):
        run.updated_at = datetime.now().isoformat()
        self._persist_run(run)
        self.active_runs.pop(run.run_id, None)
        self.completed_runs[run.run_id] = run

    def _summary_text(self, run: RunState) -> str:
        done = [t for t in run.plan.tasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in run.plan.tasks if t.status == TaskStatus.FAILED]
        skipped = [t for t in run.plan.tasks if t.status == TaskStatus.SKIPPED]
        lines = [
            f"Run ID: {run.run_id}",
            f"Goal: {run.goal}",
            f"Status: {run.status.value}",
            f"Plan Revision: {run.plan.revision}",
            f"Tasks Completed: {len(done)}",
            f"Tasks Failed: {len(failed)}",
            f"Tasks Skipped: {len(skipped)}",
        ]
        if failed:
            lines.append("Failures:")
            for t in failed[:5]:
                lines.append(f"  - {t.name}: {t.error}")
        return "\n".join(lines)

    def _serialize_run(self, run: RunState) -> Dict[str, Any]:
        return {
            "run_id": run.run_id,
            "goal": run.goal,
            "status": run.status.value,
            "plan": {
                "id": run.plan.id,
                "goal": run.plan.goal,
                "revision": run.plan.revision,
                "created_at": run.plan.created_at,
                "tasks": [self._serialize_task(t) for t in run.plan.tasks],
            },
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "completed_at": run.completed_at,
            "summary": run.summary,
            "events": run.events[-500:],
            "replan_count": run.replan_count,
        }

    def _deserialize_run(self, data: Dict[str, Any]) -> RunState:
        plan_data = data["plan"]
        tasks = [self._deserialize_task(t) for t in plan_data.get("tasks", [])]
        plan = Plan(
            id=plan_data["id"],
            goal=plan_data["goal"],
            tasks=tasks,
            revision=plan_data.get("revision", 0),
            created_at=plan_data.get("created_at", datetime.now().isoformat()),
        )
        return RunState(
            run_id=data["run_id"],
            goal=data["goal"],
            status=RunStatus(data.get("status", "paused")),
            plan=plan,
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at", ""),
            summary=data.get("summary", ""),
            events=data.get("events", []),
            replan_count=data.get("replan_count", 0),
        )

    def _serialize_task(self, task: Task) -> Dict[str, Any]:
        out = asdict(task)
        out["status"] = task.status.value
        return out

    def _deserialize_task(self, data: Dict[str, Any]) -> Task:
        data = dict(data)
        data["status"] = TaskStatus(data.get("status", "pending"))
        return Task(**data)

    def _emit(self, event_type: str, payload: Dict[str, Any]):
        if self.emit_callback:
            self.emit_callback(event_type, payload)


class AutonomousToolsWrapper:
    def __init__(self, tools_class: Any, data_store: Any = None, ai_model: Any = None):
        self.tools_class = tools_class
        self.data_store = data_store
        self.ai_model = ai_model

    def get_definitions(self) -> List[Dict[str, Any]]:
        if hasattr(self.tools_class, "get_agent_definitions"):
            return self.tools_class.get_agent_definitions()
        return self.tools_class.get_definitions()

    def execute(self, tool_name: str, args: Dict[str, Any]) -> str:
        if tool_name in {"browser_open", "open_browser"}:
            try:
                from tools.browser import navigate

                return navigate(args.get("url", ""))
            except Exception as exc:
                return f"Error executing {tool_name}: {exc}"
        return self.tools_class.execute_tracked(tool_name, args, self.data_store, self.ai_model)
