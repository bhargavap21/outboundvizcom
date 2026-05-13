"""Deep research per qualified lead — website, LinkedIn, Behance, news."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import structlog

log = structlog.get_logger()


@dataclass
class AgencyBrief:
    agency_name: str
    website: Optional[str] = None
    verticals: list[str] = field(default_factory=list)
    team_size: Optional[int] = None
    tool_stack: list[str] = field(default_factory=list)
    estimated_render_volume: Optional[str] = None
    contact_name: Optional[str] = None
    contact_linkedin: Optional[str] = None
    contact_email: Optional[str] = None
    recent_projects: list[dict] = field(default_factory=list)
    trigger_summary: str = ""
    raw_sources: dict = field(default_factory=dict)


def research_agency(agency_name: str, website: str, linkedin_url: str) -> AgencyBrief:
    """
    Pull and synthesize data for a single qualified lead.
    Returns a structured AgencyBrief used by content generation.
    TODO: implement each sub-function below.
    """
    brief = AgencyBrief(agency_name=agency_name, website=website)

    try:
        brief.raw_sources["website"] = _scrape_website(website)
    except Exception as e:
        log.warning("website_scrape_failed", agency=agency_name, error=str(e))

    try:
        brief.raw_sources["linkedin"] = _scrape_linkedin(linkedin_url)
    except Exception as e:
        log.warning("linkedin_scrape_failed", agency=agency_name, error=str(e))

    try:
        brief.raw_sources["behance"] = _scrape_behance(agency_name)
    except Exception as e:
        log.warning("behance_scrape_failed", agency=agency_name, error=str(e))

    try:
        brief.raw_sources["news"] = _fetch_news(agency_name)
    except Exception as e:
        log.warning("news_fetch_failed", agency=agency_name, error=str(e))

    return brief


def _scrape_website(url: str) -> dict:
    """Scrape services, client logos, case studies, team page."""
    raise NotImplementedError


def _scrape_linkedin(linkedin_url: str) -> dict:
    """Scrape employee list, titles, tools mentioned in profiles via Apify."""
    raise NotImplementedError


def _scrape_behance(agency_name: str) -> dict:
    """Scrape last 5 projects: vertical, render style, apparent tool used."""
    raise NotImplementedError


def _fetch_news(agency_name: str) -> dict:
    """Google News search: '[agency] + client'. Awards, public relationships."""
    raise NotImplementedError
