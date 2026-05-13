"""Trade press signal detection — RSS feeds (feedparser) and Google News RSS."""
from __future__ import annotations
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List
import feedparser
import httpx
import structlog

from agent.signal_detection.classifier import classify_signal_type, extract_vertical_hint
from agent.signal_detection.linkedin import RawSignal, _match_agency

log = structlog.get_logger()

RSS_FEEDS: dict[str, str] = {
    "core77":  "https://www.core77.com/rss",
    "dezeen":  "https://www.dezeen.com/feed/",
    "idsa":    "https://www.idsa.org/rss.xml",
}

# Google News RSS — free, no API key required
_GNEWS_RSS_URL = (
    "https://news.google.com/rss/search"
    "?q={query}&hl=en-US&gl=US&ceid=US:en"
)
_HTTPX_TIMEOUT = 15  # seconds


def fetch_rss_signals(seed_agencies: List[str]) -> List[RawSignal]:
    """
    Parse RSS feeds from Core77, Dezeen, IDSA.
    Keeps only entries that mention at least one seed agency by name.
    """
    signals: List[RawSignal] = []
    agency_set_lower = {a.lower() for a in seed_agencies}

    for feed_name, feed_url in RSS_FEEDS.items():
        try:
            parsed = feedparser.parse(feed_url)
            if parsed.bozo and not parsed.entries:
                log.warning("rss_feed_parse_error", feed=feed_name, url=feed_url)
                continue

            for entry in parsed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                raw_text = f"{title} {summary}"
                raw_lower = raw_text.lower()

                agency_name = next(
                    (a for a in seed_agencies if a.lower() in raw_lower), None
                )
                if not agency_name:
                    continue

                url = entry.get("link", "")
                published_at = _parse_entry_date(entry)
                signal_type = classify_signal_type(raw_text, source="trade_press")

                signals.append(RawSignal(
                    agency_name=agency_name,
                    source="trade_press",
                    signal_type=signal_type,
                    vertical_hint=extract_vertical_hint(raw_text),
                    url=url,
                    raw_text=raw_text,
                    timestamp=published_at,
                ))

        except Exception as e:
            log.error("rss_feed_error", feed=feed_name, error=str(e))

    log.info("rss_signals_fetched", feeds=len(RSS_FEEDS), signals=len(signals))
    return signals


def fetch_google_news(seed_agencies: List[str]) -> List[RawSignal]:
    """
    Query Google News RSS for each agency to catch client announcements,
    awards, and press coverage not captured by trade press RSS.
    """
    signals: List[RawSignal] = []

    with httpx.Client(timeout=_HTTPX_TIMEOUT, follow_redirects=True) as client:
        for agency_name in seed_agencies:
            query = f'"{agency_name}" industrial design'
            url = _GNEWS_RSS_URL.format(query=httpx.QueryParams({"q": query})["q"])

            try:
                response = client.get(
                    "https://news.google.com/rss/search",
                    params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
                )
                response.raise_for_status()
                parsed = feedparser.parse(response.text)

                for entry in parsed.entries:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "") or ""
                    raw_text = f"{title} {summary}"

                    entry_url = entry.get("link", "")
                    published_at = _parse_entry_date(entry)
                    signal_type = classify_signal_type(raw_text, source="trade_press")

                    signals.append(RawSignal(
                        agency_name=agency_name,
                        source="google_news",
                        signal_type=signal_type,
                        vertical_hint=extract_vertical_hint(raw_text),
                        url=entry_url,
                        raw_text=raw_text,
                        timestamp=published_at,
                    ))

            except Exception as e:
                log.error("google_news_error", agency=agency_name, error=str(e))

    log.info("google_news_fetched", agencies=len(seed_agencies), signals=len(signals))
    return signals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_entry_date(entry: feedparser.FeedParserDict) -> datetime:
    for field in ("published", "updated", "created"):
        value = entry.get(f"{field}_parsed") or entry.get(field)
        if value:
            if hasattr(value, "tm_year"):
                # struct_time from feedparser
                import time
                try:
                    return datetime.fromtimestamp(time.mktime(value))
                except (ValueError, OverflowError):
                    continue
            if isinstance(value, str):
                try:
                    return parsedate_to_datetime(value).replace(tzinfo=None)
                except Exception:
                    continue
    return datetime.utcnow()
