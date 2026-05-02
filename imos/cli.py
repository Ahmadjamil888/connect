from __future__ import annotations

import asyncio
import json
import webbrowser
from pathlib import Path

import click

from imos.config import list_configured_adapters, remove_adapter_config, save_adapter_config
from imos.mcp_server import install_mcp_configs
from imos.orchestrator import IMOSOrchestrator
from imos.registry import AdapterRegistry


async def _build_orchestrator() -> IMOSOrchestrator:
    registry = AdapterRegistry()
    await registry.auto_discover()
    return IMOSOrchestrator(registry)


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.argument("prompt")
@click.option("--adapters", default="", help="Comma-separated adapter targets")
def run(prompt: str, adapters: str) -> None:
    async def _run():
        orchestrator = await _build_orchestrator()
        context = {"target_adapters": [item.strip() for item in adapters.split(",") if item.strip()]} if adapters else {}
        result = await orchestrator.run(prompt, context=context)
        click.echo(result.final_response)

    asyncio.run(_run())


@cli.group()
def adapters() -> None:
    pass


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
def adapters_add(adapter_type: str, name: str) -> None:
    provider = click.prompt("Provider/kind", default=name)
    model = click.prompt("Model (optional)", default="", show_default=False)
    config = {"name": name, "adapter_type": adapter_type, "provider": provider}
    if model:
        config["model"] = model
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


@cli.group()
def mcp() -> None:
    pass


@mcp.command("install")
def mcp_install() -> None:
    click.echo(json.dumps(install_mcp_configs(), indent=2))


@cli.command()
def dashboard() -> None:
    webbrowser.open("http://127.0.0.1:8765/imos")
    click.echo("Opened IMOS dashboard")


def main(argv: list[str] | None = None) -> None:
    cli.main(args=argv, prog_name="imos", standalone_mode=False)


if __name__ == "__main__":
    main()
