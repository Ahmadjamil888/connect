from __future__ import annotations

import httpx

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
    },
    "required": ["query"],
}


def run(inputs, **_kwargs):
    response = httpx.get(
        "https://api.duckduckgo.com/",
        params={
            "q": str(inputs["query"]),
            "format": "json",
            "no_html": 1,
            "no_redirect": 1,
        },
        timeout=30.0,
    )
    return response.text[:4000]
