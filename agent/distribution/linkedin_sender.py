"""LinkedIn outreach via Phantombuster — connection requests and DMs."""
from __future__ import annotations
import structlog
from config.settings import PHANTOMBUSTER_API_KEY, LINKEDIN_CONNECT_DAILY_LIMIT

log = structlog.get_logger()


def send_connection_request(linkedin_url: str, note: str, lead_id: int) -> bool:
    """
    Send a LinkedIn connection request via Phantombuster.
    Enforces 20/day limit to avoid account suspension.
    TODO: implement Phantombuster API call.
    """
    raise NotImplementedError


def send_dm(linkedin_url: str, message: str, lead_id: int, sequence_step: int) -> bool:
    """
    Send a LinkedIn DM (only after connection accepted).
    TODO: implement Phantombuster API call.
    """
    raise NotImplementedError
