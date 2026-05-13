"""
SendGrid cold email sender.

Rate limits (from spec):
  - 40 cold sends/day max
  - Send window: 8am–11am recipient local time (Mon/Wed outperform)
  - Unsubscribe link required in every email (CAN-SPAM)
  - Each send logged to OutreachEvent table

A/B variant: alternate by lead_id parity so the learning loop
can compare open rates across subject line variants.
"""
from __future__ import annotations
from datetime import datetime, timezone
import structlog

from config.settings import (
    SENDGRID_API_KEY,
    OUTBOUND_EMAIL_FROM,
    EMAIL_DAILY_LIMIT,
    EMAIL_SEND_HOUR_START,
    EMAIL_SEND_HOUR_END,
)
from db import get_session
from db.models import OutreachEvent, Lead, LeadStatus

log = structlog.get_logger()

_UNSUBSCRIBE_FOOTER = (
    "\n\n---\n"
    "You're receiving this because your agency was identified as a potential Vizcom fit. "
    "To unsubscribe, reply with 'unsubscribe'."
)


def send_cold_email(
    lead_id: int,
    to_email: str,
    to_name: str,
    subject_a: str,
    subject_b: str,
    body: str,
) -> bool:
    """
    Send the Day-3 cold email. Picks A/B variant based on lead_id parity.
    Enforces daily send cap and send-window before attempting delivery.
    Returns True on success.
    """
    if not _within_send_window():
        log.info("email_outside_send_window", lead_id=lead_id)
        return False

    if not _under_daily_cap():
        log.warning("email_daily_cap_reached", lead_id=lead_id)
        return False

    variant = "A" if lead_id % 2 == 0 else "B"
    subject = subject_a if variant == "A" else (subject_b or subject_a)
    full_body = body + _UNSUBSCRIBE_FOOTER

    success = _sendgrid_send(to_email, to_name, subject, full_body)
    _log_event(lead_id, "email", 1, subject, full_body, variant, success)

    if success:
        _update_lead(lead_id, LeadStatus.in_sequence)
        log.info("cold_email_sent", lead_id=lead_id, to=to_email, variant=variant)
    else:
        log.error("cold_email_failed", lead_id=lead_id, to=to_email)

    return success


def send_final_email(lead_id: int, to_email: str, to_name: str, body: str) -> bool:
    """Day-30 final touch. No A/B — one gracious close, no pressure."""
    if not _under_daily_cap():
        log.warning("email_daily_cap_reached", lead_id=lead_id)
        return False

    subject = "One last note"
    full_body = body + _UNSUBSCRIBE_FOOTER
    success = _sendgrid_send(to_email, to_name, subject, full_body)
    _log_event(lead_id, "email", 5, subject, full_body, "final", success)

    if success:
        _update_lead(lead_id, LeadStatus.exhausted)
        log.info("final_email_sent", lead_id=lead_id, to=to_email)

    return success


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sendgrid_send(to_email: str, to_name: str, subject: str, body: str) -> bool:
    try:
        import sendgrid as sg_module
        from sendgrid.helpers.mail import Mail, To, From, Subject, PlainTextContent

        sg = sg_module.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        message = Mail(
            from_email=From(OUTBOUND_EMAIL_FROM),
            to_emails=To(to_email, to_name),
            subject=Subject(subject),
            plain_text_content=PlainTextContent(body),
        )
        resp = sg.client.mail.send.post(request_body=message.get())
        return resp.status_code in (200, 202)
    except Exception as e:
        log.error("sendgrid_send_error", error=str(e))
        return False


def _within_send_window() -> bool:
    """True if current UTC hour falls within the configured send window.

    Target is 8–11am recipient local time. EST=UTC-5, PST=UTC-8.
    Adding 8h buffer so West Coast recipients aren't missed.
    """
    now_hour = datetime.now(timezone.utc).hour
    return EMAIL_SEND_HOUR_START <= now_hour <= (EMAIL_SEND_HOUR_END + 8)


def _under_daily_cap() -> bool:
    """Returns True if today's email send count is under the daily limit."""
    session = get_session()
    try:
        with session:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            sent_today = (
                session.query(OutreachEvent)
                .filter(OutreachEvent.channel == "email")
                .filter(OutreachEvent.sent_at >= today)
                .count()
            )
            return sent_today < EMAIL_DAILY_LIMIT
    except Exception as e:
        log.warning("daily_cap_check_failed", error=str(e))
        return True  # fail open


def _log_event(
    lead_id: int,
    channel: str,
    step: int,
    subject: str,
    body: str,
    variant: str,
    success: bool,
) -> None:
    session = get_session()
    try:
        with session:
            event = OutreachEvent(
                lead_id=lead_id,
                channel=channel,
                sequence_step=step,
                subject=subject,
                body=body,
                variant=variant,
                sent_at=datetime.utcnow() if success else None,
            )
            session.add(event)
            session.commit()
    except Exception as e:
        log.warning("outreach_event_log_failed", lead_id=lead_id, error=str(e))


def _update_lead(lead_id: int, status: LeadStatus) -> None:
    session = get_session()
    try:
        with session:
            lead = session.get(Lead, lead_id)
            if lead:
                lead.status = status
                lead.last_contacted_at = datetime.utcnow()
                session.commit()
    except Exception as e:
        log.warning("lead_status_update_failed", lead_id=lead_id, error=str(e))
