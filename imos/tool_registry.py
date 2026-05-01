"""
IMOS Tool Registry — auto-discovers skills from the skills/ folder,
builds TOOL_DEFINITIONS for the LLM API, and routes tool calls to handlers.
Every tool result is logged to AuditLogger.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Skill loader
# ---------------------------------------------------------------------------

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(f"imos_skill_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _load_skill(directory: Path) -> Optional[Dict[str, Any]]:
    handler_py = directory / "handler.py"
    skill_md = directory / "SKILL.md"
    if not handler_py.exists():
        return None
    description = ""
    if skill_md.exists():
        description = skill_md.read_text(encoding="utf-8").strip().splitlines()[0].lstrip("# ").strip()
    description = description or directory.name
    try:
        mod = _load_module(directory.name, handler_py)
    except Exception as exc:
        print(f"[IMOS] Warning: could not load skill {directory.name}: {exc}")
        return None
    schema = getattr(mod, "TOOL_SCHEMA", {"type": "object", "properties": {}})
    handler = getattr(mod, "run", None)
    if handler is None:
        return None
    return {
        "name": directory.name,
        "description": description,
        "input_schema": schema,
        "handler": handler,
    }


def discover_skills(root: Path = SKILLS_ROOT) -> List[Dict[str, Any]]:
    """Scan skills/ folder and return list of skill dicts."""
    skills: List[Dict[str, Any]] = []
    if not root.exists():
        return skills
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        skill = _load_skill(directory)
        if skill:
            skills.append(skill)
    return skills


# ---------------------------------------------------------------------------
# Registry class
# ---------------------------------------------------------------------------

class IMOSToolRegistry:
    """
    Holds all tool definitions and routes calls to the correct handler.
    """

    def __init__(self, audit_logger=None):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._audit = audit_logger
        self._refresh()

    def _refresh(self):
        """Re-scan skills folder and rebuild registry."""
        self._tools.clear()
        for skill in discover_skills():
            self._tools[skill["name"]] = skill

    def tool_definitions(self) -> List[Dict[str, Any]]:
        """Return list of tool defs in Anthropic/OpenAI format."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["input_schema"],
            }
            for t in self._tools.values()
        ]

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def call(
        self,
        name: str,
        inputs: Dict[str, Any],
        *,
        workspace: str = "",
        session_id: str = "",
        model_config: Optional[Dict[str, Any]] = None,
        shell_runner=None,
        process_manager=None,
        memory_store=None,
    ) -> Any:
        """Execute a tool by name and return its result."""
        tool = self._tools.get(name)
        if tool is None:
            result = {"ok": False, "error": f"Unknown tool: {name}"}
        else:
            try:
                result = tool["handler"](
                    inputs,
                    workspace=workspace,
                    session_id=session_id,
                    model_config=model_config or {},
                    shell_runner=shell_runner,
                    process_manager=process_manager,
                    memory_store=memory_store,
                )
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}

        # Verify result
        try:
            result = verify_tool_result(name, inputs, result)
        except RuntimeError as exc:
            result = {"ok": False, "error": str(exc), "verification_failed": True}

        # Audit log
        if self._audit is not None:
            preview = (result if isinstance(result, str) else json.dumps(result, ensure_ascii=False))[:800]
            self._audit.append(
                "tool_result",
                name,
                {"session_id": session_id, "input": inputs, "result_preview": preview},
            )
        return result

    def list_names(self) -> List[str]:
        return list(self._tools.keys())


# ---------------------------------------------------------------------------
# Verification layer (Step 8)
# ---------------------------------------------------------------------------

def verify_tool_result(tool_name: str, inputs: Dict[str, Any], result: Any) -> Any:
    """
    After every tool execution, verify the result is real.
    Raises RuntimeError if verification fails.
    """
    verifications: Dict[str, Callable[[], bool]] = {
        "write_file": lambda: (
            isinstance(result, dict)
            and bool(result.get("path"))
            and os.path.exists(result["path"])
            and os.path.getsize(result["path"]) > 0
        ),
        "bash": lambda: (
            isinstance(result, dict)
            and result.get("returncode") is not None
        ),
        "clean_pc": lambda: (
            isinstance(result, dict)
            and isinstance(result.get("freed_mb"), (int, float))
        ),
        "weather": lambda: (
            isinstance(result, dict)
            and "temp_c" in result
        ),
        "news": lambda: (
            isinstance(result, dict)
            and isinstance(result.get("articles"), list)
        ),
        "get_weather": lambda: (
            isinstance(result, dict)
            and "temp_c" in result
        ),
        "get_news": lambda: (
            isinstance(result, dict)
            and isinstance(result.get("articles"), list)
        ),
        "wikipedia_search": lambda: (
            isinstance(result, dict)
            and bool(result.get("summary"))
        ),
        "get_joke": lambda: (
            isinstance(result, dict)
            and bool(result.get("joke"))
        ),
        "get_world_health": lambda: (
            isinstance(result, dict)
            and result.get("ok") is not False
        ),
        "shell_run": lambda: (
            isinstance(result, dict)
            and result.get("returncode") is not None
        ),
    }
    check = verifications.get(tool_name)
    if check is not None:
        try:
            passed = check()
        except Exception:
            passed = False
        if not passed:
            raise RuntimeError(
                f"Tool '{tool_name}' returned unverified result: "
                + (json.dumps(result, ensure_ascii=False)[:300] if not isinstance(result, str) else result[:300])
            )
    return result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_registry: Optional[IMOSToolRegistry] = None


def get_registry(audit_logger=None) -> IMOSToolRegistry:
    global _registry
    if _registry is None:
        _registry = IMOSToolRegistry(audit_logger=audit_logger)
    return _registry
