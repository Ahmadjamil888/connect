from __future__ import annotations

from connectai.jarvis import JarvisRuntime
from connectai.voice import SpeechEngine


def voice_loop():
    runtime = JarvisRuntime()
    voice = SpeechEngine()
    voice.speak("Jarvis online. At your service, Sir.")
    wake_words = ("jarvis", "hey jarvis", "ok jarvis")

    while True:
        heard = voice.listen()
        if not heard.get("ok"):
            continue
        user_said = str(heard.get("text", "")).strip()
        if not user_said:
            continue
        lowered = user_said.lower()
        if not any(wake in lowered for wake in wake_words):
            continue
        for wake in wake_words:
            lowered = lowered.replace(wake, "").strip()
        if not lowered:
            voice.speak("Yes Sir?")
            heard = voice.listen()
            if not heard.get("ok"):
                continue
            lowered = str(heard.get("text", "")).strip().lower()
        if lowered in {"exit", "goodbye", "shut down", "stop"}:
            voice.speak("Goodbye Sir. Jarvis shutting down.")
            break
        response = runtime.process(lowered, session_key="jarvis-voice")
        if response:
            voice.speak(response[:500])


if __name__ == "__main__":
    voice_loop()
