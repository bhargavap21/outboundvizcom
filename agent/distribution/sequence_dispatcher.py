"""
Sequence dispatcher — advances leads through the channel schedule.

Called daily by the main pipeline. For each lead in content_ready or
in_sequence status, checks which steps are due and fires them.

Channel schedule (from spec):
  Day  1  Behance/ArtStation comment  — manual or future automation
  Day  3  Cold email
  Day  7  LinkedIn connection request
  Day 14  LinkedIn DM (only if connected)
  Day 30  Final email → lead marked exhausted

Content is stored on the Lead.agency_brief JSON field, written
by the content generation step.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
import structlog

from db import get_session
from db.models import Lead, LeadStatus, OutreachEvent
from agent.distribution.email_sender import send_cold_email, send_final_email
from agent.distribution.linkedin_sender import (
    send_connection_request,
    send_dm,
    is_connected,
)
from agent.response_handler.handler import handle_sequence_exhausted

log = structlog.get_logger()

# Days after first_contacted_at each step fires
_STEP_DAY = {
    "email_cold":    3,
    "li_connect":    7,
    "li_dm":        14,
    "email_final":  30,
}


def run_sequence_dispatcher() -> dict:
    """
    Advance all active leads through their channel sequence.
    Returns counts of actions taken.
    """
    counts = {"email_cold": 0, "li_connect": 0, "li_dm": 0, "email_final": 0, "skipped": 0}

    session = get_session()
    with session:
        leads = (
            session.query(Lead)
            .filter(Lead.status.in_([LeadStatus.content_ready, LeadStatus.in_sequence]))
            .all()
        )

        for lead in leads:
            pkg = lead.agency_brief or {}
            if not pkg:
                log.warning("no_content_package", lead_id=lead.id, agency=lead.agency_name)
                counts["skipped"] += 1
                continue

            anchor = lead.last_contacted_at or lead.created_at or datetime.utcnow()
            days_elapsed = (datetime.utcnow() - anchor).days

            # Step: cold email (Day 3)
            if _step_due("email_cold", days_elapsed, lead.id, session):
                ok = send_cold_email(
                    lead_id=lead.id,
                    to_email=lead.contact_email or "",
                    to_name=lead.contact_name or "",
                    subject_a=pkg.get("cold_email_subject_a", ""),
                    subject_b=pkg.get("cold_email_subject_b", ""),
                    body=pkg.get("cold_email_body", ""),
                )
                if ok:
                    counts["email_cold"] += 1
                    if not lead.last_contacted_at:
                        lead.last_contacted_at = datetime.utcnow()

            # Step: LinkedIn connection (Day 7)
            elif _step_due("li_connect", days_elapsed, lead.id, session):
                contact_li = lead.contact_linkedin or ""
                if contact_li:
                    ok = send_connection_request(
                        lead_id=lead.id,
                        linkedin_url=contact_li,
                        note=pkg.get("linkedin_connection_note", ""),
                    )
                    if ok:
                        counts["li_connect"] += 1
                else:
                    log.info("li_connect_skipped_no_url", lead_id=lead.id)
                    counts["skipped"] += 1

            # Step: LinkedIn DM (Day 14, only if connected)
            elif _step_due("li_dm", days_elapsed, lead.id, session):
                if is_connected(lead.id) and lead.contact_linkedin:
                    ok = send_dm(
                        lead_id=lead.id,
                        linkedin_url=lead.contact_linkedin,
                        message=pkg.get("linkedin_dm_day14", ""),
                        sequence_step=4,
                    )
                    if ok:
                        counts["li_dm"] += 1
                else:
                    log.info("li_dm_skipped_not_connected", lead_id=lead.id)
                    counts["skipped"] += 1

            # Step: final email (Day 30) → then mark exhausted + start cooldown
            elif _step_due("email_final", days_elapsed, lead.id, session):
                ok = send_final_email(
                    lead_id=lead.id,
                    to_email=lead.contact_email or "",
                    to_name=lead.contact_name or "",
                    body=pkg.get("final_email_day30", ""),
                )
                if ok:
                    counts["email_final"] += 1
                    handle_sequence_exhausted(lead.id)

        session.commit()

    log.info("sequence_dispatcher_complete", **counts)
    return counts


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _step_due(step: str, days_elapsed: int, lead_id: int, session) -> bool:
    """True if this step is scheduled for today and hasn't been sent yet."""
    target_day = _STEP_DAY[step]
    if days_elapsed < target_day:
        return False

    channel_map = {
        "email_cold":   ("email", 1),
        "li_connect":   ("linkedin_connect", 3),
        "li_dm":        ("linkedin_dm", 4),
        "email_final":  ("email", 5),
    }
    channel, seq_step = channel_map[step]

    already_sent = (
        session.query(OutreachEvent)
        .filter(OutreachEvent.lead_id == lead_id)
        .filter(OutreachEvent.channel == channel)
        .filter(OutreachEvent.sequence_step == seq_step)
        .filter(OutreachEvent.sent_at.isnot(None))
        .first()
    )
    return already_sent is None
