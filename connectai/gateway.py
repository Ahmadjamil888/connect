from __future__ import annotations

from pathlib import Path
from typing import Dict

from connectai.channels import MessageEnvelope
from connectai.command_router import CommandResult


class ConnectAIGateway:
    def __init__(self, runtime, session_manager, memory_store, command_router):
        self.runtime = runtime
        self.session_manager = session_manager
        self.memory_store = memory_store
        self.command_router = command_router

    def _dedupe_response(self, text: str) -> str:
        value = (text or "").strip()
        if not value:
            return text
        lines = [line.rstrip() for line in value.splitlines()]
        if len(lines) % 2 == 0:
            half = len(lines) // 2
            if lines[:half] == lines[half:]:
                return "\n".join(lines[:half]).strip()
        midpoint = len(value) // 2
        if len(value) % 2 == 0 and value[:midpoint].strip() == value[midpoint:].strip():
            return value[:midpoint].strip()
        return text

    def handle(self, envelope: MessageEnvelope, workspace: str, model_config: dict) -> CommandResult:
        command_result = self.command_router.route(envelope.text)
        if command_result.handled:
            return command_result
        result = self.handle_with_meta(envelope, workspace, model_config)
        return CommandResult(handled=True, output=str(result.get("output", "")))

    def handle_with_meta(self, envelope: MessageEnvelope, workspace: str, model_config: dict, on_text_delta=None) -> Dict[str, object]:
        command_result = self.command_router.route(envelope.text)
        if command_result.handled:
            return {"output": command_result.output, "should_exit": command_result.should_exit, "handled_command": True, "usage": {}}

        lowered = envelope.text.strip().lower()
        if lowered in {
            "clean my pc",
            "clean pc",
            "clean this pc",
            "clean my computer",
            "clean computer",
        }:
            response = self.runtime.run(
                user_text="Clean this PC by removing temp files. Use the clean_pc skill with confirm=true, then summarize the result.",
                session_history=[],
                session_id="direct-clean",
                workspace=workspace,
                model_config=model_config,
                on_text_delta=on_text_delta,
                return_meta=True,
            )
            return {"output": response.get("text", ""), "session_id": "direct-clean", "usage": response.get("usage", {})}

        session = self.session_manager.get_or_create(
            session_key=envelope.session_key,
            channel=envelope.channel,
            user_id=envelope.user_id,
        )
        self.session_manager.append_message(session, "user", envelope.text, envelope.metadata)
        response = self.runtime.run(
            user_text=envelope.text,
            session_history=self.session_manager.history(session, limit=20),
            session_id=session.session_id,
            workspace=workspace,
            model_config=model_config,
            on_text_delta=on_text_delta,
            return_meta=True,
        )
        response_text = self._dedupe_response(str(response.get("text", "")))
        self.session_manager.append_message(session, "assistant", response_text)
        self.memory_store.remember(
            content=envelope.text,
            kind="user",
            session_id=session.session_id,
            metadata={"channel": envelope.channel, "user_id": envelope.user_id},
        )
        if response_text:
            self.memory_store.remember(
                content=response_text[:500],
                kind="assistant",
                session_id=session.session_id,
                metadata={"channel": envelope.channel},
            )
        return {"output": response_text, "session_id": session.session_id, "usage": response.get("usage", {})}
