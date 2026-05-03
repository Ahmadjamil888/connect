from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
import webbrowser

import click
import httpx
from imos.config import list_configured_adapters, remove_adapter_config, save_adapter_config
from imos.mcp_server import install_mcp_configs
from imos.orchestrator import IMOSOrchestrator
from imos.registry import AdapterRegistry
from imos.session_runtime import IMOSSessionRuntime
from imos.ui import get_ui_config, save_ui_config
from imos.wake_service import _install_autostart_file, start_background as start_wake_service, status as wake_status, stop_background as stop_wake_service, uninstall_autostart


async def _build_orchestrator() -> IMOSOrchestrator:
    registry = AdapterRegistry()
    await registry.auto_discover()
    return IMOSOrchestrator(registry)

async def _build_runtime() -> IMOSSessionRuntime:
    return IMOSSessionRuntime(await _build_orchestrator())

def _launch_legacy_shell() -> None:
    import ai_assistant

    original_argv = sys.argv[:]
    try:
        sys.argv = ["imos"]
        ai_assistant.main()
    finally:
        sys.argv = original_argv

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
        _interactive_shell("default")


@cli.command()
@click.option("--session", "session_name", default="default", help="Session name")
@click.option("--beast", "beast_mode", is_flag=True, help="Fan the prompt out to all configured model and IDE adapters")
def shell(session_name: str, beast_mode: bool) -> None:
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


@cli.group(invoke_without_command=True)
@click.pass_context
def mcp(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@mcp.command("install")
def mcp_install() -> None:
    click.echo(json.dumps(install_mcp_configs(), indent=2))


@cli.command()
def dashboard() -> None:
    try:
        from config.config import load_config

        port = int(load_config().get("dashboard", {}).get("port", 5000) or 5000)
    except Exception:
        port = 5000
    dashboard_url = f"http://127.0.0.1:{port}/"
    healthy = False
    try:
        response = httpx.get(f"{dashboard_url}api/status", timeout=2.0)
        healthy = response.status_code < 500
    except Exception:
        healthy = False

    if not healthy:
        subprocess.Popen(
            [sys.executable, "imos_server.py", "--no-browser"],
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
    click.echo("Opened IMOS dashboard" if healthy else "Started IMOS dashboard and opened browser")


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
