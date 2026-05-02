from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.os.common import BaseOSAdapter


class SshAdapter(BaseOSAdapter):
    def __init__(self, name: str = "ssh", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config, capabilities=["execute", "stream", "upload", "download", "port_forward"])
        self.hosts = (config or {}).get("hosts", {})

    async def health_check(self) -> bool:
        return bool(self.hosts)

    async def execute(self, host_name: str, command: str) -> Any:
        import paramiko

        host = self.hosts[host_name]
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        await asyncio.to_thread(
            client.connect,
            host["host"],
            port=host.get("port", 22),
            username=host["username"],
            password=host.get("password"),
            key_filename=host.get("key_file"),
        )
        stdin, stdout, stderr = await asyncio.to_thread(client.exec_command, command)
        output = await asyncio.to_thread(stdout.read)
        errors = await asyncio.to_thread(stderr.read)
        client.close()
        return {"stdout": output.decode(), "stderr": errors.decode()}

    async def upload(self, host_name: str, local_path: str, remote_path: str) -> Any:
        import paramiko

        host = self.hosts[host_name]
        transport = paramiko.Transport((host["host"], host.get("port", 22)))
        await asyncio.to_thread(transport.connect, username=host["username"], password=host.get("password"))
        sftp = paramiko.SFTPClient.from_transport(transport)
        await asyncio.to_thread(sftp.put, local_path, remote_path)
        sftp.close()
        transport.close()
        return {"uploaded": local_path, "remote_path": remote_path}
