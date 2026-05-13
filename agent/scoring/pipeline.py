"""
Full scoring pipeline: classify → enrich → score → deduplicate → persist Leads.

Flow per daily run:
  1. Receive new Signal records from signal detection
  2. Classify each with Claude Haiku (better vertical/type, noise filter, size hint)
  3. Group by agency; for each agency enrich (tool scan + size extraction)
  4. Score every signal for the agency; pick the highest-scoring one as the lead
  5. Dedup: if a Lead for this agency already exists and was scored recently, skip
  6. Persist one Lead record per agency into the DB with full score breakdown
  7. Return bucketed output: proceed / watchlist / discarded
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import structlog

from db import get_session
from db.models import Signal, Lead, LeadStatus
from agent.scoring.scorer import score_lead, ScoringInput, ScoringResult
from agent.scoring.haiku_classifier import classify_signals, ClassificationResult
from agent.scoring.enricher import enrich_agency, EnrichmentResult
from config.settings import SCORE_PROCEED, SCORE_WATCHLIST, DEDUP_WINDOW_DAYS

log = structlog.get_logger()


@dataclass
class ScoredLead:
    signal: Signal
    classification: ClassificationResult
    enrichment: EnrichmentResult
    score_result: ScoringResult
    lead: Lead


@dataclass
class PipelineOutput:
    proceed: list[ScoredLead] = field(default_factory=list)
    watchlist: list[ScoredLead] = field(default_factory=list)
    discarded: list[ScoredLead] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.proceed) + len(self.watchlist) + len(self.discarded)


def run_scoring_pipeline(new_signals: list[Signal]) -> PipelineOutput:
    """
    Score a list of new Signal records.
    Returns PipelineOutput with leads bucketed into proceed / watchlist / discarded.
    """
    if not new_signals:
        log.info("scoring_pipeline_no_signals")
        return PipelineOutput()

    # ── Step 1: Haiku classification ─────────────────────────────────────────
    log.info("scoring_classify_start", count=len(new_signals))
    signal_dicts = [
        {"agency": s.agency_name, "source": s.source, "text": s.raw_text or ""}
        for s in new_signals
    ]
    classifications = classify_signals(signal_dicts)
    log.info("scoring_classify_done", classified=len(classifications))

    # Filter noise immediately
    valid_pairs: list[tuple[Signal, ClassificationResult]] = [
        (sig, cls)
        for sig, cls in zip(new_signals, classifications)
        if cls.is_id_agency
    ]
    noise_count = len(new_signals) - len(valid_pairs)
    if noise_count:
        log.info("scoring_noise_filtered", count=noise_count)

    # ── Step 2: Group by agency ───────────────────────────────────────────────
    by_agency: dict[str, list[tuple[Signal, ClassificationResult]]] = defaultdict(list)
    for sig, cls in valid_pairs:
        by_agency[sig.agency_name].append((sig, cls))

    # ── Step 3: Enrich + score per agency ─────────────────────────────────────
    session = get_session()
    output = PipelineOutput()

    # Load recently-scored leads to avoid re-creating duplicates
    cutoff = datetime.utcnow() - timedelta(days=DEDUP_WINDOW_DAYS)
    with session:
        recent_lead_agencies = {
            row[0]
            for row in session.query(Lead.agency_name)
            .filter(Lead.created_at >= cutoff)
            .filter(Lead.status != LeadStatus.suppressed)
            .all()
        }

    for agency_name, pairs in by_agency.items():
        all_texts = [sig.raw_text or "" for sig, _ in pairs]

        # Pick the Haiku team_size_hint from the signal most confident about it
        size_hints = [
            cls.team_size_hint
            for _, cls in pairs
            if cls.team_size_hint is not None
        ]
        haiku_size = min(size_hints) if size_hints else None  # conservative: take smallest plausible

        with session:
            enrichment = enrich_agency(
                agency_name=agency_name,
                all_signal_texts=all_texts,
                haiku_team_size_hint=haiku_size,
                db_session=session,
            )

        # Score every signal for this agency and pick the best one
        best: tuple[Signal, ClassificationResult, ScoringResult] | None = None
        for sig, cls in pairs:
            inp = ScoringInput(
                agency_name=agency_name,
                vertical=cls.vertical,
                team_size=enrichment.team_size,
                tool_stack=enrichment.tool_stack,
                signal_type=cls.signal_type,
                signal_detected_at=sig.detected_at,
            )
            result = score_lead(inp)

            if best is None or result.total > best[2].total:
                best = (sig, cls, result)

        if best is None:
            continue

        best_sig, best_cls, best_score = best
        log.info(
            "agency_scored",
            agency=agency_name,
            score=best_score.total,
            vertical=best_cls.vertical,
            tool_stack=enrichment.tool_stack,
            team_size=enrichment.team_size,
            size_source=enrichment.team_size_source,
        )

        # ── Step 4: Bucket and persist ────────────────────────────────────────
        if best_score.total >= SCORE_PROCEED:
            status = LeadStatus.researching
        elif best_score.total >= SCORE_WATCHLIST:
            status = LeadStatus.watchlist
        else:
            status = None   # discard

        with session:
            # Deduplicate: update existing lead if present, create if not
            existing = None
            if agency_name in recent_lead_agencies:
                existing = (
                    session.query(Lead)
                    .filter(Lead.agency_name == agency_name)
                    .filter(Lead.created_at >= cutoff)
                    .filter(Lead.status != LeadStatus.suppressed)
                    .order_by(Lead.created_at.desc())
                    .first()
                )

            if existing:
                # Only update if new score is better
                if best_score.total > (existing.score or 0):
                    existing.score = best_score.total
                    existing.vertical = best_cls.vertical
                    existing.tool_stack = enrichment.tool_stack
                    if status and existing.status not in (
                        LeadStatus.warm, LeadStatus.in_sequence, LeadStatus.content_ready
                    ):
                        existing.status = status
                    existing.updated_at = datetime.utcnow()
                    lead_record = existing
                else:
                    lead_record = existing
            else:
                lead_record = Lead(
                    agency_name=agency_name,
                    vertical=best_cls.vertical,
                    score=best_score.total,
                    status=status or LeadStatus.new,
                    tool_stack=enrichment.tool_stack,
                    trigger_signal_id=best_sig.id,
                    trigger_summary=best_sig.raw_text[:200] if best_sig.raw_text else "",
                )
                session.add(lead_record)

            best_sig.processed = True
            session.commit()

        scored_lead = ScoredLead(
            signal=best_sig,
            classification=best_cls,
            enrichment=enrichment,
            score_result=best_score,
            lead=lead_record,
        )

        if status == LeadStatus.researching:
            output.proceed.append(scored_lead)
        elif status == LeadStatus.watchlist:
            output.watchlist.append(scored_lead)
        else:
            output.discarded.append(scored_lead)

    log.info(
        "scoring_pipeline_complete",
        agencies=len(by_agency),
        proceed=len(output.proceed),
        watchlist=len(output.watchlist),
        discarded=len(output.discarded),
    )
    return output
