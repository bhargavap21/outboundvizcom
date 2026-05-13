"""
LinkedIn outreach via Phantombuster.

Rate limits (from spec):
  - 20 connection requests/day max (hard LinkedIn limit)
  - DMs only sent after connection is accepted
  - Each action logged to OutreachEvent table

Phantombuster agents used:
  - LinkedIn Network Booster  → connection requests (Day 7)
  - LinkedIn Message Sender   → DMs to accepted connections (Day 14)
"""
from __future__ import annotations
from datetime import datetime
import httpx
import structlog

from config.settings import PHANTOMBUSTER_API_KEY, LINKEDIN_CONNECT_DAILY_LIMIT
from db import get_session
from db.models import OutreachEvent, Lead, LeadStatus

log = structlog.get_logger()

_PB_BASE = "https://api.phantombuster.com/api/v2"
_AGENT_CONNECT = "Connect and send follow-up messages"
_AGENT_MESSAGE = "LinkedIn Message Sender"


def send_connection_request(lead_id: int, linkedin_url: str, note: str) -> bool:
    """
    Day-7: send a LinkedIn connection request with a personalised note.
    Enforces 20/day cap. Returns True on success.
    """
    if not _under_connect_cap():
        log.warning("linkedin_connect_cap_reached", lead_id=lead_id)
        return False

    success = _launch_phantombuster(
        agent_name=_AGENT_CONNECT,
        payload={
            "profileUrls": [linkedin_url],
            "message": note,
            "numberOfAddsPerLaunch": 1,
        },
    )
    _log_event(lead_id, "linkedin_connect", step=3, body=note, success=success)

    if success:
        _update_lead(lead_id, LeadStatus.in_sequence)
        log.info("linkedin_connect_sent", lead_id=lead_id, url=linkedin_url)
    else:
        log.error("linkedin_connect_failed", lead_id=lead_id, url=linkedin_url)

    return success


def send_dm(lead_id: int, linkedin_url: str, message: str, sequence_step: int) -> bool:
    """
    Day-14: send a LinkedIn DM. Only call after verifying is_connected().
    """
    success = _launch_phantombuster(
        agent_name=_AGENT_MESSAGE,
        payload={
            "profileUrls": [linkedin_url],
            "message": message,
        },
    )
    _log_event(lead_id, "linkedin_dm", step=sequence_step, body=message, success=success)

    if success:
        log.info("linkedin_dm_sent", lead_id=lead_id, step=sequence_step)
    else:
        log.error("linkedin_dm_failed", lead_id=lead_id, step=sequence_step)

    return success


def is_connected(lead_id: int) -> bool:
    """True if a successful linkedin_connect event exists for this lead."""
    session = get_session()
    try:
        with session:
            event = (
                session.query(OutreachEvent)
                .filter(OutreachEvent.lead_id == lead_id)
                .filter(OutreachEvent.channel == "linkedin_connect")
                .filter(OutreachEvent.sent_at.isnot(None))
                .first()
            )
            return event is not None
    except Exception as e:
        log.warning("connection_check_failed", lead_id=lead_id, error=str(e))
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _launch_phantombuster(agent_name: str, payload: dict) -> bool:
    """Find agent by name, then launch with payload. Returns True if accepted."""
    if not PHANTOMBUSTER_API_KEY:
        log.warning("phantombuster_key_missing")
        return False

    headers = {"X-Phantombuster-Key": PHANTOMBUSTER_API_KEY}

    try:
        resp = httpx.get(f"{_PB_BASE}/agents", headers=headers, timeout=10)
        resp.raise_for_status()
        agents = resp.json().get("data", {}).get("agents", [])
        agent = next((a for a in agents if a.get("name") == agent_name), None)

        if not agent:
            log.warning("phantombuster_agent_not_found", name=agent_name)
            return False

        launch_resp = httpx.post(
            f"{_PB_BASE}/agents/{agent['id']}/launch",
            json={"output": "result-object", "arguments": payload},
            headers=headers,
            timeout=15,
        )
        launch_resp.raise_for_status()
        return launch_resp.status_code in (200, 201, 202)

    except Exception as e:
        log.error("phantombuster_launch_error", agent=agent_name, error=str(e))
        return False


def _under_connect_cap() -> bool:
    session = get_session()
    try:
        with session:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            sent_today = (
                session.query(OutreachEvent)
                .filter(OutreachEvent.channel == "linkedin_connect")
                .filter(OutreachEvent.sent_at >= today)
                .count()
            )
            return sent_today < LINKEDIN_CONNECT_DAILY_LIMIT
    except Exception as e:
        log.warning("connect_cap_check_failed", error=str(e))
        return True


def _log_event(
    lead_id: int, channel: str, step: int, body: str, success: bool
) -> None:
    session = get_session()
    try:
        with session:
            event = OutreachEvent(
                lead_id=lead_id,
                channel=channel,
                sequence_step=step,
                body=body,
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
