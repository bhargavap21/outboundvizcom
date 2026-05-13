# Vizcom GTM Agent

An agentic outbound pipeline that monitors the web for signals that boutique industrial design agencies are actively pitching new business — then researches, scores, and generates personalized outreach automatically.

Built as Track 2 of the BSV AI Fellow written project.

**Repo:** [github.com/bhargavap21/outboundvizcom](https://github.com/bhargavap21/outboundvizcom)

---

## What It Does

Design agencies win or lose pitches based on how many concept directions they can show. Traditional rendering creates a hard ceiling: teams sketch 50 ideas, render 4, and the client picks from 4. Vizcom removes that ceiling — but most boutique agencies have never heard of it.

This agent monitors public signals (LinkedIn posts, Behance updates, trade press) to find agencies that are actively pitching, scores them against a weighted rubric, and generates personalized multi-channel outreach without human involvement.

---

## Pipeline Overview

```
Signal Detection → Scoring → Research → Content Generation → Distribution → Response Handling
      (daily)       (daily)   (per lead)     (per lead)        (daily)        (inbound)
```

| Step | Module | What it does |
|------|--------|-------------|
| 1. Signal Detection | `agent/signal_detection/` | Scrapes LinkedIn posts, Behance, Core77/Dezeen RSS, Google News for qualifying signals |
| 2. Scoring | `agent/scoring/` | Haiku classifies signals → enriches with team size/tools → scores 0–100 across 5 dimensions |
| 3. Research | `agent/research/` | Scrapes website, LinkedIn, Behance, news → Haiku synthesizes into structured `AgencyBrief` |
| 4. Content Generation | `agent/content/` | Sonnet generates all 5 outreach pieces per lead using spec-enforced voice rules |
| 5. Distribution | `agent/distribution/` | Sequence dispatcher advances leads through timed channel steps via SendGrid + Phantombuster |
| 6. Response Handling | `agent/response_handler/` | Haiku classifies inbound replies → routes warm leads, objections, unsubscribes, bounces |
| 7. Learning Loop | `agent/learning_loop/` | Weekly Sonnet digest: open/reply rates by variant, suggested scoring weight changes |

---

## Lead Scoring

Scored 0–100. ≥65 proceeds to outreach. 40–64 enters watchlist.

| Dimension | Weight | Logic |
|-----------|--------|-------|
| Vertical fit | 25 pts | Footwear / electronics / furniture = 25. Automotive = 15. Medical = 5. |
| Company size | 20 pts | 10–25 employees = 20. 5–10 or 25–50 = 12. Outside range = 0. |
| Tool signal | 20 pts | KeyShot or Rhino detected = 20. No signal = 5. |
| Signal recency | 20 pts | <7 days = 20. 7–14 days = 12. >14 days = 5. |
| Signal strength | 15 pts | New client win = 15. Case study = 12. Job post = 8. Portfolio update = 5. |

---

## Channel Sequence

Each touch warms the next. Channels run in sequence, not parallel.

| Day | Channel | Action |
|-----|---------|--------|
| 1 | Behance/ArtStation | Opinionated comment on their new project. No pitch, no link. |
| 3 | Cold email | Sent to Design Director. Specific project observation. Closes with a question. |
| 7 | LinkedIn | Connection request with short personalised note. |
| 14 | LinkedIn DM | Useful vertical insight. No ask. |
| 25–28 | Physical mailer | 80+ score leads only. Lob API. *(not yet implemented)* |
| 30 | Final email | Acknowledges may not be right fit. Leaves door open. |

---

## Content Voice Rules

All outreach enforces Vizcom's peer-to-peer voice at the prompt level:

- Open with an observation that proves you looked — not a compliment
- Name the pain as something felt, not a statistic
- Reference a real Vizcom customer by name with one concrete detail
- Close with a question that invites pushback, not a meeting request
- **Banned:** "caught my eye", "love to connect", "workflow session", "seamless", "game-changing", "AI", "machine learning", "technology"

---

## Project Structure

```
agent/
├── signal_detection/
│   ├── runner.py          # Orchestrates all signal collectors
│   ├── linkedin.py        # LinkedIn posts + job postings via Apify
│   ├── behance.py         # Behance portfolio signals via Apify
│   ├── trade_press.py     # Core77, Dezeen RSS + Google News
│   ├── classifier.py      # Keyword-based signal type + vertical extraction
│   └── apify_client.py    # Shared Apify runner with retry + permanent error handling
│
├── scoring/
│   ├── pipeline.py        # End-to-end: classify → enrich → score → persist
│   ├── haiku_classifier.py # Batch Haiku classification (10 signals/call)
│   ├── enricher.py        # Team size + tool stack enrichment from DB + text scan
│   └── scorer.py          # 5-dimension weighted scoring (pure functions)
│
├── research/
│   ├── researcher.py      # Orchestrates all scrapers → synthesizer
│   ├── brief.py           # AgencyBrief dataclass
│   ├── website_scraper.py # httpx + BeautifulSoup: team, tools, contacts
│   ├── linkedin_scraper.py # DB signals + harvestapi/linkedin-company Apify actor
│   ├── behance_scraper.py # easyapi/behance-people-scraper Apify actor
│   ├── news_scraper.py    # Google News RSS: client wins, awards, press
│   └── synthesizer.py     # Haiku synthesizes raw sources → structured AgencyBrief
│
├── content/
│   └── generator.py       # Sonnet: Behance comment, cold email (A/B), connection
│                          #         note, Day-14 DM, Day-30 final email
│
├── distribution/
│   ├── sequence_dispatcher.py # Day-based orchestrator, DB-backed idempotency
│   ├── email_sender.py    # SendGrid: 40/day cap, send window, A/B variant, CAN-SPAM
│   └── linkedin_sender.py # Phantombuster: 20 connects/day, DM after connection
│
├── response_handler/
│   └── handler.py         # Haiku classifies replies → warm/objection/unsub/bounce
│                          # Slack alerts, objection drafts, 90-day cooldown
│
├── learning_loop/
│   └── analyzer.py        # Weekly Sonnet digest: open/reply rates, weight suggestions
│
└── main.py                # APScheduler: daily pipeline + Sunday learning loop

config/settings.py         # All env vars, model names, rate limits, actor IDs
db/models.py               # SQLAlchemy: Signal, Lead, OutreachEvent, AgencyList
scripts/
├── seed_agency_list.py    # Seeds 10 test agencies with real data
├── test_pipeline.py       # Score existing DB signals, show per-lead breakdown
├── test_research.py       # Run research on PROCEED leads, print AgencyBrief
├── test_content.py        # Run full research + content gen, print all 5 pieces
└── verify_actors.py       # Verify Apify auth + actor IDs (no paid runs)
```

---

## Tech Stack

| Component | Tool |
|-----------|------|
| Orchestration | Python + APScheduler |
| LinkedIn signals | Apify `data-slayer/linkedin-company-posts-scraper` |
| Behance signals | Apify `easyapi/behance-people-scraper` |
| Trade press | feedparser + httpx (Core77, Dezeen, Google News RSS) |
| Website scraping | httpx + BeautifulSoup4 |
| LinkedIn enrichment | Apify `harvestapi/linkedin-company` |
| LLM: classification + scoring | `claude-haiku-4-5` |
| LLM: email + DM copy | `claude-sonnet-4-20250514` |
| Database | SQLite (dev) → PostgreSQL (prod) |
| Email sending | SendGrid |
| LinkedIn outreach | Phantombuster |
| Physical mail | Lob API *(not yet implemented)* |

---

## Setup

**1. Clone and install**
```bash
git clone https://github.com/bhargavap21/outboundvizcom.git
cd outboundvizcom
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Configure environment**
```bash
cp .env.example .env
# Fill in your keys (see below)
```

Required in `.env`:
```
ANTHROPIC_API_KEY=
APIFY_API_KEY=
SENDGRID_API_KEY=
OUTBOUND_EMAIL_FROM=outreach@yourdomain.com
PHANTOMBUSTER_API_KEY=
SLACK_WEBHOOK_URL=          # optional — for warm lead + bounce alerts
```

**3. Initialise the database**
```bash
python -m db
python scripts/seed_agency_list.py
```

**4. Verify Apify actors**
```bash
python scripts/verify_actors.py
```

**5. Run the scoring pipeline against existing signals**
```bash
python scripts/test_pipeline.py
```

**6. Run research on a PROCEED lead**
```bash
python scripts/test_research.py "Morrama"
```

**7. Generate full content package**
```bash
python scripts/test_content.py "Morrama"
```

---

## Running the Agent

```bash
# Start the full scheduled pipeline (daily signal detection + Sunday learning loop)
python -m agent.main
```

The daily job fires at 06:00 UTC. The learning loop fires every Sunday at 02:00 UTC.

---

## What's Working

- End-to-end signal-to-content pipeline verified on live data
- Morrama, Priority Designs, Whipsaw, Bould Design, Layer all surface in a single daily pass
- Haiku classification filters ~40% noise (financial articles, wrong industry)
- Research step identifies contact names (e.g. Jo Barnard / Morrama), verticals, recent projects
- Content generation enforces all voice rules at prompt level — no banned words in test output
- Sequence dispatcher advances leads through Day 3/7/14/30 with DB-backed idempotency

## Known Gaps

- **Seed list not loaded in main.py** — `SEED_AGENCIES = []`, needs one-line DB query fix
- **Tool stack detection pre-scoring** — enricher scans signal text only; news posts don't mention renderers, so tool dimension contributes minimum 5pts across all real leads
- **Behance comments not posted** — content is generated and stored, posting step not built
- **Physical mailer not built** — Lob API integration missing
- **No inbound webhook endpoint** — `handle_response()` exists but needs a Flask/FastAPI server for SendGrid Inbound Parse to call
- **Learning loop doesn't update weights** — produces digest but doesn't write back to `scorer.py`

---

## Models Used

| Use case | Model | Reason |
|----------|-------|--------|
| Signal classification (batch 10) | `claude-haiku-4-5` | ~200 calls/day, needs to be cheap |
| Agency brief synthesis | `claude-haiku-4-5` | ~30 calls/day, structured JSON output |
| Cold email + DM copy | `claude-sonnet-4-20250514` | Voice quality matters, ~30 calls/day |
| Objection reply drafts | `claude-sonnet-4-20250514` | Human reviews before sending |
| Weekly learning digest | `claude-sonnet-4-20250514` | Narrative synthesis, once/week |

---

*BSV AI Fellow — Track 2: Agentic GTM | May 2026*
