"""Shared Apify client with retry logic and result iteration."""
from __future__ import annotations
from typing import Any
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from apify_client import ApifyClient
from apify_client.errors import ApifyApiError
from config.settings import APIFY_API_KEY

log = structlog.get_logger()

_client: ApifyClient | None = None

# Errors that indicate a permanent failure — do not retry these
_PERMANENT_ERROR_FRAGMENTS = (
    "must rent a paid Actor",
    "free trial has expired",
    "must be an object",       # actor-side null push bug; retrying won't help
    "Actor build not found",
    "Actor not found",
)


class PermanentActorError(Exception):
    """Raised for errors that should not be retried."""


def get_client() -> ApifyClient:
    global _client
    if _client is None:
        if not APIFY_API_KEY:
            raise RuntimeError("APIFY_API_KEY is not set")
        _client = ApifyClient(APIFY_API_KEY)
    return _client


def _is_permanent(exc: Exception) -> bool:
    msg = str(exc)
    return any(frag in msg for frag in _PERMANENT_ERROR_FRAGMENTS)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def run_actor(actor_id: str, run_input: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Run an Apify actor synchronously and return all dataset items.
    Retries up to 3x with exponential backoff on transient failures.
    Raises PermanentActorError immediately for paywall / actor bugs (no retry).
    """
    client = get_client()
    log.info("apify_actor_start", actor=actor_id)

    try:
        run = client.actor(actor_id).call(run_input=run_input)
    except Exception as exc:
        if _is_permanent(exc):
            raise PermanentActorError(str(exc)) from exc
        raise

    if run is None:
        raise RuntimeError(f"Apify actor {actor_id} returned no run object")

    # Actor-side failures (e.g. null push) surface as a FAILED run status
    if run.get("status") == "FAILED":
        raise PermanentActorError(
            f"Actor {actor_id} run {run.get('id')} ended in FAILED status"
        )

    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    log.info("apify_actor_complete", actor=actor_id, items=len(items))
    return items
