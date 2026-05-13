"""Behance and ArtStation portfolio signal detection via Apify."""
from __future__ import annotations
from datetime import datetime
from typing import List
import structlog

from agent.signal_detection.apify_client import run_actor
from agent.signal_detection.classifier import extract_vertical_hint
from agent.signal_detection.linkedin import RawSignal, _match_agency, _parse_date
from config.settings import (
    APIFY_ACTOR_BEHANCE,
    APIFY_ACTOR_ARTSTATION,
    APIFY_PORTFOLIO_MAX_RESULTS,
)

log = structlog.get_logger()


def fetch_behance_projects(seed_agencies: List[str]) -> List[RawSignal]:
    """
    Scrape the latest projects from each agency's Behance account via Apify.
    Actor: apify/behance-scraper (verify at https://apify.com/store?search=behance)

    Expected actor input:
      searchQueries — list of agency name search terms
      maxResults    — max projects per query
    """
    signals: List[RawSignal] = []

    run_input = {
        "searchQueries": seed_agencies,
        "maxResults": APIFY_PORTFOLIO_MAX_RESULTS,
        "proxy": {"useApifyProxy": True},
    }

    try:
        items = run_actor(APIFY_ACTOR_BEHANCE, run_input)
    except Exception as e:
        log.error("behance_actor_failed", error=str(e))
        return signals

    for item in items:
        owner = (
            item.get("ownerName")
            or item.get("owners", [{}])[0].get("displayName", "")
            or item.get("teamName", "")
        )
        agency_name = _match_agency(owner, seed_agencies)
        if not agency_name:
            # Try matching on the project description/tags
            raw = _behance_to_text(item)
            agency_name = _match_agency(raw, seed_agencies)
        if not agency_name:
            continue

        url = item.get("url") or item.get("projectUrl") or ""
        raw_text = _behance_to_text(item)
        published_at = _parse_date(
            item.get("publishedOn") or item.get("createdOn") or item.get("modifiedOn")
        )

        signals.append(RawSignal(
            agency_name=agency_name,
            source="behance",
            signal_type="portfolio_update",
            vertical_hint=extract_vertical_hint(raw_text),
            url=url,
            raw_text=raw_text,
            timestamp=published_at,
        ))

    log.info("behance_fetched", total_items=len(items), signals=len(signals))
    return signals


def fetch_artstation_projects(seed_agencies: List[str]) -> List[RawSignal]:
    """
    Scrape the latest projects from ArtStation for each agency via Apify.
    Actor: apify/artstation-scraper (verify at https://apify.com/store?search=artstation)

    Expected actor input:
      searchQueries — list of agency name search terms
      maxResults    — max projects per query
    """
    signals: List[RawSignal] = []

    run_input = {
        "searchQueries": seed_agencies,
        "maxResults": APIFY_PORTFOLIO_MAX_RESULTS,
        "proxy": {"useApifyProxy": True},
    }

    try:
        items = run_actor(APIFY_ACTOR_ARTSTATION, run_input)
    except Exception as e:
        log.error("artstation_actor_failed", error=str(e))
        return signals

    for item in items:
        owner = (
            item.get("user", {}).get("full_name", "")
            or item.get("username", "")
            or item.get("ownerName", "")
        )
        agency_name = _match_agency(owner, seed_agencies)
        if not agency_name:
            raw = _artstation_to_text(item)
            agency_name = _match_agency(raw, seed_agencies)
        if not agency_name:
            continue

        url = (
            item.get("permalink")
            or item.get("url")
            or f"https://www.artstation.com/projects/{item.get('hash_id', '')}"
        )
        raw_text = _artstation_to_text(item)
        published_at = _parse_date(
            item.get("created_at") or item.get("updated_at")
        )

        signals.append(RawSignal(
            agency_name=agency_name,
            source="artstation",
            signal_type="portfolio_update",
            vertical_hint=extract_vertical_hint(raw_text),
            url=url,
            raw_text=raw_text,
            timestamp=published_at,
        ))

    log.info("artstation_fetched", total_items=len(items), signals=len(signals))
    return signals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _behance_to_text(item: dict) -> str:
    tags = " ".join(item.get("tags", []) or [])
    fields = " ".join(item.get("fields", []) or [])
    parts = [
        item.get("name", ""),
        item.get("description", ""),
        tags,
        fields,
        item.get("ownerName", ""),
    ]
    return " | ".join(p for p in parts if p)


def _artstation_to_text(item: dict) -> str:
    tags = " ".join(
        t.get("name", "") if isinstance(t, dict) else str(t)
        for t in (item.get("tags") or [])
    )
    categories = " ".join(
        c.get("name", "") if isinstance(c, dict) else str(c)
        for c in (item.get("categories") or [])
    )
    parts = [
        item.get("title", ""),
        item.get("description", ""),
        tags,
        categories,
    ]
    return " | ".join(p for p in parts if p)
