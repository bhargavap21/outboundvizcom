"""
Pre-scoring enrichment: fills in team_size and tool_stack before scoring.

Two cheap sources (no extra API calls beyond what we already have):
  1. tool_stack  — scan all raw_text collected for this agency for tool keywords
  2. team_size   — use Haiku's team_size_hint if extracted, else check agency_list DB

A LinkedIn company scraper call (for definitive headcount) is deferred to the
full research step (Step 3), which only runs on leads that pass the score threshold.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import re
import structlog

from db.models import AgencyList

log = structlog.get_logger()

# Tools we're looking for in raw text / employee profiles
TARGET_TOOLS = {
    "keyshot", "rhino", "alias", "solidworks", "catia",
    "modo", "v-ray", "cinema 4d", "blender", "procreate",
}

# Regex patterns for team size mentions in text
_SIZE_PATTERNS = [
    r"\b(\d{1,3})[- ]?person\b",
    r"\bteam of (\d{1,3})\b",
    r"\b(\d{1,3})[- ]?strong\b",
    r"\b(\d{1,3})\s+designers?\b",
    r"\b(\d{1,3})\s+employees?\b",
    r"\b(\d{1,3})\s+people\b",
    r"\bstudio of (\d{1,3})\b",
]
_SIZE_RE = [re.compile(p, re.IGNORECASE) for p in _SIZE_PATTERNS]


@dataclass
class EnrichmentResult:
    team_size: Optional[int]
    tool_stack: list[str] = field(default_factory=list)
    team_size_source: str = "unknown"  # db | text_hint | haiku | none


def enrich_agency(
    agency_name: str,
    all_signal_texts: list[str],
    haiku_team_size_hint: Optional[int] = None,
    db_session=None,
) -> EnrichmentResult:
    """
    Build enrichment data for an agency from three sources in priority order:
      1. agency_list DB table (pre-populated seed data)
      2. Haiku team_size_hint (extracted from signal text by classifier)
      3. Regex scan of all signal texts for size mentions
    Tool stack is always scanned from raw text (free).
    """
    tool_stack = _scan_for_tools(all_signal_texts)

    # Source 1: agency_list table
    if db_session:
        try:
            record = (
                db_session.query(AgencyList)
                .filter(AgencyList.name.ilike(f"%{agency_name}%"))
                .first()
            )
            if record and record.team_size_estimate:
                return EnrichmentResult(
                    team_size=record.team_size_estimate,
                    tool_stack=tool_stack,
                    team_size_source="db",
                )
        except Exception as e:
            log.warning("agency_list_lookup_failed", agency=agency_name, error=str(e))

    # Source 2: Haiku hint (passed in from classifier)
    if haiku_team_size_hint is not None:
        return EnrichmentResult(
            team_size=haiku_team_size_hint,
            tool_stack=tool_stack,
            team_size_source="haiku",
        )

    # Source 3: Regex scan of all signal texts
    size = _extract_size_from_texts(all_signal_texts)
    return EnrichmentResult(
        team_size=size,
        tool_stack=tool_stack,
        team_size_source="text_hint" if size else "none",
    )


def _scan_for_tools(texts: list[str]) -> list[str]:
    """Return any TARGET_TOOLS mentioned across all texts for this agency."""
    found: set[str] = set()
    combined = " ".join(texts).lower()
    for tool in TARGET_TOOLS:
        if tool in combined:
            found.add(tool)
    return sorted(found)


def _extract_size_from_texts(texts: list[str]) -> Optional[int]:
    """Try all regex patterns across texts; return first plausible number found."""
    for text in texts:
        for pattern in _SIZE_RE:
            m = pattern.search(text)
            if m:
                val = int(m.group(1))
                if 2 <= val <= 200:  # sanity bounds for a boutique agency
                    return val
    return None
