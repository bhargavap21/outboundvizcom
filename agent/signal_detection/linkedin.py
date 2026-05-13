"""LinkedIn signal detection — job postings and company feed posts."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class RawSignal:
    agency_name: str
    source: str
    signal_type: str
    vertical_hint: str
    url: str
    raw_text: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


def fetch_job_postings(seed_agencies: List[str]) -> List[RawSignal]:
    """
    Pull new junior/mid designer job postings from LinkedIn Jobs API
    for each agency in the seed list.
    TODO: integrate Apify LinkedIn Jobs scraper.
    """
    raise NotImplementedError


def fetch_company_posts(seed_agencies: List[str]) -> List[RawSignal]:
    """
    Pull recent company feed posts (case studies, project announcements)
    from LinkedIn company pages via Apify.
    TODO: integrate Apify LinkedIn Company Scraper.
    """
    raise NotImplementedError
