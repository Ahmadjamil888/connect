from __future__ import annotations

from typing import Any

from imos.adapters.models.common import AsyncModelAdapter


class GroqAdapter(AsyncModelAdapter):
    supported_models = [
        "llama-3.1-8b-instant",
        "openai/gpt-oss-20b",
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
    ]

    def __init__(self, name: str = "groq", config: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, provider_name="groq", config=config, default_model="llama-3.1-8b-instant")
        self.client = None

    async def connect(self) -> bool:
        try:
            from groq import AsyncGroq
        except ModuleNotFoundError:
            self.status = "error"
            return False
        self.client = AsyncGroq(api_key=(self.config or {}).get("GROQ_API_KEY") or (self.config or {}).get("api_key"))
        return await self.health_check()

    async def health_check(self) -> bool:
        if self.client is None:
            return False
        try:
            await self.client.models.list()
            self.status = "connected"
            return True
        except Exception:
            self.status = "error"
            return False

    async def _perform_request(self, task, stream: bool, callback):
        if self.client is None and not await self.connect():
            raise RuntimeError("Groq client unavailable")

        last_error: Exception | None = None
        for model in self._candidate_models(task):
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "system", "content": self._system_prompt(task)}] if self._system_prompt(task) else [],
                    "temperature": self._temperature(task),
                    "max_tokens": self._max_tokens(task),
                }
                payload["messages"].append({"role": "user", "content": task.prompt})
                if stream:
                    response = await self._retry(self.client.chat.completions.create, **payload, stream=True)
                    chunks: list[str] = []
                    async for chunk in response:
                        token = getattr(chunk.choices[0].delta, "content", "") if chunk.choices else ""
                        if token:
                            chunks.append(token)
                            await self._invoke_callback(callback, token)
                    return {"output": "".join(chunks), "metadata": self._usage() | {"model": model}}
                response = await self._retry(self.client.chat.completions.create, **payload)
                usage = getattr(response, "usage", None)
                return {
                    "output": response.choices[0].message.content if response.choices else "",
                    "metadata": self._usage(
                        prompt_tokens=int(getattr(usage, "prompt_tokens", 0)),
                        completion_tokens=int(getattr(usage, "completion_tokens", 0)),
                        total_tokens=int(getattr(usage, "total_tokens", 0)),
                    )
                    | {"model": model},
                }
            except Exception as exc:
                last_error = exc
                if not self._should_try_fallback(exc):
                    raise
        raise RuntimeError(str(last_error) if last_error else "Groq request failed")

    def _candidate_models(self, task) -> list[str]:
        requested = self._selected_model(task).strip()
        aliases = {
            "llama-3.3-70b": "llama-3.3-70b-versatile",
            "llama-3.1-8b": "llama-3.1-8b-instant",
            "mixtral-8x7b": "mixtral-8x7b-32768",
            "gemma2-9b": "gemma2-9b-it",
        }
        primary = aliases.get(requested, requested)
        ordered = [primary] if primary else []
        for model in self.supported_models:
            if model not in ordered:
                ordered.append(model)
        return ordered

    def _should_try_fallback(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return any(token in message for token in ["rate limit", "quota", "429", "capacity", "depleted", "tokens per day"])
