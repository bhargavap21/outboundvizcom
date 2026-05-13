"""Main agent loop — APScheduler orchestrates all pipeline steps."""
from __future__ import annotations
import structlog
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import SIGNAL_DETECTION_HOUR
from db import init_db, get_session
from db.models import Lead, LeadStatus
from agent.signal_detection.runner import run_signal_detection
from agent.scoring.pipeline import run_scoring_pipeline
from agent.research.researcher import research_agency
from agent.content.generator import generate_content
from agent.learning_loop.analyzer import run_weekly_analysis

log = structlog.get_logger()

SEED_AGENCIES: list[str] = []  # TODO: load from agency_list table or CSV


def pipeline_daily() -> None:
    log.info("daily_pipeline_start")

    # Step 1: Signal detection
    new_signals = run_signal_detection(SEED_AGENCIES)
    log.info("signals_detected", count=len(new_signals))

    # Step 2: Classify → enrich → score → persist leads
    scoring_output = run_scoring_pipeline(new_signals)
    log.info(
        "scoring_complete",
        proceed=len(scoring_output.proceed),
        watchlist=len(scoring_output.watchlist),
        discarded=len(scoring_output.discarded),
    )

    # Step 3 + 4: Deep research and content generation for qualifying leads
    session = get_session()
    with session:
        qualifying = (
            session.query(Lead)
            .filter(Lead.status == LeadStatus.researching)
            .all()
        )
        for lead in qualifying:
            try:
                brief = research_agency(
                    agency_name=lead.agency_name,
                    website=lead.website or "",
                    linkedin_url=lead.linkedin_url or "",
                )
                content = generate_content(brief)
                lead.status = LeadStatus.content_ready
                log.info("content_generated", agency=lead.agency_name)
            except Exception as e:
                log.error("pipeline_error", agency=lead.agency_name, error=str(e))
        session.commit()

    log.info("daily_pipeline_complete")


def pipeline_weekly() -> None:
    log.info("weekly_learning_loop_start")
    try:
        digest = run_weekly_analysis()
        log.info("weekly_digest_complete", length=len(digest))
    except Exception as e:
        log.error("weekly_loop_error", error=str(e))


def main() -> None:
    init_db()
    log.info("db_initialized")

    scheduler = BlockingScheduler()

    # Daily signal detection at configured hour (UTC)
    scheduler.add_job(
        pipeline_daily,
        CronTrigger(hour=SIGNAL_DETECTION_HOUR, minute=0),
        id="daily_pipeline",
        name="Daily signal detection + scoring + research",
        max_instances=1,
        coalesce=True,
    )

    # Weekly learning loop every Sunday at 02:00 UTC
    scheduler.add_job(
        pipeline_weekly,
        CronTrigger(day_of_week="sun", hour=2, minute=0),
        id="weekly_learning_loop",
        name="Weekly performance analysis",
        max_instances=1,
        coalesce=True,
    )

    log.info("scheduler_starting")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler_stopped")


if __name__ == "__main__":
    main()
