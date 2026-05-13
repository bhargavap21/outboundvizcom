"""Lead scoring — 5-dimension 0-100 model per spec."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

HIGH_VERTICAL = {"footwear", "consumer electronics", "furniture", "home goods", "apparel accessories"}
MID_VERTICAL = {"automotive"}

HIGH_TOOLS = {"keyshot", "rhino", "alias"}


@dataclass
class ScoringInput:
    agency_name: str
    vertical: str
    team_size: Optional[int]
    tool_stack: list[str]
    signal_type: str          # new_hire | case_study | client_win | portfolio_update
    signal_detected_at: datetime


@dataclass
class ScoringResult:
    agency_name: str
    total: float
    vertical_score: float
    size_score: float
    tool_score: float
    recency_score: float
    strength_score: float


def score_lead(inp: ScoringInput) -> ScoringResult:
    vertical_score = _score_vertical(inp.vertical)
    size_score = _score_size(inp.team_size)
    tool_score = _score_tools(inp.tool_stack)
    recency_score = _score_recency(inp.signal_detected_at)
    strength_score = _score_signal_strength(inp.signal_type)

    total = vertical_score + size_score + tool_score + recency_score + strength_score
    return ScoringResult(
        agency_name=inp.agency_name,
        total=round(total, 1),
        vertical_score=vertical_score,
        size_score=size_score,
        tool_score=tool_score,
        recency_score=recency_score,
        strength_score=strength_score,
    )


def _score_vertical(vertical: str) -> float:
    v = vertical.lower()
    if any(h in v for h in HIGH_VERTICAL):
        return 25.0
    if any(m in v for m in MID_VERTICAL):
        return 15.0
    return 5.0


def _score_size(team_size: Optional[int]) -> float:
    if team_size is None:
        return 0.0
    if 10 <= team_size <= 25:
        return 20.0
    if 5 <= team_size < 10 or 25 < team_size <= 50:
        return 12.0
    return 0.0


def _score_tools(tool_stack: list[str]) -> float:
    lowered = {t.lower() for t in tool_stack}
    if lowered & HIGH_TOOLS:
        return 20.0
    return 5.0


def _score_recency(detected_at: datetime) -> float:
    age_days = (datetime.utcnow() - detected_at).days
    if age_days < 7:
        return 20.0
    if age_days < 14:
        return 12.0
    if age_days < 30:
        return 5.0
    return 0.0


def _score_signal_strength(signal_type: str) -> float:
    return {
        "client_win": 15.0,
        "case_study": 12.0,
        "new_hire": 8.0,
        "portfolio_update": 5.0,
    }.get(signal_type, 5.0)
