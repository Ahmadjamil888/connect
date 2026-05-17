from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools import browser_tools, terminal_tools


def lovable_build_project(prompt: str) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    try:
        steps.append(browser_tools.navigate("https://lovable.dev"))
        selectors = ["textarea", "[placeholder*='idea']", "[data-testid='prompt-input']"]
        typed = None
        for selector in selectors:
            attempt = browser_tools.type(selector, prompt)
            steps.append(attempt)
            if attempt.get("status") == "success":
                typed = selector
                break
        if typed is None:
            return {"status": "error", "error": "Could not find a Lovable prompt input", "steps": steps}

        submit_attempts = [
            browser_tools.click("button[type='submit']"),
            browser_tools.click("[data-testid='submit-button']"),
            browser_tools.click(by_text="Submit"),
        ]
        steps.extend(submit_attempts)
        if not any(step.get("status") == "success" for step in submit_attempts):
            return {"status": "error", "error": "Could not submit Lovable prompt", "steps": steps}

        wait_deploy = browser_tools.wait_for_text("Deploy", timeout_ms=120000)
        steps.append(wait_deploy)
        if wait_deploy.get("status") != "success":
            wait_open = browser_tools.wait_for_text("Open project", timeout_ms=120000)
            steps.append(wait_open)
            if wait_open.get("status") != "success":
                return {"status": "error", "error": "Lovable did not show Deploy or Open project in time", "steps": steps}

        screenshot_path = str((Path.cwd() / "screenshots" / "lovable-result.png").resolve())
        shot = browser_tools.screenshot(screenshot_path)
        steps.append(shot)
        page = browser_tools.get_text("body")
        steps.append(page)
        if page.get("status") != "success":
            return {"status": "error", "error": page.get("error", "Could not read Lovable page"), "steps": steps}

        urls = sorted(set(re.findall(r"https://[a-zA-Z0-9.-]+\.lovable\.app[^\s\"'<>)]*", page.get("content", ""))))
        return {
            "status": "success",
            "prompt_selector": typed,
            "urls": urls,
            "page_content": page.get("content", ""),
            "screenshot_path": shot.get("path"),
            "current_url": steps[-1].get("current_url") if isinstance(steps[-1], dict) else None,
            "steps": steps,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "steps": steps}


def vercel_deploy(project_path: str, prod: bool = True) -> dict[str, Any]:
    command = "vercel --yes"
    if prod:
        command += " --prod"
    result = terminal_tools.run_command(command, cwd=project_path, timeout=900)
    if result.get("status") != "success":
        return result
    urls = re.findall(r"https://[a-zA-Z0-9.-]+\.vercel\.app", result.get("stdout", ""))
    if not urls:
        return {"status": "error", "error": "Could not parse Vercel URL from CLI output", "stdout": result.get("stdout", ""), "stderr": result.get("stderr", "")}
    return {
        "status": "success",
        "project_path": str(Path(project_path).expanduser().resolve()),
        "deploy_url": urls[-1],
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "exit_code": result.get("exit_code"),
    }


def netlify_deploy(project_path: str, prod: bool = True) -> dict[str, Any]:
    command = "netlify deploy --json"
    if prod:
        command += " --prod"
    result = terminal_tools.run_command(command, cwd=project_path, timeout=900)
    if result.get("status") != "success":
        return result
    try:
        payload = json.loads(result.get("stdout", ""))
    except Exception as exc:
        return {"status": "error", "error": f"Could not parse Netlify JSON output: {exc}", "stdout": result.get("stdout", "")}
    deploy_url = payload.get("deploy_url") or payload.get("url")
    if not deploy_url:
        return {"status": "error", "error": "Netlify CLI output did not include deploy_url", "payload": payload}
    return {
        "status": "success",
        "project_path": str(Path(project_path).expanduser().resolve()),
        "deploy_url": deploy_url,
        "site_id": payload.get("site_id"),
        "raw_json": payload,
    }
