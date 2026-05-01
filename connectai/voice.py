from __future__ import annotations

from typing import Optional


class SpeechEngine:
    def __init__(self):
        try:
            import pyttsx3
        except ModuleNotFoundError as exc:
            raise RuntimeError("voice unavailable: missing dependency 'pyttsx3'") from exc
        self.engine = None
        self.available = False
        self.mode = "jarvis"
        self.error = ""
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", 175)
            self.available = True
            self.set_voice("jarvis")
        except Exception as exc:
            self.error = str(exc)

    def set_voice(self, mode: str) -> str:
        if self.engine is None:
            self.mode = "friday" if mode.strip().lower() == "friday" else "jarvis"
            return self.mode
        voices = self.engine.getProperty("voices") or []
        selected: Optional[str] = None
        lowered = mode.strip().lower()
        if voices:
            if lowered == "friday" and len(voices) > 1:
                selected = voices[1].id
                self.mode = "friday"
            else:
                selected = voices[0].id
                self.mode = "jarvis"
        if selected:
            self.engine.setProperty("voice", selected)
        return self.mode

    def speak(self, text: str) -> dict:
        if self.engine is None:
            return {"ok": False, "spoken": text, "mode": self.mode, "error": self.error or "Text-to-speech unavailable."}
        self.engine.say(text)
        self.engine.runAndWait()
        return {"ok": True, "spoken": text, "mode": self.mode}

    def listen(self, timeout: int = 5, phrase_time_limit: int = 10) -> dict:
        try:
            import speech_recognition as sr
        except ModuleNotFoundError as exc:
            raise RuntimeError("voice input unavailable: missing dependency 'SpeechRecognition'") from exc
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                text = recognizer.recognize_google(audio).strip()
                return {"ok": True, "text": text}
            except sr.WaitTimeoutError:
                return {"ok": False, "error": "Timed out waiting for speech."}
            except sr.UnknownValueError:
                return {"ok": False, "error": "Could not understand the audio."}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
