"""Behance portfolio signal detection via Apify. ArtStation disabled (no reliable actor)."""
from __future__ import annotations
from datetime import datetime
from typing import List
import structlog

from agent.signal_detection.apify_client import run_actor
from agent.signal_detection.classifier import extract_vertical_hint
from agent.signal_detection.linkedin import RawSignal, _match_agency, _parse_date
from config.settings import APIFY_ACTOR_BEHANCE, APIFY_PORTFOLIO_MAX_RESULTS

log = structlog.get_logger()


def fetch_behance_projects(seed_agencies: List[str]) -> List[RawSignal]:
    """
    Scrape Behance user profiles matching each agency name and extract their
    recent projects via Apify.
    Actor: easyapi/behance-people-scraper
    (https://apify.com/easyapi/behance-people-scraper)

    Input schema: { query: str, maxItems: int }
    Returns user profile objects with a nested `projects` array.
    We append "industrial design" to the query for better match precision.

    Output keys per user: url, displayName, username, company, projects[{...}]
    """
    signals: List[RawSignal] = []

    for agency_name in seed_agencies:
        run_input = {
            "query": f"{agency_name} industrial design",
            "maxItems": APIFY_PORTFOLIO_MAX_RESULTS,
        }

        try:
            items = run_actor(APIFY_ACTOR_BEHANCE, run_input)
        except Exception as e:
            log.error("behance_actor_failed", agency=agency_name, error=str(e))
            continue

        for item in items:
            # Match the Behance user back to a seed agency
            display_name = item.get("displayName") or ""
            company_field = item.get("company") or ""
            username = item.get("username") or ""

            matched = (
                _match_agency(display_name, seed_agencies)
                or _match_agency(company_field, seed_agencies)
                or _match_agency(username, seed_agencies)
            )
            if not matched:
                continue

            profile_url = item.get("url") or f"https://www.behance.net/{username}"
            projects = item.get("projects") or []

            for project in projects[:APIFY_PORTFOLIO_MAX_RESULTS]:
                raw_text = _project_to_text(project, item)
                project_url = (
                    project.get("url")
                    or project.get("projectUrl")
                    or profile_url
                )
                published_at = _parse_date(
                    project.get("publishedOn")
                    or project.get("createdOn")
                    or project.get("modifiedOn")
                )

                signals.append(RawSignal(
                    agency_name=matched,
                    source="behance",
                    signal_type="portfolio_update",
                    vertical_hint=extract_vertical_hint(raw_text),
                    url=project_url,
                    raw_text=raw_text,
                    timestamp=published_at,
                ))

    log.info("behance_fetched", agencies=len(seed_agencies), signals=len(signals))
    return signals


def fetch_artstation_projects(seed_agencies: List[str]) -> List[RawSignal]:
    """ArtStation disabled — no reliable Apify actor available as of 2026-05."""
    log.info("artstation_disabled_skipping")
    return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _project_to_text(project: dict, user: dict) -> str:
    tags = " ".join(
        t.get("name", "") if isinstance(t, dict) else str(t)
        for t in (project.get("tags") or [])
    )
    fields = " ".join(
        f.get("name", "") if isinstance(f, dict) else str(f)
        for f in (project.get("fields") or [])
    )
    parts = [
        project.get("name") or project.get("title", ""),
        project.get("description", ""),
        tags,
        fields,
        user.get("displayName", ""),
        user.get("company", ""),
    ]
    return " | ".join(p for p in parts if p)
