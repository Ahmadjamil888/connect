from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


DEFAULT_WAKE_WORD = "IMOS"
DEFAULT_WAKE_PHRASES = ("imos", "hey imos", "hi imos", "yo imos")


@dataclass
class ListenerSettings:
    active: bool = False
    persist: bool = False
    wake_word: str = DEFAULT_WAKE_WORD
    wake_phrases: list[str] | None = None


class VoiceListenerService:
    def __init__(
        self,
        state_root: Path,
        *,
        callback: Callable[[str], str] | None = None,
        speaker=None,
        event_bus=None,
        audit_logger=None,
        chime_path: Path | None = None,
    ):
        self.state_root = state_root
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.path = self.state_root / "listener.json"
        self.callback = callback
        self.speaker = speaker
        self.event_bus = event_bus
        self.audit_logger = audit_logger
        self.chime_path = chime_path or (Path.cwd() / "audio" / "chime.wav")
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._tiny_model = None
        self._base_model = None

    def _load(self) -> ListenerSettings:
        if not self.path.exists():
            return ListenerSettings(wake_phrases=list(DEFAULT_WAKE_PHRASES))
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return ListenerSettings(
                active=bool(payload.get("active", False)),
                persist=bool(payload.get("persist", False)),
                wake_word=str(payload.get("wake_word", DEFAULT_WAKE_WORD) or DEFAULT_WAKE_WORD),
                wake_phrases=list(payload.get("wake_phrases") or DEFAULT_WAKE_PHRASES),
            )
        except Exception:
            return ListenerSettings(wake_phrases=list(DEFAULT_WAKE_PHRASES))

    def _save(self, settings: ListenerSettings) -> None:
        payload = dict(settings.__dict__)
        payload["wake_phrases"] = list(payload.get("wake_phrases") or DEFAULT_WAKE_PHRASES)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _deps(self) -> dict[str, bool]:
        names = {
            "faster_whisper": False,
            "sounddevice": False,
            "numpy": False,
            "scipy": False,
            "pyttsx3": False,
            "elevenlabs": False,
        }
        for module in list(names):
            try:
                __import__(module)
                names[module] = True
            except Exception:
                names[module] = False
        return names

    def _ensure_models(self):
        if self._tiny_model is not None and self._base_model is not None:
            return self._tiny_model, self._base_model
        from faster_whisper import WhisperModel

        if self._tiny_model is None:
            self._tiny_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        if self._base_model is None:
            self._base_model = WhisperModel("base", device="cpu", compute_type="int8")
        return self._tiny_model, self._base_model

    def _play_chime(self) -> None:
        try:
            if self.chime_path.exists():
                import winsound

                winsound.PlaySound(str(self.chime_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            pass

    def _speak(self, text: str) -> None:
        if self.speaker is None:
            return
        try:
            self.speaker.speak(text)
        except Exception:
            pass

    def _transcribe_chunk(self, audio, *, sample_rate: int, model_size: str) -> str:
        import numpy as np
        from scipy.io import wavfile
        import tempfile

        _, _ = self._ensure_models()
        model = self._tiny_model if model_size == "tiny" else self._base_model
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            wavfile.write(handle.name, sample_rate, (audio * 32767).astype(np.int16))
            path = handle.name
        try:
            segments, _ = model.transcribe(path, beam_size=1)
            return " ".join(segment.text.strip() for segment in segments if segment.text).strip()
        finally:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass

    def _record(self, seconds: int, sample_rate: int = 16000):
        import sounddevice as sd

        frames = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
        sd.wait()
        return frames.flatten(), sample_rate

    def start(self, *, persist: bool = False) -> dict[str, Any]:
        settings = self._load()
        settings.active = True
        settings.persist = persist
        settings.wake_phrases = list(settings.wake_phrases or DEFAULT_WAKE_PHRASES)
        self._save(settings)
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="imos-listener")
            self._thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        settings = self._load()
        settings.active = False
        settings.persist = False
        self._save(settings)
        self._stop.set()
        return self.status()

    def set_wake_word(self, phrase: str) -> dict[str, Any]:
        settings = self._load()
        clean = phrase.strip() or DEFAULT_WAKE_WORD
        settings.wake_word = clean
        settings.wake_phrases = list(dict.fromkeys([clean.lower(), *DEFAULT_WAKE_PHRASES]))
        self._save(settings)
        return self.status()

    def status(self) -> dict[str, Any]:
        settings = self._load()
        deps = self._deps()
        required = ["faster_whisper", "sounddevice", "numpy", "scipy"]
        missing = [name for name in required if not deps.get(name)]
        return {
            "active": settings.active and bool(self._thread and self._thread.is_alive()) and not missing,
            "configured_active": settings.active,
            "persist": settings.persist,
            "wake_word": settings.wake_word,
            "wake_phrases": list(settings.wake_phrases or DEFAULT_WAKE_PHRASES),
            "deps": deps,
            "voice_ok": not missing,
            "missing": missing,
            "wake_model": "tiny",
            "command_model": "base",
        }

    def maybe_start_from_config(self, cfg: dict[str, Any]) -> None:
        listen_cfg = cfg.get("listen", {})
        if isinstance(listen_cfg, dict) and listen_cfg.get("enabled"):
            if listen_cfg.get("wake_word"):
                self.set_wake_word(str(listen_cfg.get("wake_word")))
            self.start(persist=bool(listen_cfg.get("persist", False)))

    def _log(self, kind: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        if self.audit_logger is not None:
            self.audit_logger.append(kind, message, metadata or {})
        if self.event_bus is not None:
            self.event_bus.publish(kind, message=message, **(metadata or {}))

    def _loop(self) -> None:
        while not self._stop.is_set():
            settings = self._load()
            if not settings.active:
                break
            status = self.status()
            if status["missing"]:
                time.sleep(1.0)
                continue
            try:
                audio, sample_rate = self._record(1)
                transcript = self._transcribe_chunk(audio, sample_rate=sample_rate, model_size="tiny").lower()
                phrases = [phrase.lower() for phrase in (settings.wake_phrases or DEFAULT_WAKE_PHRASES)]
                if not any(phrase in transcript for phrase in phrases):
                    continue
                self._play_chime()
                self._speak("Ready.")
                self._log("listener_wake", transcript, {"wake_word": settings.wake_word})
                command_audio, command_rate = self._record(6)
                command = self._transcribe_chunk(command_audio, sample_rate=command_rate, model_size="base").strip()
                if not command:
                    self._speak("I didn't catch that.")
                    continue
                self._log("listener_command", command, {"wake_word": settings.wake_word})
                if self.callback is not None:
                    response = self.callback(command) or ""
                    if response:
                        short = response.strip().splitlines()[0][:180]
                        self._speak(short)
            except Exception as exc:
                self._log("listener_error", str(exc))
                time.sleep(1.0)
