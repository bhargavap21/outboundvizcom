"""
Test content generation on a live AgencyBrief.

Usage:
    .venv/bin/python scripts/test_content.py                 # uses Morrama (top PROCEED lead)
    .venv/bin/python scripts/test_content.py "Bould Design"  # specific agency
"""
from __future__ import annotations
import sys
import argparse
import structlog

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(30))

from db import init_db, get_session
from db.models import Lead, LeadStatus, AgencyList
from agent.research.researcher import research_agency
from agent.content.generator import generate_content


def _get_lead(agency_filter: str | None) -> dict | None:
    session = get_session()
    with session:
        q = session.query(Lead).filter(Lead.status == LeadStatus.researching)
        if agency_filter:
            q = q.filter(Lead.agency_name.ilike(f"%{agency_filter}%"))
        lead = q.order_by(Lead.score.desc()).first()
        if not lead:
            return None
        return {
            "agency_name": lead.agency_name,
            "website": lead.website or "",
            "linkedin_url": lead.linkedin_url or "",
            "score": lead.score,
        }


def _get_agency_urls(agency_name: str) -> tuple[str, str]:
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("agency", nargs="?", help="Agency name filter")
    args = parser.parse_args()

    init_db()

    lead = _get_lead(args.agency)
    if not lead:
        print("No PROCEED leads found. Run test_pipeline.py first.")
        sys.exit(1)

    agency = lead["agency_name"]
    website = lead["website"]
    linkedin_url = lead["linkedin_url"]

    if not website or not linkedin_url:
        al_website, al_linkedin = _get_agency_urls(agency)
        website = website or al_website
        linkedin_url = linkedin_url or al_linkedin

    print(f"Researching: {agency}  (score={lead['score']})")
    brief = research_agency(agency, website, linkedin_url)
    print(f"Brief ready — contact: {brief.contact_name}, tools: {brief.tool_stack}, verticals: {brief.verticals}\n")

    print("Generating content...")
    pkg = generate_content(brief)

    sep = "═" * 65
    thin = "─" * 65

    print(f"\n{sep}")
    print("  DAY 1 — BEHANCE/ARTSTATION COMMENT")
    print(sep)
    print(pkg.behance_comment)

    print(f"\n{sep}")
    print("  DAY 3 — COLD EMAIL  ({} words)".format(len(pkg.cold_email_body.split())))
    print(sep)
    print(f"Subject A : {pkg.cold_email_subject_a}")
    print(f"Subject B : {pkg.cold_email_subject_b}")
    print(thin)
    print(pkg.cold_email_body)

    print(f"\n{sep}")
    print("  DAY 7 — LINKEDIN CONNECTION NOTE  ({} chars)".format(len(pkg.linkedin_connection_note)))
    print(sep)
    print(pkg.linkedin_connection_note)

    print(f"\n{sep}")
    print("  DAY 14 — LINKEDIN DM")
    print(sep)
    print(pkg.linkedin_dm_day14)

    print(f"\n{sep}")
    print("  DAY 30 — FINAL EMAIL")
    print(sep)
    print(pkg.final_email_day30)
    print()


if __name__ == "__main__":
    main()
