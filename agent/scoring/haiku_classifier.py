"""
Claude Haiku signal classification.
Replaces keyword-only matching with structured LLM extraction for:
  - Vertical detection (nuanced, handles synonyms keyword maps miss)
  - Signal type reclassification
  - Team size hint extraction from text
  - Noise filtering (e.g. financial "whipsaw", non-ID agencies)

Uses claude-haiku-4-5 for high-volume, low-cost classification.
Batches up to BATCH_SIZE signals per API call to minimise latency.
"""
from __future__ import annotations
import json
import structlog
import anthropic
from dataclasses import dataclass, field
from typing import Optional

from config.settings import ANTHROPIC_API_KEY, MODEL_SCORING

log = structlog.get_logger()
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

BATCH_SIZE = 10  # signals per Haiku call

VALID_VERTICALS = {
    "footwear", "consumer electronics", "furniture",
    "home goods", "apparel accessories", "automotive", "other",
}
VALID_SIGNAL_TYPES = {"client_win", "case_study", "new_hire", "portfolio_update"}


@dataclass
class ClassificationResult:
    is_id_agency: bool          # False → discard as noise
    vertical: str               # one of VALID_VERTICALS
    signal_type: str            # one of VALID_SIGNAL_TYPES
    team_size_hint: Optional[int] = None   # extracted from text if mentioned
    confidence: str = "medium"  # low | medium | high


def classify_signals(
    signals: list[dict],   # [{"agency": str, "source": str, "text": str}, ...]
) -> list[ClassificationResult]:
    """
    Classify a batch of signals with a single Haiku call.
    Returns one ClassificationResult per input signal (same order).
    Falls back to keyword defaults on any API failure.
    """
    if not signals:
        return []

    results: list[ClassificationResult] = []
    for i in range(0, len(signals), BATCH_SIZE):
        batch = signals[i : i + BATCH_SIZE]
        batch_results = _classify_batch(batch)
        results.extend(batch_results)
    return results


def _classify_batch(batch: list[dict]) -> list[ClassificationResult]:
    numbered = "\n\n".join(
        f"[{idx + 1}] agency={s['agency']} source={s['source']}\n{s['text'][:400]}"
        for idx, s in enumerate(batch)
    )

    prompt = f"""You are classifying signals from a GTM system targeting boutique industrial design (ID) agencies.

For each numbered signal below, output a JSON object on one line with these keys:
- "is_id_agency": true if the signal is genuinely from/about an industrial design or product design agency; false for noise (financial articles, wrong industry, etc.)
- "vertical": the primary design vertical — one of: footwear, consumer electronics, furniture, home goods, apparel accessories, automotive, other
- "signal_type": one of: client_win, case_study, new_hire, portfolio_update
- "team_size_hint": integer if the text explicitly mentions company/team headcount, otherwise null
- "confidence": "high" if clear, "medium" if inferred, "low" if uncertain

Output exactly {len(batch)} lines of JSON, one per signal, numbered 1-{len(batch)}.
Format: {{"n": 1, "is_id_agency": true, "vertical": "footwear", "signal_type": "case_study", "team_size_hint": null, "confidence": "high"}}

Signals:
{numbered}"""

    try:
        response = _client.messages.create(
            model=MODEL_SCORING,
            max_tokens=150 * len(batch),
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_batch_response(response.content[0].text, len(batch))
    except Exception as e:
        log.error("haiku_classifier_failed", error=str(e), batch_size=len(batch))
        return [_fallback(s) for s in batch]


def _parse_batch_response(text: str, expected: int) -> list[ClassificationResult]:
    results: list[ClassificationResult] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
            vertical = obj.get("vertical", "other")
            signal_type = obj.get("signal_type", "portfolio_update")
            results.append(ClassificationResult(
                is_id_agency=bool(obj.get("is_id_agency", True)),
                vertical=vertical if vertical in VALID_VERTICALS else "other",
                signal_type=signal_type if signal_type in VALID_SIGNAL_TYPES else "portfolio_update",
                team_size_hint=_parse_int(obj.get("team_size_hint")),
                confidence=obj.get("confidence", "medium"),
            ))
        except (json.JSONDecodeError, KeyError):
            results.append(_default_result())

    # Pad with defaults if parsing returned fewer rows than expected
    while len(results) < expected:
        results.append(_default_result())
    return results[:expected]


def _fallback(signal: dict) -> ClassificationResult:
    """Keyword-based fallback when Haiku is unavailable."""
    from agent.signal_detection.classifier import classify_signal_type, extract_vertical_hint
    return ClassificationResult(
        is_id_agency=True,
        vertical=extract_vertical_hint(signal.get("text", "")) or "other",
        signal_type=classify_signal_type(signal.get("text", ""), signal.get("source", "")),
        team_size_hint=None,
        confidence="low",
    )


def _default_result() -> ClassificationResult:
    return ClassificationResult(
        is_id_agency=True,
        vertical="other",
        signal_type="portfolio_update",
        confidence="low",
    )


def _parse_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        v = int(value)
        return v if 1 <= v <= 500 else None
    except (TypeError, ValueError):
        return None
