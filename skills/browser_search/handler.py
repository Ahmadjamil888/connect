"""
IMOS Browser Search skill — open YouTube, Google, or any URL.
"""
from __future__ import annotations

import webbrowser
from urllib.parse import quote_plus

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["youtube", "google", "open_url"],
        },
        "query": {"type": "string"},
        "url": {"type": "string"},
    },
    "required": ["action"],
}


def run(inputs, **_kwargs):
    action = str(inputs.get("action", "")).strip().lower()
    query = str(inputs.get("query", "")).strip()
    url = str(inputs.get("url", "")).strip()

    if action == "youtube":
        if not query:
            return {"ok": False, "error": "query is required for youtube search"}
        target = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        webbrowser.open(target)
        return {"ok": True, "action": "youtube", "query": query, "url": target}

    if action == "google":
        if not query:
            return {"ok": False, "error": "query is required for google search"}
        target = f"https://www.google.com/search?q={quote_plus(query)}"
        webbrowser.open(target)
        return {"ok": True, "action": "google", "query": query, "url": target}

    if action == "open_url":
        if not url:
            return {"ok": False, "error": "url is required for open_url"}
        webbrowser.open(url)
        return {"ok": True, "action": "open_url", "url": url}

    return {"ok": False, "error": f"Unknown action: {action}"}
