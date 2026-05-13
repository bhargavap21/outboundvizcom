"""Deep research per qualified lead — website, LinkedIn, Behance, news."""
from __future__ import annotations
import structlog

from agent.research.brief import AgencyBrief  # re-export for backward compat
from agent.research.website_scraper import scrape_website
from agent.research.linkedin_scraper import scrape_linkedin
from agent.research.behance_scraper import scrape_behance
from agent.research.news_scraper import search_news
from agent.research.synthesizer import synthesize_brief

log = structlog.get_logger()

__all__ = ["AgencyBrief", "research_agency"]


def research_agency(agency_name: str, website: str, linkedin_url: str) -> AgencyBrief:
    """
    Pull and synthesize data for a single qualified lead.
    Runs all four scrapers in sequence, then feeds raw sources to Claude Haiku
    for structured extraction into an AgencyBrief.
    """
    raw_sources: dict = {}

    if website:
        try:
            raw_sources["website"] = scrape_website(website)
        except Exception as e:
            log.warning("website_scrape_failed", agency=agency_name, error=str(e))
            raw_sources["website"] = {}

    try:
        raw_sources["linkedin"] = scrape_linkedin(agency_name, linkedin_url)
    except Exception as e:
        log.warning("linkedin_scrape_failed", agency=agency_name, error=str(e))
        raw_sources["linkedin"] = {}

    try:
        raw_sources["behance"] = scrape_behance(agency_name)
    except Exception as e:
        log.warning("behance_scrape_failed", agency=agency_name, error=str(e))
        raw_sources["behance"] = {}

    try:
        raw_sources["news"] = search_news(agency_name)
    except Exception as e:
        log.warning("news_fetch_failed", agency=agency_name, error=str(e))
        raw_sources["news"] = {}

    brief = synthesize_brief(agency_name, raw_sources)
    brief.website = website
    return brief
