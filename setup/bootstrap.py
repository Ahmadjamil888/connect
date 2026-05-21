"""Post-install bootstrap: IMOS home, providers, services catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

IMOS_HOME = Path.home() / ".imos"
CUSTOM_SERVICES_PATH = IMOS_HOME / "custom_services.json"
PROVIDERS_PATH = Path(__file__).resolve().parents[1] / "config" / "providers.json"


def initialize_imos_runtime(project_root: Path | None = None) -> dict[str, Any]:
    """Create local dirs, default config, migrate env keys into providers.json."""
    root = project_root or Path(__file__).resolve().parents[1]
    IMOS_HOME.mkdir(parents=True, exist_ok=True)
    (IMOS_HOME / "sessions").mkdir(parents=True, exist_ok=True)
    (IMOS_HOME / "exports").mkdir(parents=True, exist_ok=True)

    if not CUSTOM_SERVICES_PATH.exists():
        CUSTOM_SERVICES_PATH.write_text("[]\n", encoding="utf-8")

    try:
        from imos.config import ensure_default_files

        ensure_default_files()
    except Exception:
        pass

    from core import model_manager

    migrated = model_manager.migrate_env_to_providers()
    providers = model_manager.load_providers()

    try:
        from core.services_catalog import list_all_services

        services = list_all_services()
        service_count = len(services)
        available_count = sum(1 for s in services if s.get("available"))
    except Exception:
        services = []
        service_count = 0
        available_count = 0

    return {
        "imos_home": str(IMOS_HOME),
        "providers": len(providers),
        "migrated_from_env": len(migrated),
        "services_total": service_count,
        "services_available": available_count,
        "project_root": str(root),
    }


def print_bootstrap_summary(summary: dict[str, Any]) -> None:
    print(f"  IMOS home:     {summary.get('imos_home', '')}")
    print(f"  Providers:     {summary.get('providers', 0)} saved")
    print(f"  Services:      {summary.get('services_available', 0)}/{summary.get('services_total', 0)} available")
    print(f"  CLI models:    imos -> /model add <type> <model-id> [key] [base_url]")
    print(f"  CLI services:  /services  |  /service add <name> [detail]")
    print(f"  Dashboard:     http://127.0.0.1:7070")


if __name__ == "__main__":
    result = initialize_imos_runtime(Path(__file__).resolve().parents[1])
    print_bootstrap_summary(result)
