"""SendGrid email sending with rate limiting and timezone-aware scheduling."""
from __future__ import annotations
import structlog
from config.settings import (
    SENDGRID_API_KEY, OUTBOUND_EMAIL_FROM,
    EMAIL_DAILY_LIMIT, EMAIL_SEND_HOUR_START, EMAIL_SEND_HOUR_END,
)

log = structlog.get_logger()


def send_cold_email(
    to_email: str,
    to_name: str,
    subject: str,
    body: str,
    lead_id: int,
    variant: str,
) -> bool:
    """
    Send a cold email via SendGrid.
    Enforces daily limit and 8am–11am recipient local time window.
    Logs send event to OutreachEvent table.
    TODO: implement SendGrid API call + timezone scheduling.
    """
    raise NotImplementedError
