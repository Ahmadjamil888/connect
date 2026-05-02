from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.os.common import BaseOSAdapter


class DockerAdapter(BaseOSAdapter):
    def __init__(self, name: str = "docker", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["images", "containers", "volumes", "networks", "exec", "logs", "stats"])
        self.client = None

    async def connect(self) -> bool:
        try:
            import docker
        except ModuleNotFoundError:
            self.status = "error"
            return False
        self.client = docker.from_env()
        self.status = "connected"
        return True

    async def health_check(self) -> bool:
        return self.client is not None

    async def build_image(self, path: str, tag: str) -> Any:
        return await asyncio.to_thread(self.client.images.build, path=path, tag=tag)

    async def run_container(self, image: str, command: str | None = None, detach: bool = True, **kwargs) -> Any:
        container = await asyncio.to_thread(self.client.containers.run, image, command=command, detach=detach, **kwargs)
        return {"id": container.id, "name": container.name}

    async def stop_container(self, container_id: str) -> Any:
        container = self.client.containers.get(container_id)
        return await asyncio.to_thread(container.stop)

    async def remove_container(self, container_id: str) -> Any:
        container = self.client.containers.get(container_id)
        return await asyncio.to_thread(container.remove, force=True)
