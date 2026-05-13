"""Trade press signal detection — RSS feeds and Google News."""
from __future__ import annotations
from typing import List
from agent.signal_detection.linkedin import RawSignal

RSS_FEEDS = [
    "https://www.core77.com/rss",
    "https://www.dezeen.com/feed/",
    "https://www.idsa.org/rss.xml",
]


def fetch_rss_signals(seed_agencies: List[str]) -> List[RawSignal]:
    """
    Parse RSS feeds from Core77, Dezeen, IDSA.
    Filter entries that mention any seed agency by name.
    TODO: implement feedparser integration.
    """
    raise NotImplementedError


def fetch_google_news(agency_name: str, category: str = "") -> List[RawSignal]:
    """
    Query Google News API for "[agency_name] + design + [category]".
    TODO: integrate Google News API.
    """
    raise NotImplementedError
