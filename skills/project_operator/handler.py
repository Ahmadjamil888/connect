from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from tools.agent_bridges import chat_with_configured_model
from tools.ide_automation import choose_best_build_target

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["orchestrate", "continue", "status"]},
        "prompt": {"type": "string"},
        "project_name": {"type": "string"},
        "preferred_target": {"type": "string"},
        "deploy_target": {"type": "string"},
        "db_type": {"type": "string"},
        "private_repo": {"type": "boolean"},
    },
    "required": ["action"],
}


def _state_path(workspace: str) -> Path:
    root = Path(workspace) / ".connectai"
    root.mkdir(parents=True, exist_ok=True)
    return root / "project_operator_session.json"


def _load_state(workspace: str) -> dict[str, Any]:
    path = _state_path(workspace)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"history": []}


def _save_state(workspace: str, state: dict[str, Any]) -> dict[str, Any]:
    path = _state_path(workspace)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return cleaned or "imos-project"


def _guess_project_name(prompt: str) -> str:
    banned = {"and", "with", "for", "to", "a", "an", "the", "it", "deployed", "deploy", "website", "app", "project"}
    patterns = [
        r"(?:called|named)\s+([a-zA-Z0-9._-]+)",
        r"(?:for|build)\s+([a-zA-Z0-9._-]+)\s+(?:website|app|project)",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            candidate = _slugify(match.group(1))
            if candidate not in banned:
                return candidate
    lowered = prompt.lower()
    if "ecommerce" in lowered or "e-commerce" in lowered or "e commerce" in lowered:
        return "ecommerce-store"
    if "website" in lowered:
        return "website-project"
    if "dashboard" in lowered:
        return "dashboard-project"
    return _slugify(" ".join(prompt.split()[:4]))


def _looks_like_web_project(prompt: str) -> bool:
    lowered = prompt.lower()
    markers = [
        "website",
        "web app",
        "webapp",
        "landing page",
        "ecommerce",
        "e-commerce",
        "shop",
        "storefront",
        "next.js",
        "react",
        "frontend",
        "full stack",
        "fullstack",
        "saas",
    ]
    return any(marker in lowered for marker in markers)


def _wants_deploy(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(marker in lowered for marker in ["deploy", "deployed", "ship it", "go live", "production"])


def _infer_db_type(prompt: str) -> str:
    lowered = prompt.lower()
    if "mongodb" in lowered:
        return "mongodb"
    if "mysql" in lowered:
        return "mysql"
    if "postgres" in lowered or "postgresql" in lowered:
        return "postgres"
    if "sqlite" in lowered:
        return "sqlite"
    if _looks_like_web_project(prompt):
        return "postgres" if os.getenv("DATABASE_URL", "").strip() else "sqlite"
    return "none"


def _infer_deploy_target(prompt: str, requested: str = "") -> str:
    explicit = (requested or "").strip().lower()
    if explicit in {"vercel", "netlify", "github_only", "none"}:
        return explicit
    lowered = prompt.lower()
    if "netlify" in lowered:
        return "netlify"
    if "vercel" in lowered:
        return "vercel"
    if not _wants_deploy(prompt):
        return "none"
    if os.getenv("VERCEL_TOKEN", "").strip():
        return "vercel"
    if os.getenv("NETLIFY_TOKEN", "").strip():
        return "netlify"
    return "github_only" if os.getenv("GITHUB_TOKEN", "").strip() else "none"


def _generate_build_brief(
    prompt: str,
    *,
    project_name: str,
    deploy_target: str,
    db_type: str,
    target: str,
    state: dict[str, Any],
) -> str:
    history = state.get("history", [])[-6:]
    history_text = "\n".join(f"- {item.get('prompt', '')}" for item in history if item.get("prompt"))
    rewrite_prompt = (
        "Rewrite the user's request into a single precise implementation brief for an autonomous coding agent.\n"
        "The result must be execution-oriented and must preserve continuity with prior work.\n"
        "Use these exact sections: Objective, Scope, Deliverables, Stack, Data, Integrations, Verification, GitHub, Deployment, Continuity.\n"
        "Be explicit about what files, flows, runtime verification, and deployment steps must exist.\n"
        "Do not use markdown code fences.\n\n"
        f"Target agent or IDE: {target}\n"
        f"Project name: {project_name}\n"
        f"Preferred deploy target: {deploy_target}\n"
        f"Preferred database: {db_type}\n"
        f"Recent session context:\n{history_text or '- none'}\n\n"
        f"User request:\n{prompt}"
    )
    result = chat_with_configured_model(rewrite_prompt)
    if result.get("success") and str(result.get("reply", "")).strip():
        return str(result["reply"]).strip()
    return "\n".join(
        [
            f"Objective: Build the requested project as {project_name} and keep execution state reusable across follow-up turns.",
            f"Scope: {prompt.strip()}",
            "Deliverables: Produce a working codebase, verify the main runtime locally when possible, and leave the project in a shippable state.",
            "Stack: Choose a stack appropriate to the request; for websites prefer production-ready modern web tooling.",
            f"Data: Use {db_type} when persistence is needed and wire environment-based configuration cleanly.",
            "Integrations: Use configured providers and tokens when available instead of placeholders.",
            "Verification: Do not stop at planning. Create files, verify project artifacts, and verify deploy/build outcomes when requested.",
            "GitHub: If a configured GitHub token is available, initialize a repository, commit, and push the result.",
            f"Deployment: If deployment is requested, target {deploy_target}.",
            "Continuity: Preserve context so future prompts continue from this implementation instead of restarting from scratch.",
        ]
    )


def _project_markers(project_root: Path) -> dict[str, Any]:
    markers = {
        "package_json": (project_root / "package.json").exists(),
        "requirements_txt": (project_root / "requirements.txt").exists(),
        "pyproject_toml": (project_root / "pyproject.toml").exists(),
        "dockerfile": (project_root / "Dockerfile").exists(),
        "terraform": (project_root / "main.tf").exists() or (project_root / "terraform").exists(),
        "next_app": (project_root / "app" / "page.tsx").exists() or (project_root / "src" / "app" / "page.tsx").exists(),
        "vite": (project_root / "vite.config.ts").exists() or (project_root / "vite.config.js").exists(),
        "git": (project_root / ".git").exists(),
    }
    markers["has_artifacts"] = any(value for key, value in markers.items() if key != "git")
    return markers


def _run_skill(skills: dict[str, Any], name: str, inputs: dict[str, Any], workspace: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    skill = skills.get(name)
    if skill is None:
        return {"ok": False, "error": f"Required skill not available: {name}"}
    try:
        return skill.handler(
            inputs,
            workspace=workspace,
            memory_store=kwargs.get("memory_store"),
            session_id=kwargs.get("session_id"),
            model_config=kwargs.get("model_config"),
            shell_runner=kwargs.get("shell_runner"),
            process_manager=kwargs.get("process_manager"),
            audit_logger=kwargs.get("audit_logger"),
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _save_session_state(workspace: str, state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    state.update(payload)
    history = list(state.get("history", []))
    entry = {
        "prompt": payload.get("last_prompt", ""),
        "target": payload.get("target", state.get("target", "")),
        "project_name": payload.get("project_name", state.get("project_name", "")),
        "project_root": payload.get("project_root", state.get("project_root", "")),
        "deploy_target": payload.get("deploy_target", state.get("deploy_target", "")),
        "db_type": payload.get("db_type", state.get("db_type", "")),
    }
    if entry["prompt"]:
        history.append(entry)
    state["history"] = history[-24:]
    return _save_state(workspace, state)


def _maybe_push_and_deploy(
    *,
    workspace: str,
    project_name: str,
    project_root: str,
    prompt: str,
    deploy_target: str,
    current_result: dict[str, Any],
    skills: dict[str, Any],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    result = dict(current_result)
    wants_repo = _wants_deploy(prompt) or "github" in prompt.lower() or "repo" in prompt.lower()
    if wants_repo and project_root and not result.get("github_url") and os.getenv("GITHUB_TOKEN", "").strip():
        github_result = _run_skill(
            skills,
            "github_push",
            {
                "action": "init_and_push",
                "repo_dir": project_root,
                "repo_name": project_name,
                "description": prompt.strip(),
                "private": bool(result.get("private_repo", False)),
                "commit_message": f"Initial IMOS build for {project_name}",
                "branch": "main",
            },
            workspace,
            kwargs,
        )
        if github_result.get("ok"):
            result["github"] = github_result
            result["github_url"] = github_result.get("html_url", "")
        else:
            result["github_error"] = github_result.get("error", "")

    if _looks_like_web_project(prompt) and _wants_deploy(prompt) and deploy_target in {"vercel", "netlify"} and project_root and not result.get("deploy_url"):
        skill_name = "deploy_vercel" if deploy_target == "vercel" else "deploy_netlify"
        deploy_input = {
            "action": "deploy",
            "project_dir": project_root,
            "project_name": project_name,
            "site_name": project_name,
        }
        deploy_result = _run_skill(skills, skill_name, deploy_input, workspace, kwargs)
        result["deploy"] = deploy_result
        if deploy_result.get("ok"):
            result["deploy_url"] = deploy_result.get("url", "")
        else:
            result["deploy_error"] = deploy_result.get("error", "") or deploy_result.get("output", "")
    return result


def run(inputs, *, workspace: str, **kwargs):
    from connectai.skills import SkillRegistry

    action = str(inputs.get("action", "orchestrate")).strip().lower()
    state = _load_state(workspace)
    if action == "status":
        return {"ok": True, "state": state}

    registry = SkillRegistry(Path(workspace), bundled_root=Path.cwd() / "skills")
    loaded_skills = {item.name: item for item in registry.load_all()}

    if action == "continue":
        followup = str(inputs.get("prompt", "")).strip()
        if not state.get("project_name"):
            return {"ok": False, "error": "No active build session."}
        target = str(state.get("target", "")).strip().lower() or choose_best_build_target()
        context_prompt = "\n".join(
            [
                f"Continue the existing project {state.get('project_name', '')}.",
                f"Project root: {state.get('project_root', '')}",
                f"Previous execution brief:\n{state.get('generated_prompt', '')}",
                f"New request:\n{followup or 'Continue from the current verified state and finish remaining work.'}",
                "Do not restart from scratch. Reuse the existing files and continue the same implementation thread.",
            ]
        )
        if target == "browser":
            result = _run_skill(
                loaded_skills,
                "vibe_coder",
                {"action": "continue", "prompt": context_prompt},
                workspace,
                kwargs,
            )
        else:
            result = _run_skill(
                loaded_skills,
                "ide_orchestrator",
                {"action": "continue", "target": target, "prompt": context_prompt, "wait_for_response": True},
                workspace,
                kwargs,
            )
        markers = _project_markers(Path(state.get("project_root", ""))) if state.get("project_root") else {}
        combined = {
            "ok": bool(result.get("ok")),
            "target": target,
            "project_name": state.get("project_name", ""),
            "project_root": state.get("project_root", ""),
            "generated_prompt": state.get("generated_prompt", ""),
            "markers": markers,
            "continue_result": result,
            "deploy_target": state.get("deploy_target", "none"),
            "db_type": state.get("db_type", "none"),
            "last_prompt": followup,
        }
        combined = _maybe_push_and_deploy(
            workspace=workspace,
            project_name=combined["project_name"],
            project_root=combined["project_root"],
            prompt=followup or state.get("original_prompt", ""),
            deploy_target=combined["deploy_target"],
            current_result=combined,
            skills=loaded_skills,
            kwargs=kwargs,
        )
        _save_session_state(workspace, state, combined)
        return combined

    prompt = str(inputs.get("prompt", "")).strip()
    if not prompt:
        return {"ok": False, "error": "Prompt is required."}

    project_name = str(inputs.get("project_name", "")).strip() or _guess_project_name(prompt)
    preferred_target = str(inputs.get("preferred_target", "")).strip().lower()
    deploy_target = _infer_deploy_target(prompt, str(inputs.get("deploy_target", "")).strip())
    db_type = str(inputs.get("db_type", "")).strip().lower() or _infer_db_type(prompt)
    target = choose_best_build_target(preferred_target)
    generated_prompt = _generate_build_brief(
        prompt,
        project_name=project_name,
        deploy_target=deploy_target,
        db_type=db_type,
        target=target,
        state=state,
    )
    project_root = str((Path(workspace) / project_name).resolve())

    if target == "browser":
        build_result = _run_skill(
            loaded_skills,
            "vibe_coder",
            {"action": "orchestrate", "prompt": generated_prompt, "project_name": project_name},
            workspace,
            kwargs,
        )
        if build_result.get("path"):
            project_root = str(Path(build_result["path"]).resolve())
    else:
        build_result = _run_skill(
            loaded_skills,
            "ide_orchestrator",
            {
                "action": "start",
                "target": target,
                "prompt": generated_prompt,
                "project_name": project_name,
                "project_path": project_name,
                "wait_for_response": True,
            },
            workspace,
            kwargs,
        )

    markers = _project_markers(Path(project_root))
    if not markers.get("has_artifacts") and _looks_like_web_project(prompt) and loaded_skills.get("scaffold_nextjs") is not None:
        scaffold_result = _run_skill(
            loaded_skills,
            "scaffold_nextjs",
            {
                "description": prompt,
                "project_name": project_name,
                "db_type": db_type,
                "deploy_target": deploy_target if deploy_target in {"vercel", "netlify", "github_only"} else "none",
                "private_repo": bool(inputs.get("private_repo", False)),
                "include_auth": "auth" in prompt.lower() or "login" in prompt.lower(),
                "include_payments": any(term in prompt.lower() for term in ["payment", "checkout", "stripe", "ecommerce", "e-commerce"]),
            },
            workspace,
            kwargs,
        )
        if scaffold_result.get("ok"):
            project_root = str(Path(scaffold_result.get("project_dir", project_root)).resolve())
            markers = _project_markers(Path(project_root))
            build_result = {
                "ok": True,
                "mode": "scaffold_fallback",
                "response": scaffold_result.get("summary", ""),
                "details": scaffold_result,
                "github_url": scaffold_result.get("github_url", ""),
                "deploy_url": scaffold_result.get("deploy_url", ""),
            }

    result = {
        "ok": bool(build_result.get("ok")),
        "project_name": project_name,
        "project_root": project_root,
        "target": target,
        "generated_prompt": generated_prompt,
        "original_prompt": prompt,
        "deploy_target": deploy_target,
        "db_type": db_type,
        "markers": markers,
        "build_result": build_result,
        "github_url": build_result.get("github_url", ""),
        "deploy_url": build_result.get("deploy_url", ""),
        "last_prompt": prompt,
        "private_repo": bool(inputs.get("private_repo", False)),
    }
    result = _maybe_push_and_deploy(
        workspace=workspace,
        project_name=project_name,
        project_root=project_root,
        prompt=prompt,
        deploy_target=deploy_target,
        current_result=result,
        skills=loaded_skills,
        kwargs=kwargs,
    )
    _save_session_state(workspace, state, result)
    return result
