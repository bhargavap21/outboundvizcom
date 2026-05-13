"""Incoming response classification and routing."""
from __future__ import annotations
from enum import Enum
import structlog
import anthropic

from config.settings import ANTHROPIC_API_KEY, MODEL_CONTENT
from db import get_session
from db.models import Lead, LeadStatus, OutreachEvent

log = structlog.get_logger()
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


class ResponseType(str, Enum):
    positive = "positive"
    objection = "objection"
    unsubscribe = "unsubscribe"
    bounce = "bounce"
    no_response = "no_response"


def classify_response(response_text: str) -> ResponseType:
    """Use Claude Haiku to classify an inbound reply."""
    from config.settings import MODEL_SCORING
    prompt = f"""Classify this email reply from a prospect into exactly one of: positive, objection, unsubscribe, bounce.
Reply: {response_text}
Output only the classification word."""
    resp = _client.messages.create(
        model=MODEL_SCORING,
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    label = resp.content[0].text.strip().lower()
    return ResponseType(label) if label in ResponseType._value2member_map_ else ResponseType.positive


def handle_response(lead_id: int, response_text: str, channel: str) -> None:
    """Route an inbound response to the appropriate action."""
    response_type = classify_response(response_text)
    session = get_session()

    with session:
        lead = session.get(Lead, lead_id)
        if not lead:
            log.error("lead_not_found", lead_id=lead_id)
            return

        if response_type == ResponseType.positive:
            lead.status = LeadStatus.warm
            log.info("lead_warm_flagged_for_sdr", lead_id=lead_id)

        elif response_type == ResponseType.objection:
            draft = _draft_objection_reply(response_text, lead)
            log.info("objection_draft_ready_for_review", lead_id=lead_id, draft=draft)

        elif response_type == ResponseType.unsubscribe:
            lead.status = LeadStatus.suppressed
            log.info("lead_suppressed", lead_id=lead_id)

        elif response_type == ResponseType.bounce:
            log.warning("email_bounced_try_linkedin", lead_id=lead_id)

        session.commit()


def _draft_objection_reply(response_text: str, lead: "Lead") -> str:
    prompt = f"""A prospect at {lead.agency_name} replied to a Vizcom cold email with this objection:
"{response_text}"

Draft a brief, non-pushy reply (under 80 words) that addresses the objection without being salesy.
Focus on their specific concern. Do not re-pitch from scratch."""
    resp = _client.messages.create(
        model=MODEL_CONTENT,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()
