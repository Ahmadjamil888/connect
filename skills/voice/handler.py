from __future__ import annotations

from connectai.voice import SpeechEngine

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["speak", "listen", "switch_voice"]},
        "text": {"type": "string"},
        "mode": {"type": "string", "enum": ["jarvis", "friday"]},
        "timeout": {"type": "integer"},
    },
    "required": ["action"],
}

_ENGINE: SpeechEngine | None = None


def _engine() -> SpeechEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = SpeechEngine()
    return _ENGINE


def run(inputs, **_kwargs):
    action = str(inputs.get("action", "")).strip().lower()
    engine = _engine()
    if action == "speak":
        return engine.speak(str(inputs.get("text", "")))
    if action == "listen":
        return engine.listen(timeout=int(inputs.get("timeout", 5) or 5))
    if action == "switch_voice":
        mode = engine.set_voice(str(inputs.get("mode", "jarvis")))
        return {"ok": True, "mode": mode}
    return {"ok": False, "error": f"Unknown action: {action}"}
