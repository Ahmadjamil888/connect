from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class MessageEnvelope:
    channel: str
    user_id: str
    text: str
    session_hint: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def session_key(self) -> str:
        if self.session_hint:
            return self.session_hint
        return f"{self.channel}:{self.user_id}"


class ChannelAdapter:
    name = "channel"

    def normalize(self, user_id: str, text: str, session_hint: str = "", **metadata: Any) -> MessageEnvelope:
        return MessageEnvelope(
            channel=self.name,
            user_id=user_id,
            text=text,
            session_hint=session_hint,
            metadata=metadata,
        )
