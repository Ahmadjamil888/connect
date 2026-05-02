from __future__ import annotations

import asyncio
from typing import Any

from imos.adapters.messaging.common import BaseMessagingAdapter


class IrcAdapter(BaseMessagingAdapter):
    def __init__(self, name: str = "irc", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, config=config)
        self.server = (config or {}).get("IRC_SERVER", "")
        self.port = int((config or {}).get("IRC_PORT", 6667))
        self.nick = (config or {}).get("IRC_NICK", "imos")
        self.channel = (config or {}).get("IRC_CHANNEL", "#imos")

    async def health_check(self) -> bool:
        return bool(self.server and self.nick)

    async def send_message(self, message: str, channel: str | None = None) -> Any:
        reader, writer = await asyncio.open_connection(self.server, self.port)
        target = channel or self.channel
        writer.write(f"NICK {self.nick}\r\n".encode())
        writer.write(f"USER {self.nick} 0 * :IMOS Bot\r\n".encode())
        writer.write(f"JOIN {target}\r\n".encode())
        writer.write(f"PRIVMSG {target} :{message}\r\n".encode())
        writer.write(b"QUIT\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return {"status": "sent", "channel": target}
