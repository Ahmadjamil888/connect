from __future__ import annotations

import importlib
import inspect
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
        return self._adapters.get(name)

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
        for entry in list_configured_adapters():
            adapter = await self._instantiate_adapter(entry)
            if adapter is None:
                continue
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

        adapter_config = get_adapter_config(config["name"])
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
