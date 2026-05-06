from __future__ import annotations

import json
import re
from typing import Any

from core.vision import ask_vision


def vision_query(screenshot_path: str, prompt: str) -> str:
    return ask_vision(screenshot_path, prompt)


def parse_json_response(text: str) -> dict[str, Any] | None:
    value = str(text or "").strip()
    if not value:
        return None
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", value, re.IGNORECASE | re.DOTALL)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    inline = re.search(r"(\{.*\})", value, re.DOTALL)
    if inline:
        try:
            parsed = json.loads(inline.group(1))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return None
