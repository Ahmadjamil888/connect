from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_VOICE_ID = "nova"


class VoiceManager:
    def __init__(self, state_root: Path):
        self.state_root = state_root
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.path = self.state_root / "voice.json"
        self.env_path = Path(__file__).resolve().parent.parent / ".env"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"muted": False, "voice_id": self._env("VOICE_VOICE_ID") or DEFAULT_VOICE_ID}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {"muted": False, "voice_id": self._env("VOICE_VOICE_ID") or DEFAULT_VOICE_ID}

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _env(self, key: str, default: str = "") -> str:
        value = os.getenv(key, "").strip()
        if value:
            return value
        if self.env_path.exists():
            for raw_line in self.env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                current_key, current_value = line.split("=", 1)
                if current_key.strip() == key:
                    return current_value.strip().strip('"').strip("'")
        return default

    def _write_env(self, key: str, value: str) -> None:
        data: dict[str, str] = {}
        if self.env_path.exists():
            for raw_line in self.env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                current_key, current_value = line.split("=", 1)
                data[current_key.strip()] = current_value.strip()
        data[key] = value
        os.environ[key] = value
        self.env_path.write_text(
            "\n".join(f"{name}={entry}" for name, entry in sorted(data.items())) + "\n",
            encoding="utf-8",
        )

    def _provider(self) -> str:
        return (self._env("VOICE_PROVIDER", "pyttsx3") or "pyttsx3").strip().lower()

    def _provider_label(self, provider: str, voice_id: str) -> str:
        if provider == "gemini-tts":
            return voice_id or "Kore"
        if provider == "openai-tts":
            return voice_id or DEFAULT_VOICE_ID
        return "local"

    def set_voice(self, voice_id: str) -> dict[str, Any]:
        state = self._load()
        state["voice_id"] = voice_id.strip() or DEFAULT_VOICE_ID
        self._save(state)
        self._write_env("VOICE_VOICE_ID", state["voice_id"])
        return self.status()

    def mute(self) -> dict[str, Any]:
        state = self._load()
        state["muted"] = True
        self._save(state)
        return self.status()

    def unmute(self) -> dict[str, Any]:
        state = self._load()
        state["muted"] = False
        self._save(state)
        return self.status()

    def status(self) -> dict[str, Any]:
        state = self._load()
        provider = self._provider()
        voice_id = str(state.get("voice_id") or self._env("VOICE_VOICE_ID") or DEFAULT_VOICE_ID)
        return {
            "muted": bool(state.get("muted", False)),
            "voice_id": voice_id,
            "provider": provider,
            "provider_label": self._provider_label(provider, voice_id),
        }

    def test_phrase(self) -> str:
        return "IMOS is ready"

    def speak(self, text: str) -> dict[str, Any]:
        state = self._load()
        if bool(state.get("muted", False)):
            return {"ok": False, "muted": True}
        provider = self._provider()
        voice_id = str(state.get("voice_id") or self._env("VOICE_VOICE_ID") or DEFAULT_VOICE_ID)
        try:
            if provider == "gemini-tts":
                api_key = self._env("VOICE_API_KEY")
                if api_key:
                    return self._speak_gemini(text, api_key=api_key, voice_id=voice_id)
            elif provider == "openai-tts":
                api_key = self._env("VOICE_API_KEY")
                if api_key:
                    return self._speak_openai(text, api_key=api_key, voice_id=voice_id)
        except Exception as exc:
            fallback = self.fallback_pyttsx3(text)
            fallback["error"] = str(exc)
            fallback["fallback_from"] = provider
            return fallback
        return self.fallback_pyttsx3(text)

    def _play_wav_bytes(self, audio_bytes: bytes) -> None:
        import sounddevice as sd
        from scipy.io import wavfile

        sample_rate, data = wavfile.read(io.BytesIO(audio_bytes))
        sd.play(data, sample_rate)
        sd.wait()

    def _speak_gemini(self, text: str, *, api_key: str, voice_id: str) -> dict[str, Any]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash-preview-tts",
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_id or "Kore"
                        )
                    )
                ),
            ),
        )
        audio_bytes = b""
        for candidate in getattr(response, "candidates", []) or []:
            for part in getattr(getattr(candidate, "content", None), "parts", []) or []:
                inline_data = getattr(part, "inline_data", None)
                if inline_data is not None:
                    audio_bytes = getattr(inline_data, "data", b"") or b""
                    break
            if audio_bytes:
                break
        if not audio_bytes:
            raise RuntimeError("Gemini TTS returned no audio.")
        self._play_wav_bytes(audio_bytes if isinstance(audio_bytes, bytes) else bytes(audio_bytes))
        return {"ok": True, "provider": "gemini-tts", "voice_id": voice_id or "Kore"}

    def _speak_openai(self, text: str, *, api_key: str, voice_id: str) -> dict[str, Any]:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice_id or DEFAULT_VOICE_ID,
            input=text,
            response_format="wav",
        )
        audio_bytes = b""
        if hasattr(response, "read"):
            audio_bytes = response.read()
        elif hasattr(response, "content"):
            audio_bytes = response.content
        if not audio_bytes:
            raise RuntimeError("OpenAI TTS returned no audio.")
        self._play_wav_bytes(audio_bytes)
        return {"ok": True, "provider": "openai-tts", "voice_id": voice_id or DEFAULT_VOICE_ID}

    def fallback_pyttsx3(self, text: str) -> dict[str, Any]:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            return {"ok": True, "provider": "pyttsx3", "voice_id": "local"}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "provider": "pyttsx3"}
