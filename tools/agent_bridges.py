from __future__ import annotations

import os
import shutil
import smtplib
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

from config.config import get_client, get_model_config, get_provider_defaults


def chat_with_claude_code(prompt: str, project_path: str = ".") -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            cwd=project_path,
            timeout=120,
            check=False,
        )
        return {
            "success": result.returncode == 0,
            "output": (result.stdout or "").strip(),
            "error": (result.stderr or "").strip(),
            "returncode": result.returncode,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "Claude Code not installed. Run: npm install -g @anthropic-ai/claude-code",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Claude Code timed out"}


def open_claude_code_interactive(project_path: str = ".") -> dict[str, Any]:
    try:
        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        process = subprocess.Popen(
            ["claude"],
            cwd=project_path,
            creationflags=creationflags,
        )
        return {"success": True, "mode": "interactive", "path": project_path, "pid": process.pid}
    except FileNotFoundError:
        return {
            "success": False,
            "error": "Claude Code not installed. Run: npm install -g @anthropic-ai/claude-code",
        }


def chat_with_openai(prompt: str, history: list[dict[str, str]] | None = None, model: str | None = None) -> dict[str, Any]:
    try:
        import openai
    except Exception as exc:
        return {"success": False, "error": f"OpenAI SDK unavailable: {exc}"}

    current = get_model_config()
    chosen_model = model or "gpt-4o"
    api_key = ""
    if str(current.get("provider", "")).strip().lower() == "openai":
        api_key = str(current.get("api_key", "")).strip()
        chosen_model = model or str(current.get("model", chosen_model)).strip() or chosen_model
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        defaults = get_provider_defaults("openai")
        api_key = str(defaults.get("api_key", "")).strip()
    if not api_key:
        return {"success": False, "error": "OpenAI API key is empty. Run /setkey openai <key> or export OPENAI_API_KEY."}

    try:
        client = openai.OpenAI(api_key=api_key)
        messages = list(history or [])
        custom_system_prompt = str(current.get("custom_system_prompt", "")).strip()
        if custom_system_prompt and not any(msg.get("role") == "system" for msg in messages):
            messages.insert(0, {"role": "system", "content": custom_system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=chosen_model,
            messages=messages,
        )
        reply = response.choices[0].message.content if response.choices else ""
        return {"success": True, "reply": reply or "", "model": chosen_model}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def chat_with_gemini(prompt: str, history: list[dict[str, str]] | None = None, model: str | None = None) -> dict[str, Any]:
    try:
        import openai
    except Exception as exc:
        return {"success": False, "error": f"OpenAI SDK unavailable: {exc}"}

    api_key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_AI_API_KEY", "").strip()
    if not api_key:
        return {"success": False, "error": "Gemini API key missing. Set GOOGLE_GEMINI_API_KEY."}
    chosen_model = model or "gemini-2.0-flash"
    try:
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        messages = list(history or [])
        current = get_model_config()
        custom_system_prompt = str(current.get("custom_system_prompt", "")).strip()
        if custom_system_prompt and not any(msg.get("role") == "system" for msg in messages):
            messages.insert(0, {"role": "system", "content": custom_system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(model=chosen_model, messages=messages)
        reply = response.choices[0].message.content if response.choices else ""
        return {"success": True, "reply": reply or "", "model": chosen_model}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def chat_with_configured_model(prompt: str, history: list[dict[str, str]] | None = None, model: str | None = None) -> dict[str, Any]:
    try:
        config = dict(get_model_config() or {})
    except Exception as exc:
        return {"success": False, "error": f"Model config unavailable: {exc}"}

    provider = str(config.get("provider") or config.get("type") or "").strip().lower()
    if not provider or config.get("no_provider_configured"):
        return {"success": False, "error": "No configured AI provider available for fallback."}

    chosen_model = str(model or config.get("model") or "").strip()
    if chosen_model:
        config["model"] = chosen_model

    try:
        client = get_client(config)
        messages = list(history or [])
        custom_system_prompt = str(config.get("custom_system_prompt", "")).strip()
        if custom_system_prompt and not any(msg.get("role") == "system" for msg in messages):
            messages.insert(0, {"role": "system", "content": custom_system_prompt})
        messages.append({"role": "user", "content": prompt})
        if provider in {"anthropic", "gcp"}:
            response = client.messages.create(
                model=str(config.get("model") or chosen_model),
                max_tokens=2048,
                system=custom_system_prompt or None,
                messages=[msg for msg in messages if msg.get("role") != "system"],
            )
            reply_parts = []
            for block in getattr(response, "content", []) or []:
                if getattr(block, "type", "") == "text" and getattr(block, "text", ""):
                    reply_parts.append(block.text)
            reply = "\n".join(part for part in reply_parts if part).strip()
        else:
            response = client.chat.completions.create(
                model=str(config.get("model") or chosen_model),
                messages=messages,
            )
            reply = response.choices[0].message.content if response.choices else ""
        return {
            "success": True,
            "reply": reply or "",
            "model": str(config.get("model") or chosen_model),
            "provider": provider,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc), "provider": provider, "model": str(config.get("model") or chosen_model)}


def run_cli_agent(command_name: str, prompt: str, project_path: str = ".", install_hint: str = "") -> dict[str, Any]:
    executable = shutil.which(command_name)
    if not executable:
        fallback = chat_with_configured_model(prompt)
        if fallback.get("success"):
            fallback["fallback_used"] = True
            fallback["fallback_reason"] = f"{command_name} executable not found"
            fallback["requested_command"] = command_name
            fallback["project_path"] = project_path
            return fallback
        error = f"{command_name} not found. Install: {install_hint or command_name}"
        if fallback.get("error"):
            error = f"{error}. API fallback unavailable: {fallback['error']}"
        return {"success": False, "error": error}
    attempts = [
        [executable, "-p", prompt],
        [executable, "--prompt", prompt],
        [executable, prompt],
    ]
    last_error = ""
    for args in attempts:
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=180,
                check=False,
            )
            if result.returncode == 0:
                return {"success": True, "output": (result.stdout or "").strip(), "error": (result.stderr or "").strip()}
            last_error = (result.stderr or result.stdout or f"exit code {result.returncode}").strip()
        except Exception as exc:
            last_error = str(exc)
    fallback = chat_with_configured_model(prompt)
    if fallback.get("success"):
        fallback["fallback_used"] = True
        fallback["fallback_reason"] = last_error or f"{command_name} failed"
        fallback["requested_command"] = command_name
        fallback["project_path"] = project_path
        return fallback
    error = last_error or f"{command_name} failed."
    if fallback.get("error"):
        error = f"{error}. API fallback unavailable: {fallback['error']}"
    return {"success": False, "error": error}


def start_imos_mcp_server_http(project_root: str | Path) -> subprocess.Popen[Any]:
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(
        [sys.executable, "-m", "imos.mcp_server", "--http"],
        cwd=str(project_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=creationflags,
    )


def start_imos_mcp_server_http_on(project_root: str | Path, port: int = 8765, host: str = "127.0.0.1") -> subprocess.Popen[Any]:
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(
        [sys.executable, "-m", "imos.mcp_server", "--http", "--host", host, "--port", str(port)],
        cwd=str(project_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=creationflags,
    )


def open_cursor_workspace(project_path: str | Path) -> dict[str, Any]:
    path = str(project_path)
    searched: list[str] = []
    exe_candidates: list[str] = []
    local_appdata = os.getenv("LOCALAPPDATA", "").strip()
    appdata = os.getenv("APPDATA", "").strip()
    program_files = os.getenv("ProgramFiles", "").strip()
    program_files_x86 = os.getenv("ProgramFiles(x86)", "").strip()
    program_w6432 = os.getenv("ProgramW6432", "").strip()

    for candidate in [
        Path(local_appdata) / "Programs" / "cursor" / "Cursor.exe" if local_appdata else None,
        Path(local_appdata) / "Programs" / "Cursor" / "Cursor.exe" if local_appdata else None,
        Path(appdata) / "cursor" / "Cursor.exe" if appdata else None,
        Path(appdata) / "Cursor" / "Cursor.exe" if appdata else None,
        Path(program_files) / "Cursor" / "Cursor.exe" if program_files else None,
        Path(program_files) / "cursor" / "Cursor.exe" if program_files else None,
        Path(program_files_x86) / "Cursor" / "Cursor.exe" if program_files_x86 else None,
        Path(program_files_x86) / "cursor" / "Cursor.exe" if program_files_x86 else None,
        Path(program_w6432) / "Cursor" / "Cursor.exe" if program_w6432 else None,
        Path(program_w6432) / "cursor" / "Cursor.exe" if program_w6432 else None,
    ]:
        if candidate is None:
            continue
        searched.append(str(candidate))
        if candidate.exists():
            exe_candidates.append(str(candidate))

    path_hits = []
    for name in ["cursor", "Cursor", "cursor.cmd", "cursor.exe"]:
        searched.append(f"PATH:{name}")
        path_value = shutil.which(name)
        if path_value:
            path_hits.append(path_value)

    exe_candidates.extend(path_hits)
    candidates = [[exe, path] for exe in exe_candidates]
    last_error = ""
    for command in candidates:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.5)
            if process.poll() is not None:
                last_error = f"{command[0]} exited immediately with code {process.returncode}"
                continue
            return {
                "success": True,
                "path": path,
                "pid": process.pid,
                "command": command[0],
                "searched": searched,
            }
        except FileNotFoundError:
            continue
        except Exception as exc:
            last_error = str(exc)
    return {
        "success": False,
        "error": last_error or "Cursor was not found in common install locations or on PATH.",
        "searched": searched,
    }


def _launch_executable_candidates(
    exe_candidates: list[str],
    project_path: str | Path,
    searched: list[str],
    label: str,
) -> dict[str, Any]:
    path = str(project_path)
    last_error = ""
    for exe in exe_candidates:
        try:
            process = subprocess.Popen(
                [exe, path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.5)
            if process.poll() is not None:
                last_error = f"{exe} exited immediately with code {process.returncode}"
                continue
            return {
                "success": True,
                "path": path,
                "pid": process.pid,
                "command": exe,
                "searched": searched,
                "launcher": label,
            }
        except FileNotFoundError:
            continue
        except Exception as exc:
            last_error = str(exc)
    return {"success": False, "error": last_error, "searched": searched, "launcher": label}


def open_ide_with_fallback(project_path: str | Path, prompt: str = "") -> dict[str, Any]:
    local_appdata = os.getenv("LOCALAPPDATA", "").strip()
    appdata = os.getenv("APPDATA", "").strip()
    program_files = os.getenv("ProgramFiles", "").strip()
    program_files_x86 = os.getenv("ProgramFiles(x86)", "").strip()
    searched: list[str] = []

    cursor_result = open_cursor_workspace(project_path)
    searched.extend(cursor_result.get("searched", []))
    if cursor_result.get("success"):
        cursor_result["fallback_used"] = False
        return cursor_result

    def existing(paths: list[Path | None]) -> list[str]:
        items: list[str] = []
        for candidate in paths:
            if candidate is None:
                continue
            searched.append(str(candidate))
            if candidate.exists():
                items.append(str(candidate))
        return items

    windsurf_paths = existing([
        Path(local_appdata) / "Programs" / "Windsurf" / "Windsurf.exe" if local_appdata else None,
        Path(local_appdata) / "Programs" / "windsurf" / "Windsurf.exe" if local_appdata else None,
        Path(appdata) / "Windsurf" / "Windsurf.exe" if appdata else None,
        Path(program_files) / "Windsurf" / "Windsurf.exe" if program_files else None,
        Path(program_files_x86) / "Windsurf" / "Windsurf.exe" if program_files_x86 else None,
    ])
    for name in ["windsurf", "Windsurf", "windsurf.exe"]:
        searched.append(f"PATH:{name}")
        path_value = shutil.which(name)
        if path_value:
            windsurf_paths.append(path_value)
    windsurf_result = _launch_executable_candidates(windsurf_paths, project_path, searched, "Windsurf")
    if windsurf_result.get("success"):
        windsurf_result["fallback_used"] = True
        return windsurf_result

    vscode = shutil.which("code")
    searched.append("PATH:code")
    if vscode:
        vscode_result = _launch_executable_candidates([vscode], project_path, searched, "VS Code")
        if vscode_result.get("success"):
            vscode_result["fallback_used"] = True
            return vscode_result

    extra_names = [
        ("zed", "Zed.exe"),
        ("aide", "Aide.exe"),
        ("void", "Void.exe"),
        ("trae", "Trae.exe"),
        ("pycharm", "pycharm64.exe"),
        ("webstorm", "webstorm64.exe"),
    ]
    extra_candidates: list[str] = []
    for folder_name, exe_name in extra_names:
        for candidate in [
            Path(local_appdata) / "Programs" / folder_name / exe_name if local_appdata else None,
            Path(local_appdata) / "Programs" / folder_name.capitalize() / exe_name if local_appdata else None,
            Path(program_files) / folder_name.capitalize() / "bin" / exe_name if program_files else None,
            Path(program_files_x86) / folder_name.capitalize() / "bin" / exe_name if program_files_x86 else None,
        ]:
            if candidate is None:
                continue
            searched.append(str(candidate))
            if candidate.exists():
                extra_candidates.append(str(candidate))
    extra_result = _launch_executable_candidates(extra_candidates, project_path, searched, "alternate IDE")
    if extra_result.get("success"):
        extra_result["fallback_used"] = True
        return extra_result

    project_name = Path(project_path).name or "project"
    vibe_prompt = (prompt or f"Build the app for the current project: {project_name}.").strip()
    vibe_prompt += " Continue building the app until there is a complete working implementation."
    urls = [
        f"https://bolt.new/?prompt={urllib.parse.quote(vibe_prompt)}",
        f"https://v0.dev/chat?q={urllib.parse.quote(vibe_prompt)}",
        f"https://lovable.dev/?prompt={urllib.parse.quote(vibe_prompt)}",
    ]
    import webbrowser

    opened = []
    for url in urls:
        if webbrowser.open(url):
            opened.append(url)
    return {
        "success": bool(opened),
        "launcher": "browser fallback",
        "searched": searched,
        "urls": opened or urls,
        "prompt": vibe_prompt,
        "fallback_used": True,
        "error": "" if opened else "No desktop IDE found; opened browser fallback URLs.",
    }


def open_best_ide(project_path: str | Path, prompt: str = "") -> dict[str, Any]:
    return open_ide_with_fallback(project_path, prompt=prompt)


def cursor_mcp_http_snippet(url: str = "http://127.0.0.1:8765/mcp") -> str:
    return (
        '{\n'
        '  "mcpServers": {\n'
        '    "imos": {\n'
        f'      "url": "{url}"\n'
        '    }\n'
        '  }\n'
        '}'
    )


def open_workspace_in_app(command_name: str, project_path: str | Path, install_hint: str = "") -> dict[str, Any]:
    executable = shutil.which(command_name)
    if not executable:
        return {"success": False, "error": f"{command_name} not found. Install: {install_hint or command_name}"}
    try:
        proc = subprocess.Popen([executable, str(project_path)])
        return {"success": True, "pid": proc.pid, "command": executable, "path": str(project_path)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def open_prompt_url(base_url: str, prompt: str) -> dict[str, Any]:
    import webbrowser

    url = f"{base_url}{urllib.parse.quote(prompt)}"
    webbrowser.open(url)
    return {"success": True, "url": url}


def send_email_smtp(to_addr: str, subject: str, body: str) -> dict[str, Any]:
    host = os.getenv("EMAIL_SMTP_HOST", "").strip()
    port = int(os.getenv("EMAIL_SMTP_PORT", "587") or 587)
    username = os.getenv("EMAIL_USERNAME", "").strip()
    password = os.getenv("EMAIL_PASSWORD", "").strip()
    from_addr = os.getenv("EMAIL_FROM", username).strip()
    if not host or not username or not password or not from_addr:
        return {"success": False, "error": "Email not configured. Set EMAIL_SMTP_HOST, EMAIL_USERNAME, EMAIL_PASSWORD, and EMAIL_FROM."}
    message = f"From: {from_addr}\r\nTo: {to_addr}\r\nSubject: {subject}\r\n\r\n{body}"
    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(username, password)
            server.sendmail(from_addr, [to_addr], message.encode("utf-8"))
        return {"success": True, "to": to_addr, "subject": subject}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
