"""Shared Apify client with retry logic and result iteration."""
from __future__ import annotations
from typing import Any, Generator
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from apify_client import ApifyClient
from config.settings import APIFY_API_KEY

log = structlog.get_logger()

_client: ApifyClient | None = None


def get_client() -> ApifyClient:
    global _client
    if _client is None:
        if not APIFY_API_KEY:
            raise RuntimeError("APIFY_API_KEY is not set")
        _client = ApifyClient(APIFY_API_KEY)
    return _client


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
    """
    client = get_client()
    log.info("apify_actor_start", actor=actor_id)

    run = client.actor(actor_id).call(run_input=run_input)
    if run is None:
        raise RuntimeError(f"Apify actor {actor_id} returned no run object")

    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    log.info("apify_actor_complete", actor=actor_id, items=len(items))
    return items
