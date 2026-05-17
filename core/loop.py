import json
import os
from typing import Any, Dict

from core.brain import think
from core.vision import get_screen_b64
from tools.registry import ToolRegistry


def _message_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
            elif isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
        return "\n".join(parts)
    return str(content or "")


def _safe_preview(value: Any, limit: int = 400) -> str:
    text = str(value)
    text = text.encode("ascii", "replace").decode("ascii")
    return text[:limit]


def _result_failed(result: Any) -> bool:
    if isinstance(result, dict):
        status = str(result.get("status", "")).lower()
        if status == "error":
            return True
        if "returncode" in result and int(result.get("returncode", 0) or 0) != 0:
            return True
        return False
    lowered = str(result).lower()
    error_markers = [
        "tool error",
        "error:",
        "'error':",
        '"error":',
        "path not found",
        "blocked:",
        "invalid url",
        "could not fetch",
        "unavailable",
        "failed",
    ]
    return any(marker in lowered for marker in error_markers)


def run(goal: str, registry: ToolRegistry, max_steps: int = 50) -> Dict[str, Any]:
    """
    Free-form autonomous execution loop.
    No predefined plan. No task graph. Just observe-think-act-verify.
    """
    history = []
    step = 0
    failed_tools: Dict[str, int] = {}

    print(f"\n[CONNECT] Starting: {goal}\n")

    while step < max_steps:
        step += 1
        screen_b64 = get_screen_b64()
        try:
            response = think(
                goal=goal,
                screen_b64=screen_b64,
                history=history,
                tools=registry.get_tool_definitions(),
            )
        except Exception as exc:
            history.append({"step": step, "type": "error", "content": str(exc)})
            return {"status": "error", "steps": step, "history": history, "error": str(exc)}

        message = response.choices[0].message
        text = _message_text(message)
        if "GOAL_COMPLETE" in text:
            print(f"\n[CONNECT] Goal completed in {step} steps.")
            return {"status": "completed", "steps": step, "history": history}

        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            history.append({"step": step, "type": "thought", "content": text})
            continue

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except Exception:
                tool_args = {}

            if failed_tools.get(tool_name, 0) >= 2:
                history.append(
                    {
                        "step": step,
                        "type": "skip",
                        "tool": tool_name,
                        "result": f"Skipped - {tool_name} failed too many times, try different approach",
                        "success": False,
                    }
                )
                continue

            print(f"\n[CONNECT Step {step}] {tool_name}")
            print(f"  Args: {json.dumps(tool_args, indent=2)[:300]}")

            result = registry.execute(tool_name, tool_args)
            success = not _result_failed(result)
            verification = None
            if tool_name in {"run_shell", "run_command"} and isinstance(result, dict) and success:
                candidate_paths = result.get("candidate_paths") or []
                if candidate_paths:
                    verification = registry.execute("verify_path_exists", {"path": candidate_paths[0]})
                    success = success and bool(isinstance(verification, dict) and verification.get("exists"))
            elif tool_name in {"write_file"} and isinstance(tool_args, dict) and tool_args.get("path"):
                verification = registry.execute("verify_path_exists", {"path": tool_args["path"]})
                success = success and bool(isinstance(verification, dict) and verification.get("exists"))
            if success:
                failed_tools[tool_name] = 0
                print(f"  Result: {_safe_preview(result)}")
            else:
                failed_tools[tool_name] = failed_tools.get(tool_name, 0) + 1
                print(f"  [ERROR] {_safe_preview(result)}")
            if verification is not None:
                print(f"  Verify: {_safe_preview(verification)}")

            history.append(
                {
                    "step": step,
                    "type": "action",
                    "tool": tool_name,
                    "args": tool_args,
                    "result": _safe_preview(result, 500),
                    "verification": _safe_preview(verification, 300) if verification is not None else "",
                    "success": success,
                }
            )

    return {"status": "max_steps_reached", "steps": step, "history": history}
