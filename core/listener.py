from __future__ import annotations

import io
import json
import os
import threading
import time
import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class ListenerSettings:
    active: bool = False
    persist: bool = False
    wake_word: str = "IMOS"


class VoiceListenerService:
    def __init__(
        self,
        state_root: Path,
        *,
        callback: Callable[[str], Any] | None = None,
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
        self._thread_lock = threading.Lock()
        self._model_error = ""
        self._model_retry_at = 0.0
        self._last_error_log = ""
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

    def _load(self) -> ListenerSettings:
        if not self.path.exists():
            return ListenerSettings()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return ListenerSettings(
                active=bool(payload.get("active", False)),
                persist=bool(payload.get("persist", False)),
                wake_word=str(payload.get("wake_word", "IMOS") or "IMOS"),
            )
        except Exception:
            return ListenerSettings()

    def _save(self, settings: ListenerSettings) -> None:
        self.path.write_text(json.dumps(settings.__dict__, indent=2), encoding="utf-8")

    def _deps(self) -> dict[str, bool]:
        names = {
            "faster_whisper": False,
            "sounddevice": False,
            "numpy": False,
            "scipy": False,
            "speech_recognition": False,
        }
        for module in list(names):
            try:
                __import__(module)
                names[module] = True
            except Exception:
                names[module] = False
        return names

    def _model_root(self) -> Path:
        root = self.state_root / "whisper_models"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _ensure_model(self, model_size: str):
        if time.time() < self._model_retry_at:
            raise RuntimeError(self._model_error or "Whisper model unavailable.")
        from faster_whisper import WhisperModel

        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                if model_size == "tiny":
                    if self._tiny_model is None:
                        self._tiny_model = WhisperModel(
                            "tiny",
                            device="cpu",
                            compute_type="int8",
                            download_root=str(self._model_root()),
                        )
                    self._model_error = ""
                    return self._tiny_model
                if self._base_model is None:
                    self._base_model = WhisperModel(
                        "base",
                        device="cpu",
                        compute_type="int8",
                        download_root=str(self._model_root()),
                    )
                self._model_error = ""
                return self._base_model
        except Exception as exc:
            self._model_error = str(exc)
            self._model_retry_at = time.time() + 300
            raise

    def _transcribe_audio(self, wav_bytes: bytes, *, model_size: str) -> str:
        import tempfile

        try:
            model = self._ensure_model(model_size)
        except Exception:
            if model_size == "base":
                model = self._ensure_model("tiny")
            else:
                raise
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            handle.write(wav_bytes)
            path = Path(handle.name)
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                segments, _ = model.transcribe(str(path), beam_size=1)
            return " ".join(segment.text.strip() for segment in segments if segment.text).strip()
        finally:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass

    def _speak(self, text: str) -> None:
        if self.speaker is None:
            return
        try:
            self.speaker.speak(text)
        except Exception:
            pass

    def _listener_paused(self) -> bool:
        return bool(self.speaker is not None and getattr(self.speaker, "listener_paused", lambda: False)())

    def start(self, *, persist: bool = False, daemon: bool = True) -> dict[str, Any]:
        settings = self._load()
        settings.active = True
        settings.persist = persist
        self._save(settings)
        with self._thread_lock:
            if self._thread is None or not self._thread.is_alive():
                self._stop.clear()
                self._thread = threading.Thread(target=self._loop, daemon=daemon, name="imos-listener")
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
        settings.wake_word = phrase.strip() or "IMOS"
        self._save(settings)
        return self.status()

    def status(self) -> dict[str, Any]:
        settings = self._load()
        deps = self._deps()
        required = ["faster_whisper", "sounddevice", "numpy", "scipy", "speech_recognition"]
        missing = [name for name in required if not deps.get(name)]
        return {
            "active": settings.active and bool(self._thread and self._thread.is_alive()) and not missing,
            "configured_active": settings.active,
            "persist": settings.persist,
            "deps": deps,
            "voice_ok": not missing,
            "missing": missing,
            "model_error": self._model_error,
            "wake_word": settings.wake_word,
            "wake_model": "tiny",
            "command_model": "base" if not self._model_error else "tiny-fallback",
            "mode": "always-on",
        }

    def maybe_start_from_config(self, cfg: dict[str, Any]) -> None:
        listen_cfg = cfg.get("listen", {})
        if isinstance(listen_cfg, dict) and listen_cfg.get("enabled"):
            self.start(persist=bool(listen_cfg.get("persist", False)), daemon=True)

    def _log(self, kind: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        if self.audit_logger is not None:
            self.audit_logger.append(kind, message, metadata or {})
        if self.event_bus is not None:
            self.event_bus.publish(kind, message=message, **(metadata or {}))

    def _loop(self) -> None:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.7
        recognizer.non_speaking_duration = 0.35
        microphone = sr.Microphone(sample_rate=16000)
        with microphone as source:
            try:
                recognizer.adjust_for_ambient_noise(source, duration=0.2)
            except Exception:
                pass
            while not self._stop.is_set():
                settings = self._load()
                if not settings.active:
                    break
                if self.status()["missing"]:
                    time.sleep(1.0)
                    continue
                if self._listener_paused():
                    time.sleep(0.1)
                    continue
                try:
                    audio = recognizer.listen(source, timeout=1, phrase_time_limit=8)
                except sr.WaitTimeoutError:
                    continue
                except Exception as exc:
                    self._log("listener_error", str(exc))
                    time.sleep(0.5)
                    continue
                if self._listener_paused():
                    continue
                try:
                    wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
                    transcript = self._transcribe_audio(wav_bytes, model_size="base").strip()
                    if not transcript:
                        continue
                    self._log("listener_command", transcript, {"mode": "always-on"})
                    if self.callback is not None:
                        self.callback(transcript)
                except Exception as exc:
                    message = str(exc)
                    if message != self._last_error_log:
                        self._log("listener_error", message)
                        self._last_error_log = message
                    time.sleep(0.5)
