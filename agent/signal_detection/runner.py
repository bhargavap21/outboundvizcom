"""Orchestrates all signal sources and persists deduplicated events."""
from __future__ import annotations
import structlog
from datetime import datetime, timedelta
from typing import List

from agent.signal_detection.linkedin import RawSignal, fetch_job_postings, fetch_company_posts
from agent.signal_detection.behance import fetch_behance_projects, fetch_artstation_projects
from agent.signal_detection.trade_press import fetch_rss_signals, fetch_google_news
from db import get_session
from db.models import Signal
from config.settings import DEDUP_WINDOW_DAYS

log = structlog.get_logger()


def run_signal_detection(seed_agencies: List[str]) -> List[Signal]:
    """
    Run all signal sources, deduplicate, and persist new signals to DB.
    Called daily by APScheduler.
    """
    raw: List[RawSignal] = []

    collectors = [
        ("linkedin_jobs",   lambda: fetch_job_postings(seed_agencies)),
        ("linkedin_posts",  lambda: fetch_company_posts(seed_agencies)),
        ("behance",         lambda: fetch_behance_projects(seed_agencies)),
        ("artstation",      lambda: fetch_artstation_projects(seed_agencies)),
        ("rss",             lambda: fetch_rss_signals(seed_agencies)),
        ("google_news",     lambda: fetch_google_news(seed_agencies)),
    ]

    for name, fn in collectors:
        try:
            results = fn()
            raw.extend(results)
            log.info("signal_source_complete", source=name, count=len(results))
        except Exception as exc:
            log.error("signal_source_error", source=name, error=str(exc))

    return _persist_signals(raw)


def _persist_signals(signals: List[RawSignal]) -> List[Signal]:
    session = get_session()
    cutoff = datetime.utcnow() - timedelta(days=DEDUP_WINDOW_DAYS)
    saved: List[Signal] = []

    with session:
        existing_urls = {
            row[0]
            for row in session.query(Signal.url).filter(Signal.detected_at >= cutoff).all()
        }

        for s in signals:
            if not s.url or s.url in existing_urls:
                continue
            record = Signal(
                agency_name=s.agency_name,
                source=s.source,
                signal_type=s.signal_type,
                vertical_hint=s.vertical_hint,
                url=s.url,
                raw_text=s.raw_text,
                detected_at=s.timestamp,
            )
            session.add(record)
            saved.append(record)
            existing_urls.add(s.url)

        session.commit()

    log.info("signals_persisted", new=len(saved), skipped=len(signals) - len(saved))
    return saved
