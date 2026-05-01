"""
IMOS Wikipedia skill — search Wikipedia and return a summary.
Uses the wikipedia-api library with requests fallback.
"""
from __future__ import annotations

import requests

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "sentences": {"type": "integer"},
    },
    "required": ["query"],
}


def _from_wikipedia_api(query: str, sentences: int) -> dict:
    import wikipediaapi
    wiki = wikipediaapi.Wikipedia(
        language="en",
        user_agent="IMOS/1.0 (intelligent-machine-os)",
    )
    page = wiki.page(query)
    if not page.exists():
        # Try search
        search_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 1,
            },
            timeout=15,
        )
        results = search_resp.json().get("query", {}).get("search", [])
        if not results:
            return {"ok": False, "error": f"No Wikipedia article found for: {query}"}
        page = wiki.page(results[0]["title"])

    summary = page.summary
    if sentences and sentences > 0:
        # Truncate to N sentences
        parts = summary.split(". ")
        summary = ". ".join(parts[:sentences]) + ("." if len(parts) > sentences else "")

    return {
        "ok": True,
        "title": page.title,
        "summary": summary[:2000],
        "url": page.fullurl,
        "source": "wikipedia-api",
    }


def _from_rest_api(query: str, sentences: int) -> dict:
    """Fallback using Wikipedia REST API."""
    response = requests.get(
        f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(query)}",
        headers={"User-Agent": "IMOS/1.0"},
        timeout=15,
    )
    if response.status_code == 404:
        return {"ok": False, "error": f"No Wikipedia article found for: {query}"}
    response.raise_for_status()
    data = response.json()
    summary = data.get("extract", "")
    if sentences and sentences > 0:
        parts = summary.split(". ")
        summary = ". ".join(parts[:sentences]) + ("." if len(parts) > sentences else "")
    return {
        "ok": True,
        "title": data.get("title", query),
        "summary": summary[:2000],
        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        "source": "wikipedia-rest",
    }


def run(inputs, **_kwargs):
    query = str(inputs.get("query", "")).strip()
    sentences = int(inputs.get("sentences", 5) or 5)
    if not query:
        return {"ok": False, "error": "query is required"}

    try:
        return _from_wikipedia_api(query, sentences)
    except ImportError:
        pass
    except Exception:
        pass

    try:
        return _from_rest_api(query, sentences)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
