from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {"type": "string"},
        "timeout_seconds": {"type": "number"},
    },
    "required": ["url"],
}


def run(inputs, **_kwargs):
    url = str(inputs["url"]).strip()
    timeout_seconds = float(inputs.get("timeout_seconds", 5) or 5)
    request = Request(url, headers={"User-Agent": "ConnectAI/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return {
                "ok": True,
                "url": url,
                "status": getattr(response, "status", 200),
                "reason": getattr(response, "reason", "OK"),
            }
    except HTTPError as exc:
        return {
            "ok": False,
            "url": url,
            "status": exc.code,
            "reason": str(exc),
        }
    except URLError as exc:
        return {
            "ok": False,
            "url": url,
            "error": str(exc.reason),
        }
