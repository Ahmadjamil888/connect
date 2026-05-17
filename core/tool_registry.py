from __future__ import annotations

from typing import Any

from tools import app_tools, browser_tools, external_ai_tools, filesystem_tools, git_tools, ide_tools, terminal_tools, web_platform_tools


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}
        self._register_all()

    def register(self, name: str, fn, consent_scope: str, description: str, json_schema: dict[str, Any]) -> None:
        self._tools[name] = {
            "fn": fn,
            "consent_scope": consent_scope,
            "description": description,
            "json_schema": json_schema,
        }

    def get(self, name: str) -> dict[str, Any] | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": meta["description"],
                    "parameters": meta["json_schema"],
                },
            }
            for name, meta in sorted(self._tools.items())
        ]

    def anthropic_tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "description": meta["description"],
                "input_schema": meta["json_schema"],
            }
            for name, meta in sorted(self._tools.items())
        ]

    def _register_all(self) -> None:
        obj = {"type": "object", "properties": {}, "required": []}
        self.register("browser.navigate", browser_tools.navigate, "browser", "Navigate a real Chromium browser to a URL", {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]})
        self.register("browser.click", browser_tools.click, "browser", "Click a real DOM element by selector or visible text", {"type": "object", "properties": {"selector": {"type": "string"}, "by_text": {"type": "string"}}})
        self.register("browser.type", browser_tools.type, "browser", "Type real text into a DOM element selected by CSS selector", {"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]})
        self.register("browser.get_text", browser_tools.get_text, "browser", "Read actual text from the current browser page", {"type": "object", "properties": {"selector": {"type": "string"}}})
        self.register("browser.wait_for_text", browser_tools.wait_for_text, "browser", "Wait until visible text appears on the page", {"type": "object", "properties": {"text": {"type": "string"}, "timeout_ms": {"type": "integer"}}, "required": ["text"]})
        self.register("browser.screenshot", browser_tools.screenshot, "browser", "Save a real browser screenshot to disk", {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
        self.register("browser.get_url", browser_tools.get_url, "browser", "Return the current browser URL", obj)
        self.register("browser.execute_js", browser_tools.execute_js, "browser", "Execute JavaScript in the current page", {"type": "object", "properties": {"script": {"type": "string"}}, "required": ["script"]})
        self.register("browser.fill_form", browser_tools.fill_form, "browser", "Fill multiple form fields by selector", {"type": "object", "properties": {"fields": {"type": "object", "additionalProperties": {"type": "string"}}}, "required": ["fields"]})
        self.register("browser.new_tab", browser_tools.new_tab, "browser", "Open a new browser tab and optionally navigate to a URL", {"type": "object", "properties": {"url": {"type": "string"}}})

        self.register("terminal.run_command", terminal_tools.run_command, "terminal", "Run a real shell command and capture stdout and stderr", {"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]})
        self.register("terminal.run_command_interactive", terminal_tools.run_command_interactive, "terminal", "Run a real shell command and capture streamed output", {"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}}, "required": ["command"]})

        self.register("fs.read_file", filesystem_tools.read_file, "", "Read a real file from disk", {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
        self.register("fs.write_file", filesystem_tools.write_file, "filesystem_write", "Write or append real content to disk", {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "mode": {"type": "string", "enum": ["write", "append"]}}, "required": ["path", "content"]})
        self.register("fs.create_directory", filesystem_tools.create_directory, "filesystem_write", "Create a real directory", {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
        self.register("fs.list_directory", filesystem_tools.list_directory, "", "List a real directory tree", {"type": "object", "properties": {"path": {"type": "string"}, "depth": {"type": "integer"}}, "required": ["path"]})
        self.register("fs.delete_file", filesystem_tools.delete_file, "filesystem_delete", "Delete a real file or directory", {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
        self.register("fs.move_file", filesystem_tools.move_file, "filesystem_write", "Move a real file or directory", {"type": "object", "properties": {"src": {"type": "string"}, "dst": {"type": "string"}}, "required": ["src", "dst"]})
        self.register("fs.search_files", filesystem_tools.search_files, "", "Search real files on disk by filename and optional content", {"type": "object", "properties": {"root": {"type": "string"}, "pattern": {"type": "string"}, "content_search": {"type": "string"}}, "required": ["root"]})

        self.register("git.init", git_tools.git_init, "terminal", "Initialize a real git repository", {"type": "object", "properties": {"cwd": {"type": "string"}}, "required": ["cwd"]})
        self.register("git.status", git_tools.git_status, "", "Get real git status", {"type": "object", "properties": {"cwd": {"type": "string"}}, "required": ["cwd"]})
        self.register("git.add", git_tools.git_add, "terminal", "Stage files with git add", {"type": "object", "properties": {"cwd": {"type": "string"}, "paths": {"type": "array", "items": {"type": "string"}}}, "required": ["cwd"]})
        self.register("git.commit", git_tools.git_commit, "terminal", "Create a real git commit", {"type": "object", "properties": {"cwd": {"type": "string"}, "message": {"type": "string"}}, "required": ["cwd", "message"]})
        self.register("git.push", git_tools.git_push, "network", "Push commits to a real git remote", {"type": "object", "properties": {"cwd": {"type": "string"}, "remote": {"type": "string"}, "branch": {"type": "string"}, "set_upstream": {"type": "boolean"}}, "required": ["cwd"]})
        self.register("git.clone", git_tools.git_clone, "network", "Clone a real git repository", {"type": "object", "properties": {"repo_url": {"type": "string"}, "destination": {"type": "string"}}, "required": ["repo_url", "destination"]})
        self.register("git.create_branch", git_tools.git_create_branch, "terminal", "Create a real git branch", {"type": "object", "properties": {"cwd": {"type": "string"}, "branch": {"type": "string"}, "checkout": {"type": "boolean"}}, "required": ["cwd", "branch"]})
        self.register("git.log", git_tools.git_log, "", "Read real git commit history", {"type": "object", "properties": {"cwd": {"type": "string"}, "max_count": {"type": "integer"}}, "required": ["cwd"]})
        self.register("github.create_repo", git_tools.github_create_repo, "network", "Create a real GitHub repository via API", {"type": "object", "properties": {"name": {"type": "string"}, "private": {"type": "boolean"}, "description": {"type": "string"}}, "required": ["name"]})
        self.register("github.create_pr", git_tools.github_create_pr, "network", "Create a real GitHub pull request via API", {"type": "object", "properties": {"repo_owner": {"type": "string"}, "repo_name": {"type": "string"}, "head": {"type": "string"}, "base": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}}, "required": ["repo_owner", "repo_name", "head", "base", "title"]})
        self.register("github.create_repo_and_push", git_tools.create_github_repo_and_push, "network", "Create a real GitHub repo and push local code to it", {"type": "object", "properties": {"project_path": {"type": "string"}, "repo_name": {"type": "string"}, "commit_message": {"type": "string"}, "private": {"type": "boolean"}}, "required": ["project_path", "repo_name"]})

        self.register("ide.open_cursor", ide_tools.open_cursor, "app_launch", "Open a path in Cursor", {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
        self.register("ide.open_vscode", ide_tools.open_vscode, "app_launch", "Open a path in VS Code", {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
        self.register("ide.open_in_ide", ide_tools.open_in_ide, "app_launch", "Open a path in the best available IDE", {"type": "object", "properties": {"path": {"type": "string"}, "ide": {"type": "string", "enum": ["auto", "cursor", "vscode"]}}, "required": ["path"]})

        self.register("ai.run_claude_code", external_ai_tools.run_claude_code, "terminal", "Run the real Claude Code CLI", {"type": "object", "properties": {"project_path": {"type": "string"}, "task": {"type": "string"}}, "required": ["project_path", "task"]})
        self.register("ai.run_codex", external_ai_tools.run_codex, "terminal", "Run the real Codex CLI", {"type": "object", "properties": {"project_path": {"type": "string"}, "task": {"type": "string"}}, "required": ["project_path", "task"]})
        self.register("ai.run_aider", external_ai_tools.run_aider, "terminal", "Run the real aider CLI", {"type": "object", "properties": {"project_path": {"type": "string"}, "task": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}}}, "required": ["project_path", "task"]})

        self.register("platform.lovable_build_project", web_platform_tools.lovable_build_project, "browser", "Build a project on lovable.dev using real browser automation", {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]})
        self.register("platform.vercel_deploy", web_platform_tools.vercel_deploy, "network", "Deploy a project with the real Vercel CLI", {"type": "object", "properties": {"project_path": {"type": "string"}, "prod": {"type": "boolean"}}, "required": ["project_path"]})
        self.register("platform.netlify_deploy", web_platform_tools.netlify_deploy, "network", "Deploy a project with the real Netlify CLI", {"type": "object", "properties": {"project_path": {"type": "string"}, "prod": {"type": "boolean"}}, "required": ["project_path"]})

        self.register("app.open_application", app_tools.open_application, "app_launch", "Open a real desktop application", {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]})
        self.register("app.take_screenshot", app_tools.take_screenshot, "browser", "Capture a real desktop screenshot", {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
        self.register("app.get_clipboard", app_tools.get_clipboard, "", "Read the real system clipboard", obj)
        self.register("app.set_clipboard", app_tools.set_clipboard, "clipboard_write", "Write to the real system clipboard", {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})
        self.register("app.list_processes", app_tools.list_processes, "", "List real running processes", {"type": "object", "properties": {"filter": {"type": "string"}}})
        self.register("app.kill_process", app_tools.kill_process, "terminal", "Terminate a real process by pid or name", {"type": "object", "properties": {"pid": {"type": "integer"}, "name": {"type": "string"}}})
