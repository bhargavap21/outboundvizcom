"""Main agent loop — APScheduler orchestrates all pipeline steps."""
from __future__ import annotations
import structlog
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import SIGNAL_DETECTION_HOUR, SCORE_PROCEED, SCORE_WATCHLIST
from db import init_db, get_session
from db.models import Signal, Lead, LeadStatus
from agent.signal_detection.runner import run_signal_detection
from agent.scoring.scorer import score_lead, ScoringInput
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

    # Step 2: Score each signal
    session = get_session()
    with session:
        for signal in new_signals:
            inp = ScoringInput(
                agency_name=signal.agency_name,
                vertical=signal.vertical_hint or "",
                team_size=None,       # enriched in research step
                tool_stack=[],        # enriched in research step
                signal_type=signal.signal_type,
                signal_detected_at=signal.detected_at,
            )
            result = score_lead(inp)
            log.info("lead_scored", agency=result.agency_name, score=result.total)

            if result.total >= SCORE_PROCEED:
                status = LeadStatus.researching
            elif result.total >= SCORE_WATCHLIST:
                status = LeadStatus.watchlist
            else:
                log.info("lead_discarded", agency=result.agency_name, score=result.total)
                signal.processed = True
                session.commit()
                continue

            lead = Lead(
                agency_name=signal.agency_name,
                vertical=signal.vertical_hint,
                score=result.total,
                status=status,
                trigger_signal_id=signal.id,
            )
            session.add(lead)
            signal.processed = True
        session.commit()

    # Step 3 + 4: Research and content generation for qualifying leads
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
            except NotImplementedError:
                log.warning("research_or_content_not_implemented", agency=lead.agency_name)
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
