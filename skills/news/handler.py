from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import requests
from config.config import _env_value

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "country": {"type": "string"},
        "provider": {"type": "string", "enum": ["auto", "worldmonitor", "worldnewsapi", "gnews", "newsapi", "google-rss", "bbc-rss"]},
        "limit": {"type": "integer"},
    },
}


def _normalize_articles(rows):
    articles = []
    for article in rows:
        if not isinstance(article, dict):
            continue
        source = article.get("source")
        if isinstance(source, dict):
            source = source.get("name", "")
        articles.append(
            {
                "title": article.get("title", "") or article.get("headline", ""),
                "source": source or article.get("publisher", "") or article.get("domain", ""),
                "url": article.get("url", "") or article.get("link", ""),
                "published_at": article.get("published_at", "") or article.get("publishedAt", ""),
            }
        )
    return articles


def _from_newsapi(country: str, category: str, limit: int) -> dict:
    api_key = _env_value("NEWS_API_KEY")
    if not api_key:
        raise RuntimeError("NEWS_API_KEY is not configured.")
    response = requests.get(
        "https://newsapi.org/v2/top-headlines",
        params={
            "country": country,
            "category": category,
            "apiKey": api_key,
            "pageSize": limit,
        },
        timeout=20,
    )
    data = response.json()
    if response.status_code != 200:
        raise RuntimeError(data.get("message", "NewsAPI lookup failed."))
    return {"ok": True, "provider": "newsapi", "articles": _normalize_articles(data.get("articles", [])[:limit])}


def _from_gnews(country: str, category: str, limit: int) -> dict:
    api_key = _env_value("GNEWS_API_KEY")
    if not api_key:
        raise RuntimeError("GNEWS_API_KEY is not configured.")
    response = requests.get(
        "https://gnews.io/api/v4/top-headlines",
        params={"category": category, "lang": "en", "country": country, "max": limit, "apikey": api_key},
        timeout=20,
    )
    data = response.json()
    if response.status_code != 200:
        raise RuntimeError("; ".join(data.get("errors", ["GNews lookup failed."])))
    return {"ok": True, "provider": "gnews", "articles": _normalize_articles(data.get("articles", [])[:limit])}


def _from_worldnewsapi(country: str, limit: int) -> dict:
    api_key = _env_value("WORLDNEWS_API_KEY")
    if not api_key:
        raise RuntimeError("WORLDNEWS_API_KEY is not configured.")
    response = requests.get(
        "https://api.worldnewsapi.com/top-news",
        params={"source-country": country, "language": "en", "number": limit},
        headers={"x-api-key": api_key},
        timeout=20,
    )
    data = response.json()
    if response.status_code != 200:
        raise RuntimeError(data.get("message", "World News API lookup failed."))
    articles = data.get("top_news") or data.get("news") or data.get("articles") or []
    return {"ok": True, "provider": "worldnewsapi", "articles": _normalize_articles(articles[:limit])}


def _from_worldmonitor(limit: int) -> dict:
    api_key = _env_value("WORLDMONITOR_API_KEY", "WORLDMONITOR_API_KEY", "WM_KEY")
    if not api_key:
        raise RuntimeError("WORLDMONITOR_API_KEY is not configured.")
    response = requests.get(
        "https://api.worldmonitor.app/api/news/v1/list-feed-digest",
        params={"limit": limit},
        headers={"X-WorldMonitor-Key": api_key},
        timeout=20,
    )
    if response.status_code != 200:
        raise RuntimeError(f"World Monitor returned {response.status_code}.")
    data = response.json()
    articles = data.get("items") or data.get("data") or data.get("stories") or data.get("results") or []
    return {"ok": True, "provider": "worldmonitor", "articles": _normalize_articles(articles[:limit]), "raw_preview": json.dumps(data)[:300]}


def _from_google_rss(limit: int) -> dict:
    response = requests.get(
        "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en",
        timeout=20,
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    articles = []
    for item in root.findall("./channel/item")[:limit]:
        articles.append(
            {
                "title": item.findtext("title", default=""),
                "source": "Google News RSS",
                "url": item.findtext("link", default=""),
                "published_at": item.findtext("pubDate", default=""),
            }
        )
    return {
        "ok": True,
        "provider": "google-rss",
        "articles": articles,
    }


def _from_bbc_rss(limit: int) -> dict:
    response = requests.get("https://feeds.bbci.co.uk/news/world/rss.xml", timeout=20)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    articles = []
    for item in root.findall("./channel/item")[:limit]:
        articles.append(
            {
                "title": item.findtext("title", default=""),
                "source": "BBC World RSS",
                "url": item.findtext("link", default=""),
                "published_at": item.findtext("pubDate", default=""),
            }
        )
    return {"ok": True, "provider": "bbc-rss", "articles": articles}


def run(inputs, **_kwargs):
    country = str(inputs.get("country", "us")).strip() or "us"
    category = str(inputs.get("category", "general")).strip() or "general"
    provider = str(inputs.get("provider", "auto")).strip().lower() or "auto"
    limit = int(inputs.get("limit", 5) or 5)

    mapping = {
        "worldmonitor": lambda: _from_worldmonitor(limit),
        "worldnewsapi": lambda: _from_worldnewsapi(country, limit),
        "gnews": lambda: _from_gnews(country, category, limit),
        "newsapi": lambda: _from_newsapi(country, category, limit),
        "google-rss": lambda: _from_google_rss(limit),
        "bbc-rss": lambda: _from_bbc_rss(limit),
    }
    if provider != "auto":
        if provider not in mapping:
            return {"ok": False, "error": f"Unknown provider: {provider}"}
        try:
            return mapping[provider]()
        except Exception as exc:
            return {"ok": False, "error": str(exc), "provider": provider}

    errors = []
    for name in ("worldmonitor", "worldnewsapi", "gnews", "newsapi", "google-rss", "bbc-rss"):
        try:
            return mapping[name]()
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    return {"ok": False, "error": "News lookup failed.", "details": errors}
