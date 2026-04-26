import os
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from groq import Groq

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS  # type: ignore
    except ImportError:
        DDGS = None


load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def _safe_fetch(url: str, timeout: int = 8) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return "[blocked: invalid URL scheme]"
    if "duckduckgo.com/l/?" in url or "uddg=" in url:
        return "[blocked: tracking redirect URL]"
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; connect-research/1.0)"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:3000]
    except Exception as exc:
        return f"[could not fetch: {exc}]"


def search_and_read(query: str = None, num_results: int = 5) -> str:
    """
    Search the web, read the top pages, return synthesized findings.
    """
    if not query:
        return "Error: query is required for research_web"
    if DDGS is None:
        return "Error: install ddgs package: pip install ddgs"

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=num_results))

    if not results:
        return f"No results found for: {query}"

    page_contents = []
    for result in results[:3]:
        href = result.get("href") or result.get("url")
        if not href:
            continue
        text = _safe_fetch(href)
        page_contents.append(
            f"SOURCE: {href}\nSNIPPET: {result.get('body', '')}\nCONTENT: {text}"
        )

    combined = "\n\n---\n\n".join(page_contents)
    synthesis = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Research question: {query}\n\nWeb pages read:\n{combined}\n\n"
                    "Provide a clear, actionable summary answering the research question.\n"
                    "Focus on: current best practices, specific recommendations, version numbers,\n"
                    "and any important warnings or considerations.\n"
                    "Be specific and concrete not generic."
                ),
            }
        ],
        max_tokens=1500,
    )
    return synthesis.choices[0].message.content


def find_best_tool_for_job(job_description: str) -> str:
    if not job_description:
        return "Error: job_description is required"
    query = f"best {job_description} 2025 comparison pros cons"
    return search_and_read(query)
