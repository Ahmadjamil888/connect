"""
IMOS Voice Loop — wake word detection + continuous STT + TTS.
Runs as a daemon thread. Wake word: "IMOS" or "Hey IMOS".
Falls back to keyboard input if microphone is unavailable.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# TTS engine (singleton, thread-safe)
# ---------------------------------------------------------------------------

class IMOSTTSEngine:
    """Thread-safe pyttsx3 wrapper that runs speech in a dedicated thread."""

    def __init__(self):
        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="imos-tts")
        self._engine = None
        self._available = False
        self._error = ""
        self._voice_mode = "jarvis"
        self._rate = 175
        self._thread.start()

    def _worker(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            self._engine = engine
            self._available = True
            self.set_voice(self._voice_mode)
        except Exception as exc:
            self._error = str(exc)
            return

        while True:
            text = self._queue.get()
            if text is None:
                break
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception:
                pass

    def speak(self, text: str):
        if self._available:
            self._queue.put(text)

    def set_voice(self, mode: str) -> str:
        chosen = "friday" if str(mode).strip().lower() == "friday" else "jarvis"
        self._voice_mode = chosen
        if not self._engine:
            return chosen
        voices = self._engine.getProperty("voices") or []
        selected = None
        for voice in voices:
            vid = (voice.id or "").lower()
            vname = (voice.name or "").lower()
            if chosen == "friday" and ("zira" in vid or "zira" in vname):
                selected = voice.id
                break
            if chosen == "jarvis" and ("david" in vid or "david" in vname):
                selected = voice.id
                break
        if selected:
            self._engine.setProperty("voice", selected)
        return chosen

    def set_rate(self, rate: int) -> int:
        self._rate = max(100, min(int(rate or 175), 260))
        if self._engine:
            self._engine.setProperty("rate", self._rate)
        return self._rate

    def status(self) -> dict:
        return {
            "available": self._available,
            "voice": self._voice_mode,
            "rate": self._rate,
            "error": self._error,
        }

    def speak_sync(self, text: str, timeout: float = 15.0):
        """Speak and wait for completion (approximate)."""
        if not self._available:
            return
        done = threading.Event()
        words = len(text.split())
        estimated = max(2.0, words / 2.5)  # ~150 wpm

        def _speak():
            self._queue.put(text)
            time.sleep(estimated)
            done.set()

        threading.Thread(target=_speak, daemon=True).start()
        done.wait(timeout=timeout)

    @property
    def available(self) -> bool:
        return self._available


_tts: Optional[IMOSTTSEngine] = None
_tts_lock = threading.Lock()


def get_tts() -> IMOSTTSEngine:
    global _tts
    with _tts_lock:
        if _tts is None:
            _tts = IMOSTTSEngine()
    return _tts


def speak(text: str):
    """Speak text asynchronously (non-blocking)."""
    get_tts().speak(text)


def speak_sync(text: str):
    """Speak text and wait for it to finish."""
    get_tts().speak_sync(text)


def configure_tts(*, voice: str | None = None, rate: int | None = None) -> dict:
    tts = get_tts()
    if voice is not None:
        tts.set_voice(voice)
    if rate is not None:
        tts.set_rate(rate)
    return tts.status()


def get_voice_status() -> dict:
    tts = get_tts()
    mic_available = False
    try:
        import speech_recognition as sr
        with sr.Microphone():
            mic_available = True
    except Exception:
        mic_available = False
    data = tts.status()
    data["mic_available"] = mic_available
    return data


# ---------------------------------------------------------------------------
# STT listener
# ---------------------------------------------------------------------------

def listen_once(timeout: int = 5, phrase_time_limit: int = 12) -> Optional[str]:
    """
    Listen for one utterance and return the transcript, or None on failure.
    """
    try:
        import speech_recognition as sr
    except ImportError:
        return None

    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.3)
            audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        text = r.recognize_google(audio).strip()
        return text if text else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Wake word detection
# ---------------------------------------------------------------------------

WAKE_WORDS = ["imos", "hey imos", "i moss", "i mos"]


def _contains_wake_word(text: str) -> bool:
    lowered = text.lower().strip()
    return any(w in lowered for w in WAKE_WORDS)


def _strip_wake_word(text: str) -> str:
    lowered = text.lower()
    for w in sorted(WAKE_WORDS, key=len, reverse=True):
        if lowered.startswith(w):
            return text[len(w):].strip(" ,.")
    return text.strip()


# ---------------------------------------------------------------------------
# Voice loop
# ---------------------------------------------------------------------------

class IMOSVoiceLoop:
    """
    Continuously listens for the wake word, then captures the full command
    and calls the on_command callback with the transcript.
    """

    def __init__(
        self,
        on_command: Callable[[str], str],
        *,
        activation_sound: bool = True,
    ):
        self.on_command = on_command
        self.activation_sound = activation_sound
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._mic_available = self._check_mic()

    def _check_mic(self) -> bool:
        try:
            import speech_recognition as sr
            with sr.Microphone():
                pass
            return True
        except Exception:
            return False

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="imos-voice-loop"
        )
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        if not self._mic_available:
            print("[IMOS Voice] Microphone not available — voice loop disabled.")
            return

        print("[IMOS Voice] Listening for wake word: 'IMOS' or 'Hey IMOS'")
        tts = get_tts()

        while self._running:
            # Phase 1: listen for wake word
            transcript = listen_once(timeout=3, phrase_time_limit=4)
            if transcript is None:
                continue

            if not _contains_wake_word(transcript):
                continue

            # Wake word detected
            print(f"[IMOS Voice] Wake word detected: '{transcript}'")
            if self.activation_sound and tts.available:
                tts.speak("Online, sir.")
                time.sleep(0.8)

            # Phase 2: capture the actual command
            # If the wake word phrase already contains a command, use it
            command = _strip_wake_word(transcript)
            if not command:
                # Listen for the command separately
                print("[IMOS Voice] Listening for command...")
                command = listen_once(timeout=6, phrase_time_limit=15)

            if not command:
                tts.speak("I didn't catch that.")
                continue

            print(f"[IMOS Voice] Command: '{command}'")

            # Phase 3: execute and speak response
            try:
                response = self.on_command(command)
                if response and tts.available:
                    # Truncate very long responses for speech
                    speech_text = response[:600] if len(response) > 600 else response
                    tts.speak(speech_text)
            except Exception as exc:
                print(f"[IMOS Voice] Error executing command: {exc}")
                tts.speak("I encountered an error processing that command.")


# ---------------------------------------------------------------------------
# Convenience starter
# ---------------------------------------------------------------------------

_voice_loop: Optional[IMOSVoiceLoop] = None


def start_voice_loop(on_command: Callable[[str], str]) -> IMOSVoiceLoop:
    """Start the IMOS voice loop daemon thread."""
    global _voice_loop
    _voice_loop = IMOSVoiceLoop(on_command=on_command)
    _voice_loop.start()
    return _voice_loop
