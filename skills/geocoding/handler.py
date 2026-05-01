"""
IMOS Geocoding skill — get lat/lon and location info for any place.
Uses OpenStreetMap Nominatim (free, no key required).
"""
from __future__ import annotations

import requests

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "place": {"type": "string"},
    },
    "required": ["place"],
}


def run(inputs, **_kwargs):
    place = str(inputs.get("place", "")).strip()
    if not place:
        return {"ok": False, "error": "place is required"}

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place, "format": "json", "limit": 3},
            headers={"User-Agent": "IMOS/1.0 (intelligent-machine-os)"},
            timeout=20,
        )
        response.raise_for_status()
        results = response.json()
        if not results:
            return {"ok": False, "error": f"No results found for: {place}"}
        top = results[0]
        return {
            "ok": True,
            "place": place,
            "display_name": top.get("display_name"),
            "lat": float(top.get("lat", 0)),
            "lon": float(top.get("lon", 0)),
            "country": top.get("address", {}).get("country", ""),
            "type": top.get("type", ""),
            "all_results": [
                {
                    "display_name": r.get("display_name"),
                    "lat": float(r.get("lat", 0)),
                    "lon": float(r.get("lon", 0)),
                }
                for r in results[:3]
            ],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
