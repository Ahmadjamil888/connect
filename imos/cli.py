from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import webbrowser
import shutil
from pathlib import Path

import click
import httpx
from imos.config import list_configured_adapters, remove_adapter_config, save_adapter_config
from imos.mcp_server import install_mcp_configs
from imos.models import IMOSTask
from imos.orchestrator import IMOSOrchestrator
from imos.registry import AdapterRegistry
from imos.router import TaskRouter
from imos.session_runtime import IMOSSessionRuntime
from imos.ui import get_ui_config, save_ui_config
from imos.wake_service import _install_autostart_file, start_background as start_wake_service, status as wake_status, stop_background as stop_wake_service, uninstall_autostart


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _is_windows() -> bool:
    return os.name == "nt"


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _remove_path_entry(current_path: str, target: str) -> str:
    normalized_target = target.strip().rstrip("\\/").lower()
    kept: list[str] = []
    for item in current_path.split(os.pathsep):
        cleaned = item.strip()
        if not cleaned:
            continue
        if cleaned.rstrip("\\/").lower() == normalized_target:
            continue
        kept.append(cleaned)
    return os.pathsep.join(kept)


def _launch_runtime_in_terminal() -> bool:
    command = "imos"
    if _is_windows():
        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(["powershell", "-NoExit", "-Command", command], creationflags=creationflags)
        return True
    if _is_macos():
        script = f'tell application "Terminal" to do script "{command}"'
        subprocess.Popen(["osascript", "-e", script])
        return True
    for args in (
        ["x-terminal-emulator", "-e", command],
        ["gnome-terminal", "--", command],
        ["konsole", "-e", command],
        ["xfce4-terminal", "-e", command],
        ["xterm", "-e", command],
    ):
        try:
            subprocess.Popen(args)
            return True
        except Exception:
            continue
    return False


def _remove_windows_user_path_entry(target: Path) -> bool:
    if not _is_windows():
        return False
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        )
        try:
            current_path, reg_type = winreg.QueryValueEx(key, "PATH")
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
        updated_path = _remove_path_entry(str(current_path), str(target))
        if updated_path == current_path:
            winreg.CloseKey(key)
            return False
        winreg.SetValueEx(key, "PATH", 0, reg_type, updated_path)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def _remove_cli_launchers() -> list[str]:
    removed: list[str] = []
    executable_dir = Path(sys.executable).resolve().parent
    targets = [Path.home() / "imos-bin" / "imos.cmd"]
    if _is_windows():
        targets.extend(
            [
                executable_dir / "imos.bat",
                executable_dir / "imos.exe",
                executable_dir / "imos-script.py",
            ]
        )
    else:
        targets.append(Path.home() / ".local" / "bin" / "imos")
    for path in targets:
        try:
            if path.exists():
                path.unlink()
                removed.append(str(path))
        except Exception:
            continue
    return removed


def _run_pip_uninstall() -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "connectai"],
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    details = stdout or stderr or f"pip exited with code {result.returncode}"
    return {"ok": result.returncode == 0, "details": details}


async def _build_orchestrator() -> IMOSOrchestrator:
    registry = AdapterRegistry()
    await registry.auto_discover()
    return IMOSOrchestrator(registry)

async def _build_runtime() -> IMOSSessionRuntime:
    return IMOSSessionRuntime(await _build_orchestrator())

def _launch_legacy_shell() -> None:
    try:
        from imos.operator_shell import run

        run()
    except Exception as exc:
        if exc.__class__.__name__ != "NoConsoleScreenBufferError":
            raise
        _interactive_shell("default")

def _interactive_shell(session_name: str, beast_mode: bool = False) -> None:
    async def _run() -> None:
        runtime = await _build_runtime()
        session_id = runtime.ensure_session(session_name)
        click.echo(f"IMOS session: {session_name} ({session_id})")
        click.echo("Type `exit` or `quit` to stop.")
        while True:
            prompt = click.prompt("imos", prompt_suffix="> ", type=str)
            if prompt.strip().lower() in {"exit", "quit"}:
                break
            result = await runtime.run_turn(prompt, session_id=session_id, session_name=session_name, context={"beast_mode": beast_mode})
            click.echo(result.final_response)

    asyncio.run(_run())


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        _launch_legacy_shell()


@cli.command()
@click.option("--session", "session_name", default="default", help="Session name")
@click.option("--beast", "beast_mode", is_flag=True, help="Fan the prompt out to all configured model and IDE adapters")
def shell(session_name: str, beast_mode: bool) -> None:
    if session_name == "default" and not beast_mode:
        _launch_legacy_shell()
        return
    _interactive_shell(session_name, beast_mode=beast_mode)


@cli.command("legacy-shell")
def legacy_shell() -> None:
    _launch_legacy_shell()


@cli.command()
@click.argument("prompt")
@click.option("--adapters", default="", help="Comma-separated adapter targets")
@click.option("--session", "session_name", default="default", help="Persistent session name")
@click.option("--beast", "beast_mode", is_flag=True, help="Run prompt across multiple model and IDE adapters")
def run(prompt: str, adapters: str, session_name: str, beast_mode: bool) -> None:
    async def _run():
        runtime = await _build_runtime()
        context = {
            "target_adapters": [item.strip() for item in adapters.split(",") if item.strip()],
            "beast_mode": beast_mode,
        }
        result = await runtime.run_turn(prompt, session_name=session_name, context=context)
        click.echo(result.final_response)

    asyncio.run(_run())


@cli.group(invoke_without_command=True)
@click.pass_context
def adapters(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@adapters.command("list")
def adapters_list() -> None:
    async def _list():
        orchestrator = await _build_orchestrator()
        rows = [{"name": item.name, "type": item.adapter_type, "status": item.status} for item in orchestrator.registry.get_all()]
        click.echo(json.dumps(rows, indent=2))

    asyncio.run(_list())


@adapters.command("add")
@click.argument("adapter_type")
@click.argument("name")
@click.option("--provider", default=None, help="Provider or adapter kind")
@click.option("--model", default=None, help="Model name when applicable")
@click.option("--api-key", default=None, help="API key when applicable")
@click.option("--base-url", default=None, help="Base URL when applicable")
def adapters_add(adapter_type: str, name: str, provider: str | None, model: str | None, api_key: str | None, base_url: str | None) -> None:
    provider = provider or click.prompt("Provider/kind", default=name)
    model = model if model is not None else click.prompt("Model (optional)", default="", show_default=False)
    api_key = api_key if api_key is not None else click.prompt("API key (optional)", default="", hide_input=True, show_default=False)
    base_url = base_url if base_url is not None else click.prompt("Base URL (optional)", default="", show_default=False)
    config = {"name": name, "adapter_type": adapter_type, "provider": provider}
    if model:
        config["model"] = model
    if api_key:
        config["api_key"] = api_key
    if base_url:
        config["base_url"] = base_url
    save_adapter_config(name, config)
    click.echo(f"Added adapter {name}")


@adapters.command("test")
@click.argument("name")
def adapters_test(name: str) -> None:
    async def _test():
        orchestrator = await _build_orchestrator()
        adapter = orchestrator.registry.get(name)
        if not adapter:
            click.echo(f"Adapter not found: {name}")
            return
        click.echo(json.dumps({"name": name, "healthy": await adapter.health_check()}, indent=2))

    asyncio.run(_test())


@adapters.command("remove")
@click.argument("name")
def adapters_remove(name: str) -> None:
    remove_adapter_config(name)
    click.echo(f"Removed adapter {name}")


@cli.command()
def history() -> None:
    async def _history():
        orchestrator = await _build_orchestrator()
        click.echo(json.dumps(orchestrator.context_manager.recent_history(50), indent=2))

    asyncio.run(_history())


@cli.group(invoke_without_command=True)
@click.pass_context
def sessions(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@sessions.command("list")
def sessions_list() -> None:
    async def _list():
        runtime = await _build_runtime()
        click.echo(json.dumps(runtime.list_sessions(), indent=2))

    asyncio.run(_list())


@sessions.command("history")
@click.argument("session_id")
@click.option("--limit", default=30, type=int, help="History limit")
def sessions_history(session_id: str, limit: int) -> None:
    async def _history():
        runtime = await _build_runtime()
        click.echo(json.dumps(runtime.history(session_id, limit=limit), indent=2))

    asyncio.run(_history())


@sessions.command("status")
@click.argument("session_id")
def sessions_status(session_id: str) -> None:
    async def _status():
        runtime = await _build_runtime()
        click.echo(json.dumps(runtime.status(session_id), indent=2))

    asyncio.run(_status())


@sessions.command("export")
@click.argument("session_id")
def sessions_export(session_id: str) -> None:
    async def _export():
        runtime = await _build_runtime()
        click.echo(json.dumps(runtime.export_session(session_id), indent=2))

    asyncio.run(_export())


@cli.command()
def status() -> None:
    async def _status():
        orchestrator = await _build_orchestrator()
        click.echo(
            json.dumps(
                {
                    "configured_adapters": list_configured_adapters(),
                    "loaded_adapters": [{"name": item.name, "status": item.status} for item in orchestrator.registry.get_all()],
                },
                indent=2,
            )
        )

    asyncio.run(_status())


@cli.command("self-test")
def self_test() -> None:
    async def _self_test():
        orchestrator = await _build_orchestrator()
        runtime = IMOSSessionRuntime(orchestrator)
        router = TaskRouter(orchestrator.registry, orchestrator.settings, synthesis_adapter=orchestrator.synthesis_adapter)
        report: dict[str, object] = {"checks": []}

        def add_check(name: str, ok: bool, details: object) -> None:
            report["checks"].append({"name": name, "ok": ok, "details": details})

        adapters = orchestrator.registry.get_all()
        add_check(
            "adapter_registry",
            True,
            [{"name": item.name, "type": item.adapter_type, "status": item.status} for item in adapters],
        )

        scan_task = router._heuristic_decompose("scan my pc for unwanted files")[0].subtasks[0]
        add_check(
            "router_scan_unwanted_files",
            scan_task.subtask_type == "search_files" and scan_task.metadata.get("action") == "scan_unwanted_files",
            {"subtask_type": scan_task.subtask_type, "action": scan_task.metadata.get("action")},
        )

        cleanup_task = router._heuristic_decompose("remove all unwanted files from my pc")[0].subtasks[0]
        add_check(
            "router_delete_unwanted_files",
            cleanup_task.subtask_type == "cleanup_files" and cleanup_task.metadata.get("action") == "delete_unwanted_files",
            {"subtask_type": cleanup_task.subtask_type, "action": cleanup_task.metadata.get("action"), "params": cleanup_task.metadata.get("params", {})},
        )

        os_adapter = orchestrator.registry.get("local_os")
        if os_adapter is not None:
            system_info = await os_adapter.send(
                IMOSTask(
                    task_id="selftest-system-info",
                    prompt="show system info",
                    subtask_type="system_info",
                    target_adapter=os_adapter.name,
                    metadata={"action": "system_info"},
                )
            )
            add_check("local_os_system_info", system_info.success, system_info.output if system_info.success else system_info.error)

            scan_result = await os_adapter.send(
                IMOSTask(
                    task_id="selftest-scan",
                    prompt="scan my pc for unwanted files",
                    subtask_type="search_files",
                    target_adapter=os_adapter.name,
                    metadata={"action": "scan_unwanted_files", "params": {}},
                )
            )
            add_check(
                "local_os_scan_unwanted_files",
                scan_result.success and isinstance(scan_result.output, dict) and "matches" in scan_result.output,
                scan_result.output if scan_result.success else scan_result.error,
            )

            cleanup_root = Path.cwd() / ".imos_selftest_cleanup"
            if cleanup_root.exists():
                shutil.rmtree(cleanup_root, ignore_errors=True)
            cleanup_root.mkdir(parents=True, exist_ok=True)
            junk = cleanup_root / "junk.tmp"
            keep = cleanup_root / "keep.txt"
            junk.write_text("junk", encoding="utf-8")
            keep.write_text("keep", encoding="utf-8")
            try:
                cleanup_result = await os_adapter.send(
                    IMOSTask(
                        task_id="selftest-cleanup",
                        prompt="remove all unwanted files from my pc",
                        subtask_type="cleanup_files",
                        target_adapter=os_adapter.name,
                        metadata={"action": "delete_unwanted_files", "params": {"root": str(cleanup_root), "confirm": True}},
                    )
                )
                ok = (
                    cleanup_result.success
                    and isinstance(cleanup_result.output, dict)
                    and cleanup_result.output.get("deleted_count") == 1
                    and keep.exists()
                    and not junk.exists()
                )
                add_check("local_os_delete_unwanted_files", ok, cleanup_result.output if cleanup_result.success else cleanup_result.error)
            finally:
                shutil.rmtree(cleanup_root, ignore_errors=True)

        ide_adapter = orchestrator.registry.get("local_ide")
        if ide_adapter is not None:
            ide_root = Path.cwd() / ".imos_selftest_ide"
            if ide_root.exists():
                shutil.rmtree(ide_root, ignore_errors=True)
            ide_root.mkdir(parents=True, exist_ok=True)
            original_workspace = getattr(ide_adapter, "workspace", None)
            try:
                ide_adapter.workspace = ide_root
                delegated = await ide_adapter.send(
                    IMOSTask(
                        task_id="selftest-ide-delegate",
                        prompt="write a sample file",
                        subtask_type="code_generation",
                        target_adapter=ide_adapter.name,
                        metadata={"action": "delegate_prompt", "params": {"prompt": "write a sample file"}},
                    )
                )
                delegated_path = None
                if delegated.success and isinstance(delegated.output, dict):
                    delegated_path = delegated.output.get("inbox_path")
                add_check("local_ide_delegate_prompt", delegated.success and bool(delegated_path) and Path(str(delegated_path)).exists(), delegated.output if delegated.success else delegated.error)
            finally:
                if original_workspace is not None:
                    ide_adapter.workspace = original_workspace
                shutil.rmtree(ide_root, ignore_errors=True)

        model_adapter = orchestrator.registry.get("default_model")
        if model_adapter is not None:
            healthy = await model_adapter.health_check()
            add_check("default_model_health", healthy and model_adapter.status == "connected", {"status": model_adapter.status})

        browser_adapter = orchestrator.registry.get("local_browser")
        if browser_adapter is not None:
            healthy = await browser_adapter.health_check()
            add_check("local_browser_health", healthy and browser_adapter.status == "connected", {"status": browser_adapter.status})

        session_id = runtime.ensure_session("self-test")
        add_check("session_runtime", bool(session_id), {"session_id": session_id})

        click.echo(json.dumps(report, indent=2))

    asyncio.run(_self_test())


@cli.group(invoke_without_command=True)
@click.pass_context
def mcp(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@mcp.command("install")
def mcp_install() -> None:
    click.echo(json.dumps(install_mcp_configs(), indent=2))


@cli.command()
def login() -> None:
    from imos import auth

    sys.exit(0 if auth.cmd_login() else 1)


@cli.command()
def logout() -> None:
    from imos import auth

    auth.cmd_logout()


@cli.command()
def whoami() -> None:
    from imos import auth

    auth.cmd_whoami_clerk()


@cli.command()
def dashboard() -> None:
    port = 7070
    try:
        from config.config import load_config

        port = int(load_config().get("dashboard", {}).get("port", 7070) or 7070)
    except Exception:
        port = 7070
    dashboard_url = f"http://127.0.0.1:{port}/"
    healthy = False
    try:
        response = httpx.get(f"{dashboard_url}api/status", timeout=2.0)
        healthy = response.status_code < 500
    except Exception:
        healthy = False

    if not healthy:
        launched_terminal = _launch_runtime_in_terminal()
        if not launched_terminal:
            subprocess.Popen(
                [sys.executable, str(_project_root() / "imos_server.py"), "--no-browser"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        for _ in range(20):
            try:
                response = httpx.get(f"{dashboard_url}api/status", timeout=2.0)
                if response.status_code < 500:
                    healthy = True
                    break
            except Exception:
                time.sleep(0.5)
    webbrowser.open(dashboard_url)
    if healthy:
        click.echo("Opened IMOS dashboard")
    elif _is_windows():
        click.echo("Opened IMOS dashboard and launched the runtime in a new terminal window")
    else:
        click.echo("Started IMOS dashboard and opened browser")


@cli.group(invoke_without_command=True)
@click.pass_context
def wake(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@wake.command("start")
def wake_start() -> None:
    click.echo(start_wake_service())


@wake.command("stop")
def wake_stop() -> None:
    click.echo(stop_wake_service())


@wake.command("status")
def wake_status_command() -> None:
    click.echo(json.dumps(wake_status(), indent=2))


@wake.command("install")
def wake_install() -> None:
    path = _install_autostart_file()
    result = start_wake_service()
    click.echo(json.dumps({"autostart": str(path), "service": result}, indent=2))


@wake.command("uninstall")
def wake_uninstall() -> None:
    removed = [str(path) for path in uninstall_autostart()]
    stopped = stop_wake_service()
    click.echo(json.dumps({"removed": removed, "service": stopped}, indent=2))


@cli.group(invoke_without_command=True)
@click.pass_context
def install(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@install.command("wake")
def install_wake_alias() -> None:
    path = _install_autostart_file()
    result = start_wake_service()
    click.echo(json.dumps({"autostart": str(path), "service": result}, indent=2))


@install.command("mcp")
def install_mcp_alias() -> None:
    click.echo(json.dumps(install_mcp_configs(), indent=2))


@cli.command()
def uninstall() -> None:
    removed_autostart = [str(path) for path in uninstall_autostart()]
    wake_result = stop_wake_service()
    removed_launchers = _remove_cli_launchers()
    removed_path = False
    if _is_windows():
        removed_path = _remove_windows_user_path_entry(Path.home() / "imos-bin")
    pip_result = _run_pip_uninstall()
    report = {
        "wake_service": wake_result,
        "removed_autostart": removed_autostart,
        "removed_launchers": removed_launchers,
        "removed_path_entry": removed_path,
        "pip_uninstall": pip_result,
        "repository_root": str(_project_root()),
        "note": "Local repo files and ~/.imos data were left in place.",
    }
    click.echo(json.dumps(report, indent=2))


@cli.group(invoke_without_command=True)
@click.pass_context
def palette(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(json.dumps(get_ui_config(), indent=2))


@palette.command("list")
def palette_list() -> None:
    click.echo(json.dumps(get_ui_config(), indent=2))


@palette.command("set")
@click.option("--shell", "shell_palette", default=None, help="Shell palette name")
@click.option("--dashboard", "dashboard_palette", default=None, help="Dashboard palette name")
def palette_set(shell_palette: str | None, dashboard_palette: str | None) -> None:
    updated = save_ui_config(shell_palette=shell_palette, dashboard_palette=dashboard_palette)
    click.echo(json.dumps(updated, indent=2))


def main(argv: list[str] | None = None) -> None:
    cli.main(args=argv, prog_name="imos", standalone_mode=False)


if __name__ == "__main__":
    main()
