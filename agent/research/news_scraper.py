"""
Targeted Google News RSS search for an agency — client wins, awards, press coverage.
Reuses the same feedparser + httpx approach from signal detection trade press.
Runs multiple focused queries to maximise useful signal.
"""
from __future__ import annotations
from datetime import datetime
from email.utils import parsedate_to_datetime
import feedparser
import httpx
import structlog

log = structlog.get_logger()

TIMEOUT = 12
MAX_RESULTS = 10
_GNEWS_BASE = "https://news.google.com/rss/search"

QUERY_TEMPLATES = [
    '"{agency}" new client',
    '"{agency}" design award',
    '"{agency}" industrial design',
    '"{agency}" product design',
]


def search_news(agency_name: str) -> dict:
    """
    Run targeted Google News RSS queries for this agency.
    Returns: {articles: [{title, url, published, snippet, query}]}
    """
    result: dict = {"articles": []}
    seen_urls: set[str] = set()

    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        for template in QUERY_TEMPLATES:
            query = template.format(agency=agency_name)
            articles = _fetch_query(client, query, agency_name, seen_urls)
            result["articles"].extend(articles)
            if len(result["articles"]) >= MAX_RESULTS:
                break

    result["articles"] = result["articles"][:MAX_RESULTS]
    log.info("news_research_done", agency=agency_name, articles=len(result["articles"]))
    return result


def _fetch_query(
    client: httpx.Client,
    query: str,
    agency_name: str,
    seen_urls: set[str],
) -> list[dict]:
    articles = []
    try:
        resp = client.get(
            _GNEWS_BASE,
            params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
        )
        resp.raise_for_status()
        parsed = feedparser.parse(resp.text)

        for entry in parsed.entries[:5]:
            url = entry.get("link") or entry.get("id") or ""
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = entry.get("title", "")
            summary = entry.get("summary") or entry.get("description") or ""

            # Skip if agency name not in title or summary (noise filter)
            combined = f"{title} {summary}".lower()
            if agency_name.lower() not in combined:
                continue

            articles.append({
                "title":     title,
                "url":       url,
                "published": _parse_date(entry),
                "snippet":   summary[:300],
                "query":     query,
            })
    except Exception as e:
        log.warning("news_query_failed", query=query, error=str(e))

    return articles


def _parse_date(entry) -> str:
    for field in ("published", "updated"):
        value = entry.get(f"{field}_parsed") or entry.get(field)
        if value:
            if hasattr(value, "tm_year"):
                import time
                try:
                    return datetime.fromtimestamp(time.mktime(value)).isoformat()
                except Exception:
                    pass
            if isinstance(value, str):
                try:
                    return parsedate_to_datetime(value).isoformat()
                except Exception:
                    pass
    return datetime.utcnow().isoformat()
