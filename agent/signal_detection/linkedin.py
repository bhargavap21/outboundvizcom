"""LinkedIn signal detection via Apify — job postings and company feed posts."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List
import structlog

from agent.signal_detection.apify_client import run_actor
from agent.signal_detection.classifier import classify_signal_type, extract_vertical_hint
from config.settings import (
    APIFY_ACTOR_LINKEDIN_JOBS,
    APIFY_ACTOR_LINKEDIN_POSTS,
    APIFY_JOBS_MAX_RESULTS,
    APIFY_POSTS_MAX_RESULTS,
)

log = structlog.get_logger()

# Design-related job titles to filter for (signals active pipeline, not ops hires)
_TARGET_JOB_TITLES = {
    "industrial designer", "product designer", "id designer",
    "design intern", "junior designer", "mid-level designer",
    "senior designer", "design lead",
}


@dataclass
class RawSignal:
    agency_name: str
    source: str
    signal_type: str
    vertical_hint: str
    url: str
    raw_text: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


def fetch_job_postings(seed_agencies: List[str]) -> List[RawSignal]:
    """
    Pull designer job postings from LinkedIn Jobs for each seed agency via Apify.
    Actor: bebity/linkedin-jobs-scraper (verify at https://apify.com/bebity/linkedin-jobs-scraper)

    Expected actor input:
      queries      — search strings (one per agency)
      maxResults   — cap per query to control cost
    """
    signals: List[RawSignal] = []

    # Batch all agencies into one actor run to minimise Apify overhead
    queries = [f'"{agency}" designer' for agency in seed_agencies]
    run_input = {
        "queries": queries,
        "maxResults": APIFY_JOBS_MAX_RESULTS,
        "proxy": {"useApifyProxy": True},
    }

    try:
        items = run_actor(APIFY_ACTOR_LINKEDIN_JOBS, run_input)
    except Exception as e:
        log.error("linkedin_jobs_actor_failed", error=str(e))
        return signals

    for item in items:
        title = (item.get("title") or item.get("jobTitle") or "").lower()
        if not _is_design_role(title):
            continue

        company = item.get("companyName") or item.get("company") or ""
        agency_name = _match_agency(company, seed_agencies)
        if not agency_name:
            continue

        url = item.get("jobUrl") or item.get("url") or ""
        raw_text = _job_to_text(item)
        posted_at = _parse_date(item.get("postedAt") or item.get("publishedAt"))

        signals.append(RawSignal(
            agency_name=agency_name,
            source="linkedin_job",
            signal_type="new_hire",
            vertical_hint=extract_vertical_hint(raw_text),
            url=url,
            raw_text=raw_text,
            timestamp=posted_at,
        ))

    log.info("linkedin_jobs_fetched", total_items=len(items), signals=len(signals))
    return signals


def fetch_company_posts(seed_agencies: List[str]) -> List[RawSignal]:
    """
    Pull recent company feed posts (case studies, client wins, announcements).
    Actor: apimaestro/linkedin-company-posts-scraper
    (verify at https://apify.com/apimaestro/linkedin-company-posts-scraper)

    Expected actor input:
      companyUrls  — LinkedIn company page URLs
      maxPosts     — cap per company
    """
    signals: List[RawSignal] = []

    # Actor expects LinkedIn company URLs; we build best-guess slugs from names.
    # Real LinkedIn URLs should be stored in the agency_list table and passed in.
    company_entries = [
        {"name": name, "url": _linkedin_company_url(name)}
        for name in seed_agencies
    ]

    run_input = {
        "companyUrls": [e["url"] for e in company_entries],
        "maxPosts": APIFY_POSTS_MAX_RESULTS,
        "proxy": {"useApifyProxy": True},
    }

    try:
        items = run_actor(APIFY_ACTOR_LINKEDIN_POSTS, run_input)
    except Exception as e:
        log.error("linkedin_posts_actor_failed", error=str(e))
        return signals

    for item in items:
        company_url = item.get("companyUrl") or item.get("authorUrl") or ""
        agency_name = _match_agency_by_url(company_url, company_entries)
        if not agency_name:
            # Fall back to text matching against company name field
            company = item.get("companyName") or item.get("authorName") or ""
            agency_name = _match_agency(company, seed_agencies)
        if not agency_name:
            continue

        raw_text = item.get("text") or item.get("content") or item.get("description") or ""
        if not raw_text.strip():
            continue

        url = item.get("postUrl") or item.get("url") or ""
        posted_at = _parse_date(item.get("postedAt") or item.get("publishedAt"))
        signal_type = classify_signal_type(raw_text, source="linkedin_post")

        signals.append(RawSignal(
            agency_name=agency_name,
            source="linkedin_post",
            signal_type=signal_type,
            vertical_hint=extract_vertical_hint(raw_text),
            url=url,
            raw_text=raw_text,
            timestamp=posted_at,
        ))

    log.info("linkedin_posts_fetched", total_items=len(items), signals=len(signals))
    return signals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_design_role(title: str) -> bool:
    return any(kw in title for kw in _TARGET_JOB_TITLES)


def _match_agency(company_name: str, seed_agencies: List[str]) -> str:
    """Case-insensitive substring match of company name against seed list."""
    cn = company_name.lower()
    for agency in seed_agencies:
        if agency.lower() in cn or cn in agency.lower():
            return agency
    return ""


def _match_agency_by_url(url: str, entries: list[dict]) -> str:
    url_lower = url.lower()
    for e in entries:
        if e["url"].lower() in url_lower:
            return e["name"]
    return ""


def _linkedin_company_url(agency_name: str) -> str:
    """Best-guess LinkedIn company slug. Replace with stored URLs in production."""
    slug = agency_name.lower().replace(" ", "-").replace("&", "and")
    return f"https://www.linkedin.com/company/{slug}/"


def _job_to_text(item: dict) -> str:
    parts = [
        item.get("title", ""),
        item.get("companyName", ""),
        item.get("description", ""),
        item.get("location", ""),
    ]
    return " | ".join(p for p in parts if p)


def _parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return datetime.utcnow()
