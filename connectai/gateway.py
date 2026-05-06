from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict

from config.config import get_model_config, get_provider_defaults
from core import model_manager

from connectai.channels import MessageEnvelope
from connectai.command_router import CommandResult


class ConnectAIGateway:
    def __init__(self, runtime, session_manager, memory_store, command_router, imos_orchestrator=None):
        self.runtime = runtime
        self.session_manager = session_manager
        self.memory_store = memory_store
        self.command_router = command_router
        self.imos_orchestrator = imos_orchestrator
        self._current_process = None

    def cancel_current(self):
        try:
            if self._current_process:
                self._current_process.kill()
                self._current_process = None
        except Exception:
            pass

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

    def _prefer_verified_runtime(self, text: str) -> bool:
        lowered = (text or "").strip().lower()
        build_terms = ("build", "create", "make", "scaffold")
        website_terms = (
            "website",
            "web app",
            "webapp",
            "landing page",
            "homepage",
            "portfolio site",
            "professional website",
            "professional site",
        )
        return any(term in lowered for term in build_terms) and any(term in lowered for term in website_terms)

    def _normalize_model_config(self, model_config: dict) -> dict:
        resolved = dict(model_config or {})
        provider = str(resolved.get("type") or resolved.get("provider") or "").strip().lower()
        model_name = str(resolved.get("model", "") or "").strip()
        if not provider and model_name:
            provider = model_manager.infer_provider_type(model_name)
        if not provider and resolved.get("no_provider_configured"):
            provider = "unconfigured"
        if not provider and model_name:
            raise model_manager.ProviderConfigurationError(model_manager.unknown_provider_message(model_name))
        if provider:
            resolved["provider"] = provider
            resolved["type"] = provider
        return resolved

    def _routed_model_config(self, prompt: str, model_config: dict) -> tuple[dict, str]:
        base_config = self._normalize_model_config(get_model_config())
        if base_config.get("no_provider_configured"):
            return base_config, "default"
        routing_rules = getattr(self.command_router, "routing_rules", None)
        if routing_rules is None:
            return dict(base_config), "default"
        fallback_provider = str(base_config.get("type") or base_config.get("provider") or "").strip().lower()
        task_type, provider = routing_rules.resolve_provider(prompt, fallback_provider)
        resolved = dict(base_config)
        current_provider = str(resolved.get("type") or resolved.get("provider", "")).strip().lower()
        if provider and provider != current_provider:
            defaults = get_provider_defaults(provider)
            merged = dict(defaults)
            merged["provider"] = provider
            merged["type"] = defaults.get("type", provider)
            resolved = self._normalize_model_config(merged)
        return resolved, task_type

    def handle_with_meta(self, envelope: MessageEnvelope, workspace: str, model_config: dict, on_text_delta=None) -> Dict[str, object]:
        command_result = self.command_router.route(envelope.text)
        if command_result.handled:
            return {
                "output": command_result.output,
                "should_exit": command_result.should_exit,
                "handled_command": True,
                "usage": {},
                "updated_model_config": command_result.updated_model_config,
                "updated_workspace": command_result.updated_workspace,
            }

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
        active_model_config, task_type = self._routed_model_config(envelope.text, model_config)
        if active_model_config.get("no_provider_configured"):
            return {
                "output": "No AI provider configured. Run /model add to set one up.",
                "session_id": session.session_id,
                "usage": {},
            }
        if hasattr(self.session_manager, "set_active") and hasattr(session, "name"):
            self.session_manager.set_active(session.name)
        if hasattr(self.session_manager, "set_provider_and_routing"):
            self.session_manager.set_provider_and_routing(session.session_id, str(active_model_config.get("provider", "")), getattr(self.command_router, "routing_rules", None).list_rules() if getattr(self.command_router, "routing_rules", None) is not None else {})
        self.session_manager.append_message(session, "user", envelope.text, envelope.metadata)
        if self._prefer_verified_runtime(envelope.text):
            response = self.runtime.run(
                user_text=envelope.text,
                session_history=self.session_manager.history(session, limit=20),
                session_id=session.session_id,
                workspace=workspace,
                model_config=active_model_config,
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
            usage = response.get("usage", {}) or {}
            if hasattr(self.session_manager, "add_token_usage"):
                self.session_manager.add_token_usage(
                    session.session_id,
                    str(active_model_config.get("provider", "")),
                    int(usage.get("input_tokens", 0) or 0),
                    int(usage.get("output_tokens", 0) or 0),
                )
            if hasattr(self.session_manager, "record_memory_snapshot") and hasattr(self.memory_store, "recent_entries"):
                self.session_manager.record_memory_snapshot(session.session_id, self.memory_store.recent_entries(20), self.memory_store.recent_entries(100))
            return {"output": response_text, "session_id": session.session_id, "usage": response.get("usage", {})}
        if self.imos_orchestrator is not None:
            try:
                result = asyncio.run(
                    self.imos_orchestrator.run(
                        envelope.text,
                        context={
                            "workspace": workspace,
                            "session_key": envelope.session_key,
                            "channel": envelope.channel,
                            "user_id": envelope.user_id,
                            "preferred_provider": active_model_config.get("provider"),
                            "preferred_model": active_model_config.get("model"),
                            "task_type": task_type,
                        },
                    )
                )
                response_text = self._dedupe_response(str(result.final_response))
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
                        metadata={
                            "channel": envelope.channel,
                            "adapters": result.adapters_used,
                            "duration_ms": result.duration_ms,
                        },
                    )
                if hasattr(self.session_manager, "record_memory_snapshot") and hasattr(self.memory_store, "recent_entries"):
                    self.session_manager.record_memory_snapshot(session.session_id, self.memory_store.recent_entries(20), self.memory_store.recent_entries(100))
                return {
                    "output": response_text,
                    "session_id": session.session_id,
                    "usage": {"adapters_used": result.adapters_used, "duration_ms": result.duration_ms},
                }
            except Exception as exc:
                return {"output": f"IMOS runtime error: {exc}", "session_id": session.session_id, "usage": {}}

        response = self.runtime.run(
            user_text=envelope.text,
            session_history=self.session_manager.history(session, limit=20),
            session_id=session.session_id,
            workspace=workspace,
            model_config=active_model_config,
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
        usage = response.get("usage", {}) or {}
        if hasattr(self.session_manager, "add_token_usage"):
            self.session_manager.add_token_usage(
                session.session_id,
                str(active_model_config.get("provider", "")),
                int(usage.get("input_tokens", 0) or 0),
                int(usage.get("output_tokens", 0) or 0),
            )
        if hasattr(self.session_manager, "record_memory_snapshot") and hasattr(self.memory_store, "recent_entries"):
            self.session_manager.record_memory_snapshot(session.session_id, self.memory_store.recent_entries(20), self.memory_store.recent_entries(100))
        return {"output": response_text, "session_id": session.session_id, "usage": response.get("usage", {})}


class Gateway:
    def simple_completion(self, prompt: str) -> str:
        provider = model_manager.get_default()
        if not provider or provider.get("no_provider_configured") or provider.get("type") in {"", "unassigned", "unconfigured"}:
            raise RuntimeError("No provider configured")
        ptype = str(provider.get("type", "")).strip().lower()
        if ptype == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=provider["api_key"])
            message = client.messages.create(
                model=provider.get("model", "claude-sonnet-4-5"),
                max_tokens=32,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(block.text for block in message.content if getattr(block, "type", "") == "text").strip()
        if ptype in {"openai", "groq", "openrouter", "ollama", "lmstudio", "custom", "together", "mistral", "cohere"}:
            from openai import OpenAI

            base_url = provider.get("base_url") or get_provider_defaults(ptype).get("base_url", "")
            client = OpenAI(api_key=provider.get("api_key", ""), base_url=base_url or None)
            response = client.chat.completions.create(
                model=provider.get("model", ""),
                max_tokens=32,
                messages=[{"role": "user", "content": prompt}],
            )
            return str(response.choices[0].message.content or "").strip()
        if ptype == "gemini":
            import google.generativeai as genai

            genai.configure(api_key=provider["api_key"])
            model = genai.GenerativeModel(provider.get("model", "gemini-2.0-flash"))
            response = model.generate_content(prompt)
            return str(getattr(response, "text", "") or "").strip()
        raise RuntimeError(f"Unsupported provider type: {ptype}")
