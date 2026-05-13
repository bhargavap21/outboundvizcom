"""Behance and ArtStation public portfolio feed scraping."""
from __future__ import annotations
from typing import List
from agent.signal_detection.linkedin import RawSignal


def fetch_behance_projects(seed_agencies: List[str]) -> List[RawSignal]:
    """
    Scrape the last N projects from each agency's Behance account.
    Uses Playwright headless browser (Behance has no public API).
    TODO: implement Playwright scraper.
    """
    raise NotImplementedError


def fetch_artstation_projects(seed_agencies: List[str]) -> List[RawSignal]:
    """
    Scrape ArtStation public portfolio pages.
    TODO: implement Playwright scraper.
    """
    raise NotImplementedError
