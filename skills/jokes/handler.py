"""
IMOS Jokes skill — fetch a random joke.
Uses official-joke-api.appspot.com (free) with pyjokes fallback.
"""
from __future__ import annotations

import requests

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": ["general", "programming", "knock-knock", "any"],
        },
    },
}


def _from_api(category: str) -> dict:
    url = "https://official-joke-api.appspot.com/random_joke"
    if category in ("programming",):
        url = f"https://official-joke-api.appspot.com/jokes/{category}/random"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list):
        data = data[0]
    setup = data.get("setup", "")
    punchline = data.get("punchline", "")
    joke = f"{setup} ... {punchline}" if setup and punchline else str(data)
    return {"ok": True, "joke": joke, "setup": setup, "punchline": punchline, "source": "official-joke-api"}


def _from_pyjokes(category: str) -> dict:
    import pyjokes
    cat_map = {"programming": "neutral", "general": "neutral", "knock-knock": "neutral", "any": "all"}
    cat = cat_map.get(category, "neutral")
    joke = pyjokes.get_joke(category=cat)
    return {"ok": True, "joke": joke, "source": "pyjokes"}


def run(inputs, **_kwargs):
    category = str(inputs.get("category", "any")).strip().lower() or "any"

    # Try official joke API first
    try:
        return _from_api(category)
    except Exception:
        pass

    # Fallback to pyjokes
    try:
        return _from_pyjokes(category)
    except Exception as exc:
        return {"ok": False, "error": f"Could not fetch joke: {exc}"}
