"""
Behance research scraper — deeper project extraction for the AgencyBrief.
Reuses the easyapi/behance-people-scraper actor already verified in signal detection.
For research we want: project titles, descriptions, tags, view counts, appreciations.
"""
from __future__ import annotations
import structlog
from agent.signal_detection.apify_client import run_actor, PermanentActorError
from config.settings import APIFY_ACTOR_BEHANCE

log = structlog.get_logger()

MAX_PROJECTS = 5


def scrape_behance(agency_name: str) -> dict:
    """
    Pull the last N Behance projects for this agency.
    Returns a dict with: projects (list of dicts), profile_url.
    """
    result: dict = {"projects": [], "profile_url": ""}

    try:
        items = run_actor(
            APIFY_ACTOR_BEHANCE,
            {
                "query": f"{agency_name} industrial design",
                "maxItems": 3,   # fetch 3 user profiles; extract projects from each
            },
        )
    except PermanentActorError as e:
        log.warning("behance_research_actor_unavailable", agency=agency_name, error=str(e))
        return result
    except Exception as e:
        log.warning("behance_research_actor_failed", agency=agency_name, error=str(e))
        return result

    agency_words = [w.lower() for w in agency_name.split() if len(w) > 3]

    for user_item in items:
        display_name = user_item.get("displayName") or ""
        company = user_item.get("company") or ""
        username = user_item.get("username") or ""
        location = user_item.get("location") or user_item.get("locationCity") or ""

        # Build a broad match corpus including all profile fields
        match_text = f"{display_name} {company} {username} {location}".lower()

        # projects is returned as a dict with "nodes" list by the actor
        projects_container = user_item.get("projects") or {}
        if isinstance(projects_container, dict):
            projects_raw = projects_container.get("nodes") or []
        elif isinstance(projects_container, list):
            projects_raw = projects_container
        else:
            projects_raw = []

        project_text = " ".join(
            p.get("name", "") if isinstance(p, dict) else str(p)
            for p in projects_raw
        ).lower()

        full_corpus = f"{match_text} {project_text}"

        agency_lower = agency_name.lower()
        matched = (
            agency_lower in full_corpus
            or any(word in full_corpus for word in agency_words)
        )
        if not matched:
            continue

        result["profile_url"] = user_item.get("url") or f"https://www.behance.net/{username}"

        for p in projects_raw[:MAX_PROJECTS]:
            if not isinstance(p, dict):
                continue
            stats = p.get("stats") or {}
            result["projects"].append({
                "title":         p.get("name") or p.get("title") or "",
                "description":   (p.get("description") or "")[:300],
                "tags":          p.get("tags") or [],
                "fields":        p.get("fields") or [],
                "url":           p.get("url") or p.get("projectUrl") or "",
                "appreciations": stats.get("appreciations") if isinstance(stats, dict) else None,
                "views":         stats.get("views") if isinstance(stats, dict) else None,
                "published_on":  p.get("publishedOn") or p.get("createdOn") or "",
            })

        if result["projects"]:
            break   # found a good match — stop

    log.info(
        "behance_research_done",
        agency=agency_name,
        projects=len(result["projects"]),
        profile=result["profile_url"],
    )
    return result
