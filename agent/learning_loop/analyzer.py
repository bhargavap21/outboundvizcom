"""Weekly learning loop — performance analysis and prompt/weight recalibration."""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import json
import structlog
import anthropic

from config.settings import ANTHROPIC_API_KEY, MODEL_CONTENT
from db import get_session
from db.models import OutreachEvent, Lead

log = structlog.get_logger()
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run_weekly_analysis() -> str:
    """
    Analyse the prior week's outreach performance.
    Returns a markdown digest string and writes it to output/.
    """
    session = get_session()
    cutoff = datetime.utcnow() - timedelta(days=7)

    with session:
        events = session.query(OutreachEvent).filter(OutreachEvent.sent_at >= cutoff).all()
        leads = session.query(Lead).all()

    metrics = _compute_metrics(events)
    digest = _generate_digest(metrics, leads)
    _write_digest(digest)
    return digest


def _compute_metrics(events: list[OutreachEvent]) -> dict:
    total = len(events)
    opened = sum(1 for e in events if e.opened_at)
    replied = sum(1 for e in events if e.replied_at)

    by_variant: dict[str, dict] = {}
    for e in events:
        v = e.variant or "default"
        by_variant.setdefault(v, {"sent": 0, "opened": 0, "replied": 0})
        by_variant[v]["sent"] += 1
        if e.opened_at:
            by_variant[v]["opened"] += 1
        if e.replied_at:
            by_variant[v]["replied"] += 1

    return {
        "total_sent": total,
        "open_rate": round(opened / total, 3) if total else 0,
        "reply_rate": round(replied / total, 3) if total else 0,
        "by_variant": by_variant,
    }


def _generate_digest(metrics: dict, leads: list[Lead]) -> str:
    top_leads = sorted(
        [l for l in leads if l.score and l.score >= 65],
        key=lambda l: l.score,
        reverse=True,
    )[:10]

    top_leads_text = "\n".join(
        f"- {l.agency_name} (score {l.score}, vertical: {l.vertical})"
        for l in top_leads
    )

    prompt = f"""You are analyzing outreach performance for Vizcom's GTM agent.

Weekly metrics:
{json.dumps(metrics, indent=2)}

Top 10 scored leads this week:
{top_leads_text}

Write a concise markdown weekly digest that includes:
1. Key performance summary (open rate, reply rate)
2. Best and worst performing message variants
3. Which verticals showed the highest response rates
4. 2-3 concrete suggestions to improve next week

Keep it under 400 words."""

    response = _client.messages.create(
        model=MODEL_CONTENT,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def _write_digest(digest: str) -> None:
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    filename = out_dir / f"digest_{datetime.utcnow().strftime('%Y-%m-%d')}.md"
    filename.write_text(digest)
    log.info("digest_written", path=str(filename))
