"""
End-to-end pipeline test: signal detection → scoring → summary report.
Uses a curated seed list of boutique ID agencies that fit the ICP.
Run with: .venv/bin/python scripts/test_pipeline.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich import box

from db import init_db, get_session
from db.models import Signal, Lead, LeadStatus
from agent.signal_detection.runner import run_signal_detection
from agent.scoring.scorer import score_lead, ScoringInput
from agent.scoring.pipeline import run_scoring_pipeline
from config.settings import SCORE_PROCEED, SCORE_WATCHLIST

console = Console()

# ── Seed list: boutique ID agencies matching the ICP ──────────────────────
# linkedin_slug is the /company/<slug>/ portion of their LinkedIn URL
SEED_AGENCIES = [
    {"name": "Whipsaw",          "linkedin_slug": "whipsaw-inc"},
    {"name": "Ammunition Group", "linkedin_slug": "ammunition-group"},
    {"name": "Bould Design",     "linkedin_slug": "bould-design"},
    {"name": "Layer",            "linkedin_slug": "layer-design"},
    {"name": "Morrama",          "linkedin_slug": "morrama"},
    {"name": "Priority Designs", "linkedin_slug": "priority-designs"},
    {"name": "Fuseproject",      "linkedin_slug": "fuseproject"},
    {"name": "Ziba Design",      "linkedin_slug": "ziba"},
    {"name": "Map Project Office", "linkedin_slug": "map-project-office"},
    {"name": "PDD",              "linkedin_slug": "pdd-innovation"},
]

AGENCY_NAMES = [a["name"] for a in SEED_AGENCIES]
AGENCY_LINKEDIN_URLS = {
    a["name"]: f"https://www.linkedin.com/company/{a['linkedin_slug']}/"
    for a in SEED_AGENCIES
}


def patch_linkedin_urls():
    """
    Monkey-patch the linkedin helper to use real slugs from our seed list
    instead of the auto-generated best-guess slugs.
    """
    import agent.signal_detection.linkedin as li_mod
    def _real_linkedin_url(agency_name: str) -> str:
        return AGENCY_LINKEDIN_URLS.get(agency_name,
            f"https://www.linkedin.com/company/{agency_name.lower().replace(' ', '-')}/")
    li_mod._linkedin_company_url = _real_linkedin_url


def run_and_score() -> list[dict]:
    console.rule("[bold cyan]Step 1 — Signal Detection[/bold cyan]")
    console.print(f"Agencies: {', '.join(AGENCY_NAMES)}\n")

    patch_linkedin_urls()

    signals = run_signal_detection(AGENCY_NAMES)
    console.print(f"\n[green]✓ {len(signals)} new signals persisted to DB[/green]\n")

    console.rule("[bold cyan]Step 2 — Scoring[/bold cyan]")
    scored = []
    for signal in signals:
        inp = ScoringInput(
            agency_name=signal.agency_name,
            vertical=signal.vertical_hint or "",
            team_size=None,
            tool_stack=[],
            signal_type=signal.signal_type,
            signal_detected_at=signal.detected_at,
        )
        result = score_lead(inp)

        if result.total >= SCORE_PROCEED:
            bucket = "[bold green]PROCEED[/bold green]"
        elif result.total >= SCORE_WATCHLIST:
            bucket = "[yellow]WATCHLIST[/yellow]"
        else:
            bucket = "[dim]DISCARD[/dim]"

        scored.append({
            "agency":    signal.agency_name,
            "source":    signal.source,
            "type":      signal.signal_type,
            "vertical":  signal.vertical_hint or "—",
            "score":     result.total,
            "bucket":    bucket,
            "url":       signal.url,
            "snippet":   (signal.raw_text or "")[:120],
        })

    return sorted(scored, key=lambda x: x["score"], reverse=True)


def print_report(scored: list[dict]):
    console.rule("[bold cyan]Step 3 — Lead Report[/bold cyan]")

    table = Table(box=box.ROUNDED, show_lines=True)
    table.add_column("Agency",    style="bold", max_width=20)
    table.add_column("Source",    max_width=14)
    table.add_column("Vertical",  max_width=18)
    table.add_column("Tools",     max_width=14)
    table.add_column("Size",      justify="right", max_width=6)
    table.add_column("Score",     justify="right", max_width=6)
    table.add_column("Breakdown", max_width=30)
    table.add_column("Bucket",    max_width=12)

    for r in scored:
        bd = r.get("breakdown", {})
        breakdown_str = (
            f"v={bd.get('vertical',0)} s={bd.get('size',0)} "
            f"t={bd.get('tool',0)} r={bd.get('recency',0)} str={bd.get('strength',0)}"
            if bd else ""
        )
        table.add_row(
            r["agency"],
            r["source"],
            r["vertical"],
            r.get("tools", "—"),
            str(r.get("team_size") or "?"),
            str(r["score"]),
            breakdown_str,
            r["bucket"],
        )

    console.print(table)

    proceed  = [r for r in scored if r["score"] >= SCORE_PROCEED]
    watchlist = [r for r in scored if SCORE_WATCHLIST <= r["score"] < SCORE_PROCEED]
    discard  = [r for r in scored if r["score"] < SCORE_WATCHLIST]

    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  [green]PROCEED[/green]   {len(proceed)} leads  (≥{SCORE_PROCEED})")
    console.print(f"  [yellow]WATCHLIST[/yellow] {len(watchlist)} leads  ({SCORE_WATCHLIST}–{SCORE_PROCEED-1})")
    console.print(f"  [dim]DISCARD[/dim]   {len(discard)} leads  (<{SCORE_WATCHLIST})")

    if proceed:
        console.rule("[bold green]Top Proceed Leads[/bold green]")
        for r in proceed[:5]:
            console.print(f"\n[bold]{r['agency']}[/bold]  score={r['score']}  [{r['source']} / {r['type']}]")
            console.print(f"  Vertical: {r['vertical']}")
            console.print(f"  URL:      {r['url']}")
            console.print(f"  Snippet:  {r['snippet']}...")


def save_json(scored: list[dict]):
    os.makedirs("output", exist_ok=True)
    out = f"output/test_run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out, "w") as f:
        json.dump(scored, f, indent=2, default=str)
    console.print(f"\n[dim]Full results saved to {out}[/dim]")


def score_existing_db() -> list[dict]:
    """
    Run full scoring pipeline (Haiku classify + enrich + score) on all
    unprocessed signals in DB. Creates/updates Lead records.
    """
    console.rule("[bold cyan]Step 2 — Full scoring pipeline (Haiku + enrichment)[/bold cyan]")
    session = get_session()
    signals = session.query(Signal).filter(Signal.processed == False).all()  # noqa: E712
    session.close()

    if not signals:
        console.print("[yellow]No unprocessed signals in DB. Re-scoring all signals...[/yellow]")
        session = get_session()
        signals = session.query(Signal).all()
        session.close()

    console.print(f"Running pipeline on {len(signals)} signals...\n")
    output = run_scoring_pipeline(signals)

    scored = []

    def _add(leads, bucket_label):
        for sl in leads:
            scored.append({
                "agency":    sl.signal.agency_name,
                "source":    sl.signal.source,
                "type":      sl.classification.signal_type,
                "vertical":  sl.classification.vertical,
                "score":     sl.score_result.total,
                "bucket":    bucket_label,
                "team_size": sl.enrichment.team_size,
                "tools":     ", ".join(sl.enrichment.tool_stack) or "—",
                "size_src":  sl.enrichment.team_size_source,
                "url":       sl.signal.url,
                "snippet":   (sl.signal.raw_text or "")[:120],
                "breakdown": {
                    "vertical":  sl.score_result.vertical_score,
                    "size":      sl.score_result.size_score,
                    "tool":      sl.score_result.tool_score,
                    "recency":   sl.score_result.recency_score,
                    "strength":  sl.score_result.strength_score,
                },
            })

    _add(output.proceed,   "[bold green]PROCEED[/bold green]")
    _add(output.watchlist, "[yellow]WATCHLIST[/yellow]")
    _add(output.discarded, "[dim]DISCARD[/dim]")

    return sorted(scored, key=lambda x: x["score"], reverse=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true",
                        help="Run live Apify signal detection before scoring")
    args = parser.parse_args()

    console.rule("[bold magenta]Vizcom GTM Agent — Pipeline Test[/bold magenta]")
    init_db()

    if args.fetch:
        scored = run_and_score()
    else:
        scored = score_existing_db()

    print_report(scored)
    save_json(scored)
