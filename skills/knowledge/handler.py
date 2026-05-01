from __future__ import annotations

from datetime import datetime

import requests

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["wiki_search", "define_word", "tell_joke", "tell_time", "tell_date"]},
        "query": {"type": "string"},
        "word": {"type": "string"},
    },
    "required": ["action"],
}


def _wiki_summary(query: str) -> str:
    try:
        import wikipedia
    except ModuleNotFoundError as exc:
        raise RuntimeError("knowledge unavailable: missing dependency 'wikipedia'") from exc
    try:
        return wikipedia.summary(query, sentences=3)
    except wikipedia.exceptions.DisambiguationError as exc:
        return wikipedia.summary(exc.options[0], sentences=3)
    except Exception as exc:
        return f"No Wikipedia result found for {query}: {exc}"


def _define_word(word: str) -> str:
    response = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=20)
    if response.status_code != 200:
        return f"No definition found for {word}."
    data = response.json()[0]
    meanings = data.get("meanings", [])
    if not meanings:
        return f"No definition found for {word}."
    definition = meanings[0]["definitions"][0]["definition"]
    part_of_speech = meanings[0].get("partOfSpeech", "word")
    return f"{word} ({part_of_speech}): {definition}"


def _tell_joke() -> str:
    try:
        import pyjokes
    except ModuleNotFoundError as exc:
        raise RuntimeError("jokes unavailable: missing dependency 'pyjokes'") from exc
    return pyjokes.get_joke()


def run(inputs, **_kwargs):
    action = str(inputs.get("action", "")).strip().lower()
    if action == "wiki_search":
        return {"ok": True, "result": _wiki_summary(str(inputs.get("query", "")).strip())}
    if action == "define_word":
        return {"ok": True, "result": _define_word(str(inputs.get("word", "")).strip())}
    if action == "tell_joke":
        return {"ok": True, "result": _tell_joke()}
    if action == "tell_time":
        return {"ok": True, "result": f"It is {datetime.now().strftime('%I:%M %p')}, Sir."}
    if action == "tell_date":
        return {"ok": True, "result": f"Today is {datetime.now().strftime('%A, %B %d, %Y')}, Sir."}
    return {"ok": False, "error": f"Unknown action: {action}"}
