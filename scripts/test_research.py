"""
Test the research step on PROCEED leads already in the database.

Usage:
    .venv/bin/python scripts/test_research.py                    # all PROCEED leads
    .venv/bin/python scripts/test_research.py "Morrama"          # specific agency
    .venv/bin/python scripts/test_research.py --limit 2          # first N leads
"""
from __future__ import annotations
import sys
import argparse
import json
import structlog

# Silence structlog noise for cleaner output
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(20))

from db import init_db, get_session
from db.models import Lead, LeadStatus, AgencyList
from agent.research.researcher import research_agency

log = structlog.get_logger()


def _get_leads(agency_filter: str | None, limit: int) -> list:
    session = get_session()
    with session:
        q = session.query(Lead).filter(Lead.status == LeadStatus.researching)
        if agency_filter:
            q = q.filter(Lead.agency_name.ilike(f"%{agency_filter}%"))
        leads = q.limit(limit).all()
        # Detach from session by converting to plain dicts
        return [
            {
                "agency_name": l.agency_name,
                "website": l.website or "",
                "linkedin_url": l.linkedin_url or "",
                "score": l.score,
            }
            for l in leads
        ]


def _get_agency_urls(agency_name: str) -> tuple[str, str]:
    """Look up website and linkedin_url from AgencyList if not on Lead."""
    session = get_session()
    with session:
        record = (
            session.query(AgencyList)
            .filter(AgencyList.name.ilike(f"%{agency_name}%"))
            .first()
        )
        if record:
            website = record.website or ""
            linkedin_url = (
                f"https://www.linkedin.com/company/{record.linkedin_slug}"
                if record.linkedin_slug
                else ""
            )
            return website, linkedin_url
    return "", ""


def print_brief(brief) -> None:
    sep = "─" * 60
    print(f"\n{sep}")
    print(f"  {brief.agency_name}")
    print(sep)
    print(f"  Website      : {brief.website or '—'}")
    print(f"  Team size    : {brief.team_size or '—'}")
    print(f"  Verticals    : {', '.join(brief.verticals) or '—'}")
    print(f"  Tools        : {', '.join(brief.tool_stack) or '—'}")
    print(f"  Render vol   : {brief.estimated_render_volume or '—'}")
    print(f"  Contact      : {brief.contact_name or '—'}")
    print(f"  LinkedIn     : {brief.contact_linkedin or '—'}")
    print(f"  Trigger      : {brief.trigger_summary or '—'}")
    if brief.recent_projects:
        print(f"  Projects ({len(brief.recent_projects)}):")
        for p in brief.recent_projects[:3]:
            title = p.get("title", "")
            summary = p.get("summary", p.get("description", ""))[:80]
            rq = p.get("render_quality", "")
            print(f"    • [{rq}] {title} — {summary}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("agency", nargs="?", help="Agency name filter")
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()

    init_db()

    leads = _get_leads(args.agency, args.limit)
    if not leads:
        print("No PROCEED leads found. Run test_pipeline.py first.")
        sys.exit(1)

    print(f"\nRunning research on {len(leads)} lead(s)...\n")

    for lead in leads:
        agency = lead["agency_name"]
        website = lead["website"]
        linkedin_url = lead["linkedin_url"]

        # Supplement from AgencyList if Lead lacks URLs
        if not website or not linkedin_url:
            al_website, al_linkedin = _get_agency_urls(agency)
            website = website or al_website
            linkedin_url = linkedin_url or al_linkedin

        print(f"Researching: {agency}  (score={lead['score']})")
        try:
            brief = research_agency(agency, website, linkedin_url)
            print_brief(brief)
        except Exception as e:
            print(f"  ERROR: {e}\n")


if __name__ == "__main__":
    main()
