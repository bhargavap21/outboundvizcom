"""
LinkedIn research scraper for deep lead enrichment.

Two data sources:
  1. Existing DB signals — posts we already scraped contain author info
     (the person posting for the company is often the Design Director/Founder)
  2. Apify LinkedIn company scraper — employee count, company description
     Falls back gracefully if actor is paywalled or unavailable.
"""
from __future__ import annotations
import structlog
from db import get_session
from db.models import Signal, AgencyList
from agent.signal_detection.apify_client import run_actor, PermanentActorError
from config.settings import APIFY_API_KEY

log = structlog.get_logger()

# Actor for LinkedIn company info (employee count, description, specialties)
# Verify at https://apify.com/store before first run
LINKEDIN_COMPANY_ACTOR = "harvestapi/linkedin-company"

TARGET_TOOLS = {
    "keyshot", "rhino", "rhinoceros", "solidworks", "alias",
    "catia", "modo", "v-ray", "cinema 4d", "blender", "procreate",
    "fusion 360",
}

DIRECTOR_TITLES = {
    "design director", "creative director", "creative lead",
    "principal designer", "principal industrial designer",
    "founder", "co-founder", "partner", "head of design",
    "vp of design", "chief design officer",
}


def scrape_linkedin(agency_name: str, linkedin_url: str) -> dict:
    """
    Gather LinkedIn data for a qualified lead.
    Returns a dict with: employee_count, description, specialties,
    tool_mentions, contacts, post_authors.
    """
    result: dict = {
        "employee_count": None,
        "description": "",
        "specialties": [],
        "tool_mentions": [],
        "contacts": [],
        "post_authors": [],
    }

    # Source 1: existing posts from DB (free — already scraped)
    _enrich_from_db_signals(agency_name, result)

    # Source 2: agency_list table (may have pre-populated data)
    _enrich_from_agency_list(agency_name, result)

    # Source 3: Apify company scraper (best effort)
    if linkedin_url and APIFY_API_KEY:
        _enrich_from_apify(linkedin_url, result)

    log.info(
        "linkedin_research_done",
        agency=agency_name,
        employee_count=result["employee_count"],
        contacts=len(result["contacts"]),
        tools=result["tool_mentions"],
    )
    return result


def _enrich_from_db_signals(agency_name: str, result: dict) -> None:
    """
    Mine existing Signal records for this agency.
    Post authors and raw text often reveal contacts and tool mentions.
    """
    session = get_session()
    try:
        with session:
            signals = (
                session.query(Signal)
                .filter(Signal.agency_name == agency_name)
                .filter(Signal.source.in_(["linkedin_post", "linkedin_job"]))
                .all()
            )

        combined_text = " ".join(s.raw_text or "" for s in signals).lower()

        # Tool detection from posts text
        result["tool_mentions"] = [t for t in TARGET_TOOLS if t in combined_text]

        # Extract post authors as potential contacts
        # data-slayer actor returns author.name in the raw JSON stored as raw_text
        import json
        for signal in signals:
            raw = signal.raw_text or ""
            # The author name sometimes appears in the raw text as structured data
            # Try to extract "Design Director" / "Founder" mentions with adjacent names
            for title in DIRECTOR_TITLES:
                idx = raw.lower().find(title)
                if idx > 0:
                    snippet = raw[max(0, idx - 80):idx + len(title) + 80]
                    result["contacts"].append({
                        "name": "",   # enriched by synthesizer
                        "title": title,
                        "context": snippet.strip(),
                        "source": "linkedin_post",
                    })
    except Exception as e:
        log.warning("db_signal_enrich_failed", agency=agency_name, error=str(e))


def _enrich_from_agency_list(agency_name: str, result: dict) -> None:
    session = get_session()
    try:
        with session:
            record = (
                session.query(AgencyList)
                .filter(AgencyList.name.ilike(f"%{agency_name}%"))
                .first()
            )
            if record:
                if record.team_size_estimate:
                    result["employee_count"] = record.team_size_estimate
    except Exception as e:
        log.warning("agency_list_enrich_failed", agency=agency_name, error=str(e))


def _enrich_from_apify(linkedin_url: str, result: dict) -> None:
    """
    Try the Apify LinkedIn company scraper for employee count and description.
    Silently skips on paywall or actor errors.
    """
    try:
        items = run_actor(
            LINKEDIN_COMPANY_ACTOR,
            {
                "companies": [linkedin_url],
                "maxResults": 1,
            },
        )
        if items:
            company = items[0]
            result["employee_count"] = (
                result["employee_count"]
                or company.get("employeeCount")
                or company.get("staffCount")
            )
            result["description"] = (
                company.get("description")
                or company.get("about")
                or ""
            )[:500]
            result["specialties"] = (
                company.get("specialities")   # harvestapi uses "specialities"
                or company.get("specialties")
                or []
            )

    except PermanentActorError as e:
        log.warning("linkedin_company_actor_unavailable", error=str(e))
    except Exception as e:
        log.warning("linkedin_company_actor_failed", error=str(e))
