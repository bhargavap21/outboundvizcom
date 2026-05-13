# Vizcom: Design Agency Pitch Agent
**Track 2: Agentic GTM | Target Company: Vizcom**
Version 1.1 | For handoff to Claude Code

---

## 01 Company Overview

Vizcom turns rough sketches into photorealistic 3D renders in seconds. Built for physical product designers, not digital ones. A designer draws in Procreate or on paper, uploads it, and gets a material-accurate product visualization in real time. No rendering artist. No outsourcing. No KeyShot export queue.

**The growth problem:** Design agencies win or lose pitches based on how many concept directions they can show. Traditional rendering creates a hard ceiling: teams sketch 50 ideas, render 4, and the client picks from 4. Vizcom removes that ceiling. Most boutique agencies have never heard of it.

---

## 02 Ideal Customer Profile

**Who:** Design Director or Creative Lead at a boutique industrial design consultancy.

| Attribute | Spec |
|---|---|
| Company size | 10 to 25 people (sweet spot). 5 to 50 is workable. |
| Verticals | Footwear, consumer electronics, furniture. These three first. |
| Geography | US, UK, Germany, Netherlands, Australia |
| Current tools | KeyShot or Rhino in employee LinkedIn profiles = high priority |
| Pain trigger | Pitches new business 3 to 6x per year. Render budget is a real constraint. |
| Not a fit | Medical device firms, 100+ person studios with dedicated render pipelines, pure UX/digital agencies |

**Why this ICP:** Pain is financially quantifiable. Trigger is publicly detectable. Design Directors are active on LinkedIn and ArtStation. Agency designers refer tools to each other constantly, so one win compounds.

---

## 03 What the Agent Does

Monitors the web for signals that a boutique ID agency is actively pitching new business. When it detects a qualifying signal, it researches the agency, scores the lead, and generates personalized outreach across a coordinated channel sequence. Tracks responses and retrains its scoring weekly.

**Inputs:**
- LinkedIn job postings (new designer hires = active pipeline signal)
- Behance / ArtStation new portfolio projects from agency accounts
- Core77, Dezeen, IDSA trade press (agency features, awards, project coverage)
- Seed list of ~500 boutique ID consultancies (IDSA directory, Dexigner, DesignRush)
- LinkedIn employee profiles (tool stack signals: KeyShot, Rhino, Alias)

**Outputs:**
- Lead scorecard (JSON: agency, score, vertical, contact, trigger event)
- Cold email with two subject line variants
- ArtStation/Behance comment (pre-email, no pitch)
- LinkedIn connection note + 3-message DM sequence
- Physical mailer spec (for 80+ score leads only, dispatched via Lob)
- CRM log entry + weekly performance digest

---

## 04 Lead Scoring

Scored 0 to 100. Leads >= 65 proceed to outreach. Leads 40 to 64 enter watch list.

| Dimension | Weight | Logic |
|---|---|---|
| Vertical fit | 25 pts | Footwear/electronics/furniture = 25. Automotive = 15. Medical = 5. |
| Company size | 20 pts | 10 to 25 = 20. 5 to 10 or 25 to 50 = 12. Outside range = 0. |
| Tool signal | 20 pts | KeyShot/Rhino in employee profiles = 20. No signal = 5. |
| Signal recency | 20 pts | Under 7 days = 20. 7 to 14 days = 12. 14 to 30 days = 5. |
| Signal strength | 15 pts | New client win = 15. Case study = 12. Job post = 8. Portfolio update = 5. |

**Note on weights:** These are informed priors, not trained values. Run for 6 weeks, collect reply rates by dimension, regress against outcomes, and reweight. Vertical fit and tool signal are likely the most predictive. Company size is a proxy and will need the most adjustment.

---

## 05 Channel Sequence

Channels run in a coordinated sequence, not in parallel. Each touch warms the next.

| Day | Channel | Action |
|---|---|---|
| 0 | Signal detected | Agency posts case study, new portfolio project, or junior designer job listing |
| 1 | Behance / ArtStation | Agent posts a specific, opinionated comment on their new project. No pitch. No link. |
| 3 | Cold email | Sent to Design Director. References the specific project. Closes with a question. |
| 7 | LinkedIn | Connection request with short note referencing the same project |
| 14 | LinkedIn DM | Follow-up sharing something useful in their vertical. No hard ask. |
| 25 to 28 | Physical mailer | 80+ score leads only. Printed before/after render in their vertical, dispatched via Lob. |
| 30 | Final email | Short. Acknowledges they may not be the right fit. Leaves the door open. |

**Why physical mail:** Response gap between physical mail and email is approximately 36x by current ANA/DMA benchmarks. Dimensional mail achieves near-100% open rates. For a creative ICP that handles physical objects professionally, a well-designed printed piece lands differently than any digital message. Gate it to 80+ score leads to control cost ($5 to $15 per piece vs. fractions of a cent for email).

**Why portfolio comments first:** When an agency posts new work on Behance or ArtStation, they are in creator mode, not inbox mode. A thoughtful peer-level comment builds name recognition before the email arrives. The email then lands warmer. Bad generic comments are publicly visible, so voice discipline here matters more than anywhere else.

---

## 06 Voice and Messaging

### What Vizcom actually sounds like

Vizcom writes like a designer, not a SaaS company. From their own mission writing: "Once, design was raw, untamed. A pen in hand, an idea sparked." Short sentences. Sensory specifics. They never lead with AI. They lead with the designer's frustration. The CEO is an ex-Honda, ex-Nvidia industrial designer. The company writes like someone who has actually used KeyShot and found it exhausting.

**Voice rules for all agent-generated content:**
- Open with an observation that proves you looked, not a compliment that could apply to anyone
- Name the pain as something felt, not a statistic
- Never say: "caught my eye", "love to connect", "workflow session", "seamless", "game-changing", "revolutionary"
- Never mention AI, machine learning, or technology
- Tone check: would a senior ID director forward this to a colleague, or delete it?

### Claude prompt for cold email generation

```
You are writing outreach on behalf of Vizcom, a rendering
tool built by industrial designers for industrial designers.

Vizcom's voice: peer-to-peer, not vendor-to-customer.
Specific and sensory, never generic. Short sentences with
weight. Never lead with AI. Write like someone who has
actually used KeyShot and found it exhausting.

Agency context:
- Name: [agency_name]
- Contact: [contact_name], [title]
- Recent work: [specific_project] in [material/category]
- Observed detail: [one specific design decision from portfolio]
- Tool signal: [KeyShot/Rhino/outsourced]
- Vertical: [footwear/electronics/furniture]

Write a 130 to 150 word cold email that:
1. Opens with one specific, opinionated observation about
   their actual work. Not a compliment. Something you can
   only say if you actually looked.
2. Names the render bottleneck as something they feel,
   in the language of their craft. Not a stat.
3. References one real Vizcom customer in their vertical
   by name with a single concrete detail.
4. Closes with a question that invites pushback, not a
   meeting request.

Banned words: "caught my eye", "love to connect",
"workflow session", "I noticed", "seamless",
"game-changing", "revolutionary", "reach out", "AI",
"machine learning", "technology".

Generate two subject line variants.
One is a question. One is a fragment that creates tension.
```

### Sample output (Whipsaw, consumer electronics)

**Subject A:** How many renders were in your last pitch deck?
**Subject B:** You sketched 30. You showed 4.

---

Dan,

The temple-to-cup junction on your headphone project is the kind of decision that only gets made by someone who has actually held a bad pair. It is considered in a way most concept work is not.

Quick question: how many render variations did you show the client before landing on that direction?

Every studio I talk to has the same problem. You sketch 30 directions, you render 4, and the client picks from 4. The constraint is never ideas.

New Balance's footwear team cut their colorway review cycle in half. Breville uses it before committing to a single physical sample.

Curious whether your render cycle is actually the bottleneck, or whether it sits somewhere else in your process.

[Name]

---

## 07 Technical Stack

| Component | Tool |
|---|---|
| Orchestration | Python (APScheduler for daily detection, weekly learning loop) |
| LinkedIn signals | LinkedIn Jobs API + Apify scraper |
| Portfolio signals | Playwright headless browser (Behance, ArtStation) |
| Trade press | RSS feeds: Core77, Dezeen + Google News API |
| LLM: classification | `claude-haiku-4-5` (~200 calls/day, ~300 in / 50 out tokens) |
| LLM: scoring + brief | `claude-haiku-4-5` (~30 calls/day, ~800 in / 400 out tokens) |
| LLM: email + DM copy | `claude-sonnet-4-20250514` (~30 calls/day, ~600 in / 500 out tokens) |
| Database | SQLite (dev) -> PostgreSQL (prod) |
| Email sending | SendGrid (warmed subdomain, not vizcom.com) |
| LinkedIn outreach | Phantombuster (within ToS rate limits) |
| Physical mail | Lob API (automated print + ship) |
| CRM | HubSpot API or CSV export |

**Key constraints:**
- LinkedIn: max 20 connection requests/day per account
- Email: max 40 cold sends/day. Monday and Wednesday sends at 8 to 11am local time outperform.
- Physical mail: gate to 80+ score only. Use a fulfillment partner that can match mail drops to digital campaign timing.
- GDPR/CAN-SPAM: unsubscribe link in every email. Log all consent signals.

---

## 08 Response Handling

| Response | Action |
|---|---|
| Positive | Pause all sequences. Flag for human SDR. Log as warm. |
| Objection | Generate tailored reply draft via Claude. Human reviews before sending. |
| Unsubscribe | Immediate suppression. Log reason. Feed back to scoring model. |
| No response | Mark exhausted after full sequence. 90-day cooling period. |
| Bounce | Flag for manual verification. Route to LinkedIn channel instead. |

---

## 09 Learning Loop (weekly, every Sunday)

- Open rate by subject line variant: promote top, retire bottom
- Reply rate by vertical: adjust scoring weights
- Reply rate by signal type: recalibrate which triggers are most predictive
- Conversion by channel: identify whether email, comment, or LinkedIn touch is driving replies
- Output: markdown digest with top 10 leads, key metrics, suggested weight changes

---

## 10 Success Metrics

| Metric | Month 1 | Month 3 |
|---|---|---|
| Qualified leads/week | 15 to 20 | 40 to 60 |
| Email open rate | >35% | >45% |
| Email reply rate | >5% | >8% |
| LinkedIn connection acceptance | >30% | >40% |
| Demos/calls booked | 3 to 5/month | 10 to 15/month |
| Cost per qualified lead | <$2.00 | <$1.00 |

**What breaks first:** LinkedIn automation accounts flagged for rate limit violations. Mitigate with careful throttling, account warming, and human review of edge cases. Email deliverability on a new domain takes 4 to 6 weeks to stabilize. Start warming the sending domain before the agent goes live.

**Biggest improvement with more time:** Add a vision model to score Behance render quality. Agencies whose public renders look rough are higher-priority targets than agencies whose renders look polished. That signal is currently unavailable without a human looking at each portfolio.
