"""
Claude Haiku synthesis — turns raw multi-source research into a structured AgencyBrief.

Uses claude-haiku-4-5 (cheap, fast) to parse unstructured web/LinkedIn/Behance/news
data into a clean, content-generation-ready AgencyBrief.
"""
from __future__ import annotations
import json
from typing import Optional
import structlog
import anthropic

from agent.research.brief import AgencyBrief
from config.settings import ANTHROPIC_API_KEY, MODEL_SCORING

log = structlog.get_logger()
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

VALID_RENDER_VOLUMES = {"high", "medium", "low"}


def synthesize_brief(agency_name: str, raw_sources: dict) -> AgencyBrief:
    """
    Feed all raw research sources into Claude Haiku and parse the output
    into a structured AgencyBrief ready for email/DM content generation.
    """
    brief = AgencyBrief(agency_name=agency_name, raw_sources=raw_sources)

    prompt = _build_prompt(agency_name, raw_sources)

    try:
        response = _client.messages.create(
            model=MODEL_SCORING,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        data = _parse_response(response.content[0].text)
        _apply_to_brief(brief, data)
        log.info(
            "synthesis_complete",
            agency=agency_name,
            team_size=brief.team_size,
            tools=brief.tool_stack,
            contact=brief.contact_name,
            verticals=brief.verticals,
        )
    except Exception as e:
        log.error("synthesis_failed", agency=agency_name, error=str(e))
        # Fall back to extracting what we can without LLM
        _fallback_extract(brief, raw_sources)

    return brief


def _build_prompt(agency_name: str, raw_sources: dict) -> str:
    # Truncate each source to keep the prompt under ~4k tokens
    website  = json.dumps(raw_sources.get("website", {}),  default=str)[:1200]
    linkedin = json.dumps(raw_sources.get("linkedin", {}), default=str)[:800]
    behance  = json.dumps(raw_sources.get("behance", {}),  default=str)[:800]
    news     = json.dumps(raw_sources.get("news", {}),     default=str)[:600]

    return f"""You are a B2B sales researcher analyzing the industrial design agency "{agency_name}".

Below is raw data scraped from their website, LinkedIn, Behance, and news sources.

WEBSITE DATA:
{website}

LINKEDIN DATA:
{linkedin}

BEHANCE DATA:
{behance}

NEWS DATA:
{news}

Extract and return a single JSON object with these fields:
{{
  "team_size": <integer or null — best estimate of total studio headcount>,
  "tool_stack": <list of strings — rendering/CAD tools mentioned: KeyShot, Rhino, SolidWorks, Alias, etc.>,
  "verticals": <list of strings — design verticals: "footwear","consumer electronics","furniture","automotive","home goods","apparel accessories">,
  "contact_name": <string or null — best outreach contact: Design Director, Creative Lead, Principal, or Founder>,
  "contact_title": <string or null — their title>,
  "contact_linkedin": <string or null — their LinkedIn URL if found>,
  "recent_projects": [
    {{"title": "...", "summary": "one sentence description", "vertical": "...", "render_quality": "high|medium|low"}}
  ],
  "estimated_render_volume": <"high"|"medium"|"low" — how render-intensive their pitch workflow likely is>,
  "trigger_summary": <string — one sentence on why they are a strong Vizcom prospect right now>
}}

Return ONLY the JSON object, no other text."""


def _parse_response(text: str) -> dict:
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            l for l in lines
            if not l.strip().startswith("```")
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON block
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return {}


def _apply_to_brief(brief: AgencyBrief, data: dict) -> None:
    brief.team_size        = _safe_int(data.get("team_size"))
    brief.tool_stack       = _safe_list(data.get("tool_stack"))
    brief.verticals        = _safe_list(data.get("verticals"))
    brief.contact_name     = data.get("contact_name") or None
    brief.contact_linkedin = data.get("contact_linkedin") or None

    rv = (data.get("estimated_render_volume") or "").lower()
    brief.estimated_render_volume = rv if rv in VALID_RENDER_VOLUMES else "medium"

    projects = data.get("recent_projects") or []
    brief.recent_projects = [p for p in projects if isinstance(p, dict)][:5]
    brief.trigger_summary  = data.get("trigger_summary") or ""


def _fallback_extract(brief: AgencyBrief, raw_sources: dict) -> None:
    """Keyword-based extraction when Haiku call fails."""
    website = raw_sources.get("website", {})
    linkedin = raw_sources.get("linkedin", {})

    brief.tool_stack = list(set(
        website.get("tool_mentions", []) + linkedin.get("tool_mentions", [])
    ))
    brief.team_size = linkedin.get("employee_count") or _count_team_members(website)

    contacts = website.get("contacts", []) or linkedin.get("contacts", [])
    if contacts:
        best = contacts[0]
        brief.contact_name = best.get("name") or None
        brief.contact_linkedin = best.get("linkedin_url") or None

    behance = raw_sources.get("behance", {})
    brief.recent_projects = behance.get("projects", [])[:3]


def _count_team_members(website: dict) -> Optional[int]:
    members = website.get("team_members", [])
    return len(members) if len(members) > 2 else None


def _safe_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        v = int(value)
        return v if 1 <= v <= 1000 else None
    except (TypeError, ValueError):
        return None


def _safe_list(value) -> list:
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return []
