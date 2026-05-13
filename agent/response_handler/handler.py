"""
Incoming response classification and routing.

Handles all inbound signals per spec:
  positive    → pause sequence, flag warm, notify SDR via Slack
  objection   → draft Claude reply, store for human review, notify
  unsubscribe → immediate suppression, log reason, feed to scoring
  bounce      → flag for manual check, reroute to LinkedIn channel
  no_response → mark exhausted after full sequence, set 90-day cooldown
"""
from __future__ import annotations
from datetime import datetime, timedelta
from enum import Enum
import httpx
import structlog
import anthropic

from config.settings import (
    ANTHROPIC_API_KEY, MODEL_CONTENT, MODEL_SCORING,
    SLACK_WEBHOOK_URL, COOLING_PERIOD_DAYS,
)
from db import get_session
from db.models import Lead, LeadStatus, OutreachEvent

log = structlog.get_logger()
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


class ResponseType(str, Enum):
    positive    = "positive"
    objection   = "objection"
    unsubscribe = "unsubscribe"
    bounce      = "bounce"
    no_response = "no_response"


def handle_response(
    lead_id: int,
    response_text: str,
    channel: str,
    outreach_event_id: int | None = None,
) -> ResponseType:
    """
    Classify and route an inbound response.
    Updates lead status, logs to OutreachEvent, notifies where needed.
    Returns the ResponseType so callers can act on it.
    """
    response_type = classify_response(response_text)

    session = get_session()
    with session:
        lead = session.get(Lead, lead_id)
        if not lead:
            log.error("response_lead_not_found", lead_id=lead_id)
            return response_type

        # Update the originating OutreachEvent with the response
        if outreach_event_id:
            event = session.get(OutreachEvent, outreach_event_id)
            if event:
                event.replied_at = datetime.utcnow()
                event.response_type = response_type
                event.response_text = response_text[:2000]

        _route(lead, response_type, response_text, channel)
        session.commit()

    log.info(
        "response_handled",
        lead_id=lead_id,
        agency=lead.agency_name,
        type=response_type,
        channel=channel,
    )
    return response_type


def handle_sequence_exhausted(lead_id: int) -> None:
    """
    Call after the Day-30 final email is sent and no reply received.
    Marks lead exhausted and starts the 90-day cooling period.
    """
    session = get_session()
    with session:
        lead = session.get(Lead, lead_id)
        if lead:
            lead.status = LeadStatus.exhausted
            lead.cooldown_until = datetime.utcnow() + timedelta(days=COOLING_PERIOD_DAYS)
            session.commit()
            log.info("lead_exhausted", lead_id=lead_id, cooldown_days=COOLING_PERIOD_DAYS)


def classify_response(response_text: str) -> ResponseType:
    """Use Claude Haiku to classify an inbound reply into one of five types."""
    prompt = f"""Classify this email or LinkedIn reply from a design agency prospect.

Reply text:
{response_text[:1000]}

Classify into exactly one of:
- positive: they're interested, want to talk, asked a follow-up question, or responded warmly
- objection: they pushed back, said not now, not interested, or raised a concern
- unsubscribe: they asked to be removed, opted out, or said stop emailing
- bounce: this is an automated bounce/out-of-office/delivery failure notification
- no_response: empty reply, auto-acknowledgement with no human content

Output only the single classification word, nothing else."""

    try:
        resp = _client.messages.create(
            model=MODEL_SCORING,
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        label = resp.content[0].text.strip().lower()
        return ResponseType(label) if label in ResponseType._value2member_map_ else ResponseType.positive
    except Exception as e:
        log.warning("response_classification_failed", error=str(e))
        return ResponseType.positive  # fail safe — don't suppress an unknown reply


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def _route(lead: Lead, response_type: ResponseType, response_text: str, channel: str) -> None:
    if response_type == ResponseType.positive:
        _handle_positive(lead)

    elif response_type == ResponseType.objection:
        _handle_objection(lead, response_text)

    elif response_type == ResponseType.unsubscribe:
        _handle_unsubscribe(lead, response_text)

    elif response_type == ResponseType.bounce:
        _handle_bounce(lead, channel)

    elif response_type == ResponseType.no_response:
        # no_response is handled by handle_sequence_exhausted() after Day 30
        pass


def _handle_positive(lead: Lead) -> None:
    """Pause all sequences, mark warm, notify SDR."""
    lead.status = LeadStatus.warm
    lead.last_contacted_at = datetime.utcnow()

    _notify_slack(
        f":fire: *Warm lead* — {lead.agency_name}\n"
        f"Contact: {lead.contact_name or 'unknown'} | Score: {lead.score}\n"
        f"Lead ID: {lead.id} — pause sequence and follow up manually."
    )
    log.info("lead_marked_warm", lead_id=lead.id, agency=lead.agency_name)


def _handle_objection(lead: Lead, response_text: str) -> None:
    """Draft a reply, store it, notify for human review — do not send automatically."""
    draft = _draft_objection_reply(response_text, lead)

    # Store the draft as a new OutreachEvent with no sent_at (pending human review)
    session = get_session()
    try:
        with session:
            pending = OutreachEvent(
                lead_id=lead.id,
                channel="email",
                sequence_step=99,   # sentinel: human-review draft
                body=draft,
                variant="objection_reply",
            )
            session.add(pending)
            session.commit()
    except Exception as e:
        log.warning("objection_draft_log_failed", lead_id=lead.id, error=str(e))

    _notify_slack(
        f":speech_balloon: *Objection — needs reply* — {lead.agency_name}\n"
        f"Contact: {lead.contact_name or 'unknown'} | Lead ID: {lead.id}\n"
        f"Draft reply stored in OutreachEvent (step 99) for human review."
    )
    log.info("objection_draft_stored", lead_id=lead.id)


def _handle_unsubscribe(lead: Lead, response_text: str) -> None:
    """Immediate suppression. Log reason. Feed signal back for scoring recalibration."""
    lead.status = LeadStatus.suppressed
    lead.cooldown_until = datetime.utcnow() + timedelta(days=365 * 10)  # effectively permanent

    # Record reason on the most recent outreach event for learning loop
    session = get_session()
    try:
        with session:
            latest = (
                session.query(OutreachEvent)
                .filter(OutreachEvent.lead_id == lead.id)
                .filter(OutreachEvent.sent_at.isnot(None))
                .order_by(OutreachEvent.sent_at.desc())
                .first()
            )
            if latest:
                latest.unsubscribed = True
                latest.response_text = response_text[:500]
                latest.response_type = "unsubscribe"
                session.commit()
    except Exception as e:
        log.warning("unsubscribe_log_failed", lead_id=lead.id, error=str(e))

    log.info("lead_suppressed", lead_id=lead.id, agency=lead.agency_name)


def _handle_bounce(lead: Lead, channel: str) -> None:
    """Flag for manual verification. If email bounced, note to try LinkedIn instead."""
    if channel == "email":
        # Mark the latest email event as bounced
        session = get_session()
        try:
            with session:
                latest = (
                    session.query(OutreachEvent)
                    .filter(OutreachEvent.lead_id == lead.id)
                    .filter(OutreachEvent.channel == "email")
                    .filter(OutreachEvent.sent_at.isnot(None))
                    .order_by(OutreachEvent.sent_at.desc())
                    .first()
                )
                if latest:
                    latest.bounced = True
                    session.commit()
        except Exception as e:
            log.warning("bounce_log_failed", lead_id=lead.id, error=str(e))

        _notify_slack(
            f":warning: *Email bounced* — {lead.agency_name} (Lead {lead.id})\n"
            f"Verify email address and route to LinkedIn if contact URL is available."
        )

    log.warning("email_bounced", lead_id=lead.id, agency=lead.agency_name)


def _draft_objection_reply(response_text: str, lead: Lead) -> str:
    """Generate a short, non-pushy objection response for human review."""
    prompt = f"""A prospect at {lead.agency_name} replied to a Vizcom cold email with this objection:

"{response_text}"

Draft a brief reply (under 80 words) that:
1. Acknowledges their specific concern directly
2. Does not re-pitch from scratch
3. Leaves the door open without pressure
4. Sounds like a peer, not a vendor

Banned: "workflow session", "seamless", "game-changing", "reach out", "AI".
Output only the reply body, no subject line."""

    try:
        resp = _client.messages.create(
            model=MODEL_CONTENT,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        log.warning("objection_draft_failed", lead_id=lead.id, error=str(e))
        return ""


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def _notify_slack(message: str) -> None:
    """Post to Slack webhook if configured. Silently skips if no webhook set."""
    if not SLACK_WEBHOOK_URL:
        return
    try:
        httpx.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=5)
    except Exception as e:
        log.warning("slack_notify_failed", error=str(e))
