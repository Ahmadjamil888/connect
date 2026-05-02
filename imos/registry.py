from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path
from typing import Any

from imos.adapters.base import IMOSAdapter
from imos.config import get_adapter_config, list_configured_adapters


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, IMOSAdapter] = {}

    def register(self, adapter: IMOSAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def unregister(self, name: str) -> None:
        self._adapters.pop(name, None)

    def get(self, name: str) -> IMOSAdapter | None:
        adapter = self._adapters.get(name)
        if adapter is not None:
            return adapter
        return self._resolve_legacy_alias(name)

    def get_by_type(self, adapter_type: str) -> list[IMOSAdapter]:
        return [adapter for adapter in self._adapters.values() if adapter.adapter_type == adapter_type]

    def get_all(self) -> list[IMOSAdapter]:
        return list(self._adapters.values())

    async def health_check_all(self) -> dict[str, bool]:
        results = await self._gather_health_checks()
        return {name: status for name, status in results}

    async def _gather_health_checks(self) -> list[tuple[str, bool]]:
        import asyncio

        async def check(adapter: IMOSAdapter) -> tuple[str, bool]:
            try:
                return adapter.name, await adapter.health_check()
            except Exception:
                return adapter.name, False

        return await asyncio.gather(*(check(adapter) for adapter in self._adapters.values()))

    def get_capable_adapters(self, capability: str) -> list[IMOSAdapter]:
        return [adapter for adapter in self._adapters.values() if capability in adapter.capabilities]

    async def auto_discover(self) -> list[IMOSAdapter]:
        discovered: list[IMOSAdapter] = []
        seen_names: set[str] = set()
        for entry in list_configured_adapters():
            adapter = await self._instantiate_adapter(entry)
            if adapter is None:
                continue
            seen_names.add(adapter.name)
            if entry.get("auto_connect", True):
                try:
                    await adapter.connect()
                except Exception:
                    adapter.status = "error"
            self.register(adapter)
            discovered.append(adapter)
        for entry in self._builtin_adapters():
            if entry["name"] in seen_names or entry["name"] in self._adapters:
                continue
            adapter = await self._instantiate_adapter(entry)
            if adapter is None:
                continue
            if entry.get("auto_connect", True):
                try:
                    await adapter.connect()
                except Exception:
                    adapter.status = "error"
            self.register(adapter)
            discovered.append(adapter)
        return discovered

    async def _instantiate_adapter(self, config: dict[str, Any]) -> IMOSAdapter | None:
        module_path = config.get("module")
        class_name = config.get("class_name")
        if not module_path:
            adapter_type = config.get("adapter_type", "")
            provider = config.get("provider", config.get("kind", config.get("name", "")))
            normalized = str(provider).replace("-", "_").replace(" ", "_").lower()
            module_path = self._default_module_path(adapter_type, normalized)
            class_name = class_name or self._default_class_name(normalized)
        if not module_path or not class_name:
            return None

        module = importlib.import_module(module_path)
        cls = getattr(module, class_name, None)
        if cls is None:
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, IMOSAdapter) and obj is not IMOSAdapter:
                    cls = obj
                    break
        if cls is None:
            return None

        adapter_config = dict(config)
        adapter_config.update(get_adapter_config(config["name"]))
        adapter = cls(name=config["name"], config=adapter_config)
        if not isinstance(adapter, IMOSAdapter):
            raise TypeError(f"{class_name} is not an IMOSAdapter")
        return adapter

    def _default_module_path(self, adapter_type: str, normalized: str) -> str | None:
        mapping = {
            "model": f"imos.adapters.models.{normalized}_adapter",
            "ide": f"imos.adapters.ides.{normalized}_adapter",
            "messaging": f"imos.adapters.messaging.{normalized}_adapter",
            "meeting": f"imos.adapters.meetings.{normalized}_adapter",
            "payment": f"imos.adapters.payments.{normalized}_adapter",
            "webapp": f"imos.adapters.webapps.{normalized}_adapter",
            "vcs": f"imos.adapters.vcs.{normalized}_adapter",
            "os": f"imos.adapters.os.{normalized}_adapter",
            "browser": f"imos.adapters.webapps.{normalized}_adapter",
            "tool": f"imos.adapters.os.{normalized}_adapter",
        }
        return mapping.get(adapter_type)

    def _default_class_name(self, normalized: str) -> str:
        return "".join(part.capitalize() for part in normalized.split("_")) + "Adapter"

    def available_catalog(self) -> list[dict[str, str]]:
        root = Path(__file__).resolve().parent / "adapters"
        sections = {
            "models": "model",
            "ides": "ide",
            "messaging": "messaging",
            "meetings": "meeting",
            "payments": "payment",
            "webapps": "webapp",
            "vcs": "vcs",
            "os": "os",
        }
        items: list[dict[str, str]] = []
        for folder, adapter_type in sections.items():
            base = root / folder
            if not base.exists():
                continue
            for path in sorted(base.glob("*_adapter.py")):
                provider = path.stem.removesuffix("_adapter")
                items.append(
                    {
                        "name": provider,
                        "adapter_type": adapter_type,
                        "module": f"imos.adapters.{folder}.{path.stem}",
                    }
                )
        return items

    def _resolve_legacy_alias(self, name: str) -> IMOSAdapter | None:
        normalized = self._canonical_name(name)
        if not normalized:
            return None

        for key, adapter in self._adapters.items():
            if self._canonical_name(key) == normalized:
                return adapter

        models = self.get_by_type("model")
        if normalized == self._canonical_name("default_model") and models:
            return self._adapters.get("default_model") or models[0]

        for adapter in models:
            provider = str(getattr(adapter, "provider_name", "") or adapter.config.get("provider", "")).strip().lower()
            model = str(adapter.config.get("model", "") or getattr(adapter, "default_model", "")).strip().lower()
            aliases = {
                self._canonical_name(adapter.name),
                self._canonical_name(provider),
                self._canonical_name(f"{provider}_{model}") if provider and model else "",
                self._canonical_name(f"{provider}-{model}") if provider and model else "",
            }
            if normalized in aliases:
                return adapter
        return None

    def _canonical_name(self, value: str) -> str:
        text = str(value).strip().lower()
        text = re.sub(r"[^a-z0-9]+", "_", text)
        return text.strip("_")

    def _builtin_adapters(self) -> list[dict[str, Any]]:
        adapters = [
            {
                "name": "local_os",
                "adapter_type": "os",
                "provider": "os_control",
                "module": "imos.adapters.os.os_control_adapter",
                "class_name": "OsControlAdapter",
            },
            {
                "name": "local_ide",
                "adapter_type": "ide",
                "provider": "generic_ide",
                "module": "imos.adapters.ides.generic_ide_adapter",
                "class_name": "GenericIdeAdapter",
            },
            {
                "name": "local_browser",
                "adapter_type": "webapp",
                "provider": "browser",
                "module": "imos.adapters.webapps.browser_adapter",
                "class_name": "BrowserAdapter",
                "HEADLESS": True,
                "auto_connect": False,
            },
        ]
        try:
            from config.config import get_model_config

            model_cfg = get_model_config()
            provider = str(model_cfg.get("provider", "")).strip().lower()
            api_key = str(model_cfg.get("api_key", "")).strip()
            if provider and (api_key or provider in {"ollama", "lmstudio"}):
                adapters.insert(
                    0,
                    {
                        "name": "default_model",
                        "adapter_type": "model",
                        "provider": provider,
                        "model": model_cfg.get("model"),
                        "api_key": api_key,
                        "base_url": model_cfg.get("base_url"),
                        "max_tokens": model_cfg.get("max_tokens"),
                        "temperature": model_cfg.get("temperature"),
                    },
                )
        except Exception:
            pass
        return adapters
