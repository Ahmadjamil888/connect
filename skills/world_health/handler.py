"""
IMOS World Health skill — live disease and WHO health data.
Uses disease.sh (free, no key) and WHO GHO API (free, no key).
"""
from __future__ import annotations

import requests

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "metric": {
            "type": "string",
            "enum": ["covid", "disease_outbreaks", "life_expectancy", "vaccination_rates", "all"],
        },
    },
}


def _get_covid() -> dict:
    response = requests.get("https://disease.sh/v3/covid-19/all", timeout=20)
    response.raise_for_status()
    data = response.json()
    return {
        "source": "disease.sh",
        "cases": data.get("cases"),
        "deaths": data.get("deaths"),
        "recovered": data.get("recovered"),
        "active": data.get("active"),
        "critical": data.get("critical"),
        "cases_per_million": data.get("casesPerOneMillion"),
        "deaths_per_million": data.get("deathsPerOneMillion"),
        "updated": data.get("updated"),
        "affected_countries": data.get("affectedCountries"),
    }


def _get_who_metric(indicator: str) -> dict:
    """Fetch a WHO GHO indicator."""
    url = f"https://ghoapi.azureedge.net/api/{indicator}"
    response = requests.get(url, timeout=20, params={"$top": 5})
    response.raise_for_status()
    data = response.json()
    return {
        "indicator": indicator,
        "source": "WHO GHO",
        "sample": data.get("value", [])[:5],
    }


def run(inputs, **_kwargs):
    metric = str(inputs.get("metric", "covid")).strip().lower() or "covid"

    results = {}
    errors = []

    if metric in ("covid", "all"):
        try:
            results["covid"] = _get_covid()
        except Exception as exc:
            errors.append(f"covid: {exc}")

    if metric in ("life_expectancy", "all"):
        try:
            results["life_expectancy"] = _get_who_metric("WHOSIS_000001")
        except Exception as exc:
            errors.append(f"life_expectancy: {exc}")

    if metric in ("vaccination_rates", "all"):
        try:
            results["vaccination_rates"] = _get_who_metric("WHS4_100")
        except Exception as exc:
            errors.append(f"vaccination_rates: {exc}")

    if metric in ("disease_outbreaks", "all"):
        # Use WHO disease outbreak news RSS
        try:
            import xml.etree.ElementTree as ET
            response = requests.get(
                "https://www.who.int/rss-feeds/news-english.xml",
                timeout=20,
            )
            response.raise_for_status()
            root = ET.fromstring(response.text)
            outbreaks = []
            for item in root.findall("./channel/item")[:5]:
                outbreaks.append({
                    "title": item.findtext("title", ""),
                    "link": item.findtext("link", ""),
                    "date": item.findtext("pubDate", ""),
                })
            results["disease_outbreaks"] = {"source": "WHO RSS", "items": outbreaks}
        except Exception as exc:
            errors.append(f"disease_outbreaks: {exc}")

    if not results:
        return {"ok": False, "error": "No health data retrieved.", "details": errors}

    return {"ok": True, "data": results, "errors": errors}
