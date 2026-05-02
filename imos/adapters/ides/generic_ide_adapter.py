from __future__ import annotations

from typing import Any

from imos.adapters.ides.common import BaseIDEAdapter


class GenericIdeAdapter(BaseIDEAdapter):
    def __init__(self, name: str = "generic_ide", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
