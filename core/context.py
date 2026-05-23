import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4


class ContextManager:
    def __init__(self, session_id: str | None = None) -> None:
        self.base_dir = Path.home() / ".imos" / "sessions"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or str(uuid4())
        self.path = self.base_dir / f"{self.session_id}.json"
        self.data = self._load_or_create()

    def _default_data(self) -> dict:
        return {
            "session_id": self.session_id,
            "created_at": datetime.now().isoformat(),
            "provider_history": [],
            "messages": [],
            "summary": "",
            "token_estimate": 0,
        }

    def _coerce_session_data(self, raw_data) -> dict | None:
        if isinstance(raw_data, dict):
            data = dict(raw_data)
            data.setdefault("session_id", self.session_id)
            data.setdefault("created_at", datetime.now().isoformat())
            data.setdefault("provider_history", [])
            data.setdefault("messages", [])
            data.setdefault("summary", "")
            data.setdefault("token_estimate", 0)
            return data
        if isinstance(raw_data, list):
            # Older or malformed files sometimes contain only the message list.
            data = self._default_data()
            data["messages"] = raw_data
            return data
        return None

    def _load_or_create(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as file_handle:
                    raw_data = json.load(file_handle)
                data = self._coerce_session_data(raw_data)
                if data is not None:
                    return data
            except Exception as error:
                print(f"Warning: failed to read session file: {error}")
        data = self._default_data()
        self.data = data
        self._save()
        return data

    def _save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as file_handle:
                json.dump(self.data, file_handle, indent=2, ensure_ascii=False)
        except Exception as error:
            print(f"Warning: failed to write session file: {error}")

    def add_message(self, role, content, provider, model) -> None:
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        self.data.setdefault("messages", []).append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "provider": provider,
                "model": model,
            }
        )
        self.data["token_estimate"] = int(self.data.get("token_estimate", 0) + len(content.split()) * 1.3)
        history = self.data.setdefault("provider_history", [])
        if history:
            history[-1]["message_count"] = history[-1].get("message_count", 0) + 1
        self._save()

    def switch_provider(self, new_provider, new_model) -> None:
        history = self.data.setdefault("provider_history", [])
        if history and history[-1].get("ended_at") is None:
            history[-1]["ended_at"] = datetime.now().isoformat()
        history.append(
            {
                "provider": new_provider,
                "model": new_model,
                "started_at": datetime.now().isoformat(),
                "ended_at": None,
                "message_count": 0,
            }
        )
        self._save()

    def export_for_provider(self, target_provider) -> list[dict]:
        history = self.data.get("provider_history", [])
        original_provider = history[0]["provider"] if history else "unknown"
        bridge = {
            "role": "system",
            "content": (
                f"You are continuing a conversation that was started on {original_provider}. "
                f"The user has switched to {target_provider} due to limits or preference. "
                "Full conversation history follows. Continue naturally from where it left off. "
                "Do not mention the provider switch unless the user asks."
            ),
        }
        if self.data.get("summary"):
            bridge["content"] += f"\n\nConversation summary:\n{self.data['summary']}"

        exported = [bridge]
        for message in self.data.get("messages", []):
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "tool_result":
                exported.append({"role": "assistant", "content": f"[Tool result] {content}"})
            else:
                exported.append({"role": role, "content": content})
        return exported

    def generate_summary(self, get_response_fn) -> str:
        recent_messages = self.data.get("messages", [])[-20:]
        messages = []
        for message in recent_messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "tool_result":
                role = "assistant"
                content = f"[Tool result] {content}"
            messages.append({"role": role, "content": content})
        prompt = (
            "Summarize this conversation in 3-5 sentences covering: what was discussed,\n"
            "what was built or decided, and what the user is trying to accomplish.\n"
            "Be factual and dense. No filler."
        )
        summary = get_response_fn(messages=messages, system=prompt)
        self.data["summary"] = summary.strip()
        self._save()
        return self.data["summary"]

    def get_stats(self) -> dict:
        created_at = datetime.fromisoformat(self.data["created_at"])
        duration_minutes = max(0, int((datetime.now() - created_at).total_seconds() // 60))
        providers_used = [entry.get("provider", "") for entry in self.data.get("provider_history", [])]
        return {
            "session_id": self.data["session_id"],
            "message_count": len(self.data.get("messages", [])),
            "token_estimate": self.data.get("token_estimate", 0),
            "provider_count": len(providers_used),
            "providers_used": providers_used,
            "duration_minutes": duration_minutes,
            "summary": self.data.get("summary", ""),
            "created_at": self.data.get("created_at", ""),
        }

    @staticmethod
    def list_all() -> list[dict]:
        sessions_dir = Path.home() / ".imos" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        sessions = []
        for path in sessions_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as file_handle:
                    raw_data = json.load(file_handle)
                if isinstance(raw_data, dict):
                    data = raw_data
                elif isinstance(raw_data, list):
                    data = {
                        "session_id": path.stem,
                        "created_at": "",
                        "messages": raw_data,
                        "summary": "",
                    }
                else:
                    raise TypeError(f"unsupported session payload type: {type(raw_data).__name__}")
                sessions.append(
                    {
                        "session_id": data.get("session_id", path.stem),
                        "created_at": data.get("created_at", ""),
                        "message_count": len(data.get("messages", [])),
                        "summary_preview": str(data.get("summary", ""))[:80],
                    }
                )
            except Exception as error:
                print(f"Warning: failed to read session listing entry: {error}")
        sessions.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return sessions

    def export_markdown(self, path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        providers = "  ".join(
            f"{item.get('provider', '')} / {item.get('model', '')}" for item in self.data.get("provider_history", [])
        )
        lines = [
            f"# IMOS Session {self.data['session_id']}",
            f"**Started:** {self.data['created_at']}",
            f"**Providers:** {providers}",
            "",
        ]
        for message in self.data.get("messages", []):
            role = message.get("role", "user")
            timestamp = message.get("timestamp", "")
            content = message.get("content", "")
            provider = message.get("provider", "")
            model = message.get("model", "")
            if role == "user":
                lines.extend([f"### User    {timestamp}", content, ""])
            elif role == "assistant":
                lines.extend([f"### Assistant ({provider} / {model})    {timestamp}", content, ""])
            else:
                lines.extend([f"### Tool Result ({provider} / {model})    {timestamp}", content, ""])
        try:
            with open(destination, "w", encoding="utf-8") as file_handle:
                file_handle.write("\n".join(lines))
        except Exception as error:
            print(f"Warning: failed to export session markdown: {error}")

    @staticmethod
    def delete(session_id) -> None:
        sessions_dir = Path.home() / ".imos" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        for path in sessions_dir.glob("*.json"):
            try:
                if path.stem == session_id or path.stem.startswith(session_id):
                    path.unlink()
                    return
            except Exception as error:
                print(f"Warning: failed to delete session file: {error}")
