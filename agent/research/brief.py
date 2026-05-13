"""AgencyBrief dataclass — shared across researcher and synthesizer."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


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
