# Vizcom: Design Agency Pitch Agent
**Track 2: Agentic GTM | Target Company: Vizcom**
**Campaign: Design Agency Pitch Director Outreach Agent**
Version 1.0 | For handoff to Claude Code

---

## 01 Company Overview

### What is Vizcom?

Vizcom is an AI-powered design platform that turns rough sketches into photorealistic 3D renders in seconds. It sits at the intersection of industrial design software and generative AI, purpose-built for physical product designers, not digital or graphic designers.

Their core workflow: a designer uploads a hand sketch or tablet drawing, and Vizcom renders it as a polished, material-accurate product visualization in real time. Designers can iterate on materials, colorways, lighting, and proportions without waiting for a dedicated rendering artist or outsourcing to a render farm.

### Target Customers

| Customer Type | Description |
|---|---|
| Industrial design consultancies | Boutique agencies (5 to 50 people) pitching product concepts to brand clients in footwear, consumer electronics, furniture, and automotive |
| In-house design teams | Design departments at brands like New Balance, Skechers, Breville, and Tonal who need to iterate faster internally |
| Design educators and students | University programs teaching ID who need accessible rendering tools without KeyShot licensing costs |

### The Core Growth Problem

> **KEY INSIGHT:** Design agencies win or lose new business based on how many concept directions they can show in a pitch. Traditional rendering (KeyShot, outsourced render farms) creates a hard bottleneck: teams can sketch 50 ideas but only render 3 to 5 before the client meeting. Vizcom collapses this gap, but most boutique agencies have never heard of it.

The specific growth opportunity is outbound penetration of boutique industrial design consultancies. These firms:

- Have recurring, time-pressured pitch cycles (quarterly new business pitches)
- Are actively paying $100 to $500 per outsourced render today
- Are too small to be reached by enterprise sales, but too specialized for generic PLG
- Make buying decisions at the Design Director or Creative Lead level, reachable via LinkedIn
- Talk to each other, meaning one reference customer unlocks a network of peer referrals

---

## 02 Ideal Customer Profile (ICP)

### Primary ICP: Boutique ID Agency Pitch Director

| Attribute | Specification |
|---|---|
| Title | Design Director, Creative Lead, Principal Industrial Designer, Partner |
| Company type | Independent industrial design / product design consultancy |
| Company size | 5 to 50 employees (sweet spot: 10 to 25) |
| Verticals | Footwear, consumer electronics, furniture, home goods, apparel accessories |
| Geography | US, UK, Germany, Netherlands, Australia (English-first outreach) |
| Current tools | KeyShot, Rhino, SolidWorks, Procreate. Signals they feel the render bottleneck |
| Pain trigger | Pitching new business to brand clients 3 to 6x per year with limited render budget |
| Buying signal | New case study published, junior designer job posting, new client announcement |
| Not a fit | Pure UX/digital agencies, medical device specialists, 100+ person studios with dedicated render pipelines |

### Why This ICP Over Others

Vizcom has five solution verticals (gaming, footwear, automotive, apparel, industrial design). The boutique agency angle is the highest-leverage GTM wedge because:

- Pain is financially quantifiable. Losing a pitch because concepts looked rough costs real money.
- Trigger is detectable. Agencies signal new business activity publicly via case studies, job posts, and portfolio updates.
- Reachable at scale. Design Directors at boutique agencies are highly active on LinkedIn.
- Network effect. Agency designers move between firms and refer tools to each other.
- The pitch is the product demo. Showing more renders in a pitch IS the value proposition.

---

## 03 Agent Design

### What the Agent Does

> The agent monitors the web for signals that a boutique industrial design agency is actively pitching new business. When it detects a qualifying signal, it researches the agency, scores the lead, generates a personalized outreach message, and queues it for delivery. It then tracks responses and feeds results back to improve its targeting and messaging over time.

### Inputs: Data the Agent Needs

#### Signal Sources (monitored continuously)

| Source | What it captures |
|---|---|
| LinkedIn job postings API | New junior/mid designer roles at boutique ID agencies. Signals growth and active pipeline. |
| LinkedIn company feed | Case study posts, project announcements, client win announcements from agency accounts |
| Behance / ArtStation public feeds | New portfolio projects published by agency accounts. Reveals vertical and render quality. |
| Core77 / Dezeen / IDSA editorial | Agency features, awards, new project coverage in trade press |
| Google News alerts | "[Agency name] + design + [client category]". Catches client announcements. |

#### Reference Data (static, updated monthly)

- Seed list of ~500 boutique ID consultancies (sourced from IDSA firm directory, Dexigner, DesignRush)
- LinkedIn Sales Navigator filter: company size 5 to 50, industry = industrial design, country = target markets
- Known Vizcom customers (to exclude and use as social proof in nearby-firm outreach)
- Competitor tool list: firms mentioning KeyShot, Rhino, Alias in employee LinkedIn profiles are high-priority

### Outputs: What the Agent Produces

| Output | Description |
|---|---|
| Lead scorecard | Structured JSON with agency name, score (0 to 100), vertical, team size, trigger event, contact info |
| Personalized outreach email | ~150 word cold email referencing their specific vertical and recent work. Subject line A/B variants included. |
| LinkedIn connection note | ~280 char note personalized to their most recent project or case study |
| LinkedIn DM sequence | 3-message sequence: value comment, insight share, soft pitch |
| CRM log entry | Contact details, trigger signal, send date, response status. Exported to CSV or pushed to HubSpot. |
| Weekly digest | Top 10 scored leads, response rates by message variant, suggested template updates |

---

## 04 Step-by-Step Agent Workflow

### Step 1: Signal Detection (runs every 24 hours)

The agent runs scheduled scraping jobs across all signal sources. Each raw signal is parsed into a structured event object:

```json
{
  "agency_name": "",
  "source": "linkedin_job | linkedin_post | behance | trade_press",
  "signal_type": "new_hire | case_study | client_win | portfolio_update",
  "vertical_hint": "",
  "url": "",
  "timestamp": "",
  "raw_text": ""
}
```

Deduplication: events from the same agency within 14 days are collapsed into one lead record to avoid spam. Agencies already in an outreach sequence are suppressed.

### Step 2: Lead Scoring

Each agency event is scored 0 to 100 across five dimensions:

| Dimension | Weight | Scoring Logic |
|---|---|---|
| Vertical fit | 25 pts | Footwear/electronics/furniture = 25. Automotive = 15. Medical/industrial = 5. |
| Company size | 20 pts | 10 to 25 employees = 20. 5 to 10 or 25 to 50 = 12. Outside range = 0. |
| Tool signal | 20 pts | KeyShot/Rhino mention in employee profiles = 20. No signal = 5. |
| Signal recency | 20 pts | Signal < 7 days = 20. 7 to 14 days = 12. 14 to 30 days = 5. |
| Signal strength | 15 pts | New client win = 15. Case study = 12. Job post = 8. Portfolio update = 5. |

**Threshold:** Leads scoring >= 65 proceed to research. Leads 40 to 64 enter a watch list. Leads < 40 are discarded.

### Step 3: Deep Research (per qualified lead)

For each lead above threshold, the agent pulls and synthesizes:

- Agency website scrape: services, client logos, case studies, team page (designer count)
- LinkedIn company page: employee list, titles, tools mentioned in profiles
- Behance/ArtStation: last 5 projects. Extract vertical, render style, apparent tool used.
- News search: "[agency] + client". Any public client relationships or recent awards.

Output is a structured agency brief: vertical(s), team size, primary tool stack, estimated render volume, best contact name + LinkedIn URL, trigger event summary.

### Step 4: Content Generation

Using the agency brief, the agent generates three content assets via Claude API (`claude-sonnet-4-20250514`):

#### 4a. Cold Email

**Prompt template (abbreviated):**

```
You are a GTM specialist for Vizcom, an AI rendering tool for product designers.
Write a 140 to 160 word cold email to [contact_name] at [agency_name], a
[team_size]-person [vertical] design studio.

Their recent work: [recent_project_summary].
They appear to use [tool_hint] for rendering.

The email must:
1. Open with a specific observation about their work
2. Introduce the core pain: how many renders did they have in their last pitch deck?
3. State the value: agencies using Vizcom go from 3 to 5 renders per pitch to 40 to 50
4. Soft CTA: offer a 20-min workflow session, not a demo

Do not mention AI or machine learning.
Tone: direct, peer-to-peer, not salesy.
Generate two subject line variants.
```

#### 4b. LinkedIn Connection Note

280-character personalized connection request referencing their most recent published project. Tone: curious designer peer, not vendor.

#### 4c. LinkedIn DM Sequence (post-connect)

- **Message 1 (Day 3):** Share a relevant insight or render comparison relevant to their vertical. No ask.
- **Message 2 (Day 7):** Reference a specific Vizcom customer in their vertical with a one-line result.
- **Message 3 (Day 14):** Soft ask. "Would a 20-min workflow session be useful?" with calendar link.

### Step 5: Distribution and Sequencing

The agent queues all outreach through a sending layer with the following constraints:

- Email: max 40 new cold emails per day. Sent between 8am and 11am in recipient's local timezone.
- LinkedIn: max 20 connection requests per day. DMs only after connection accepted.
- Suppression: any agency that has replied (positive or negative) is removed from all sequences immediately.
- Cooling period: no re-contact for 90 days if no response after full sequence.
- CRM sync: every send event is logged with timestamp, variant used, and lead score.

### Step 6: Response Handling

| Response Type | Agent Action |
|---|---|
| Positive (interest, question, meeting request) | Flag for human SDR handoff. Log as "warm". Pause all automated sequences for that lead. |
| Objection (price, timing, tool already covered) | Generate a tailored reply draft using objection-specific prompt. Human reviews before sending. |
| Unsubscribe / not interested | Immediate suppression. Log reason. Feed signal back to scoring model. |
| No response (after full sequence) | Mark as "exhausted". Add to 90-day re-engagement list. Log final state. |
| Bounce / invalid email | Flag for manual email verification. Try LinkedIn channel instead. |

### Step 7: Learning Loop (runs weekly)

Every Sunday, the agent runs a performance analysis across the prior week:

- Open rate by subject line variant. Promotes top performer, retires bottom performer.
- Reply rate by vertical (footwear vs. electronics vs. furniture). Adjusts scoring weights.
- Reply rate by signal type. Recalibrates which triggers are most predictive.
- Conversion by message variant. Updates generation prompts for next week.
- Outputs a weekly digest markdown file with top 10 leads, key metrics, and suggested changes.

---

## 05 Technical Stack and Build Notes

### Recommended Stack

| Component | Tool / Approach |
|---|---|
| Orchestration | Python. Main agent loop, scheduling, state management. |
| Scraping: LinkedIn | LinkedIn Jobs API (public) + Apify LinkedIn scraper for company/post data |
| Scraping: Behance/ArtStation | Playwright headless browser. Both have public portfolio feeds. |
| Scraping: Trade press | RSS feeds (Core77, Dezeen) + Google News API |
| LLM calls | Anthropic API. `claude-sonnet-4-20250514` for email/DM generation, `claude-haiku-4-5` for scoring/classification. |
| Database | SQLite (local dev) -> PostgreSQL (prod). Stores leads, events, outreach history. |
| Email sending | SendGrid API. Transactional with open/click tracking. |
| LinkedIn outreach | Phantombuster or Dux-Soup for LinkedIn automation (within ToS rate limits) |
| CRM sync | HubSpot API or CSV export. Contact + activity log. |
| Scheduling | APScheduler (Python). Daily signal detection, weekly learning loop. |
| Monitoring | Logging to file + weekly Slack/email digest |

### Key Technical Constraints

- LinkedIn rate limits: connection requests capped at ~20/day per account to avoid suspension
- Email deliverability: use a warmed domain (not vizcom.com) for cold outreach to protect main domain reputation
- LLM cost management: use Haiku for scoring/classification (high volume), Sonnet only for final content generation
- Deduplication: store seen URLs + agency names in DB to avoid re-processing the same signals
- GDPR/CAN-SPAM: all outreach emails must include unsubscribe link. Log consent signals.

### Claude API Usage Pattern

| Call Type | Model | Frequency | Approx Tokens |
|---|---|---|---|
| Signal classification | `claude-haiku-4-5` | ~200/day | ~300 in / 50 out |
| Lead scoring + brief generation | `claude-haiku-4-5` | ~30/day | ~800 in / 400 out |
| Email + DM content generation | `claude-sonnet-4-20250514` | ~30/day | ~600 in / 500 out |
| Weekly learning loop analysis | `claude-sonnet-4-20250514` | ~1/week | ~2000 in / 800 out |
| Objection response drafts | `claude-sonnet-4-20250514` | ~5/day | ~500 in / 300 out |

---

## 06 Sample Agent Outputs

### Example Lead Scorecard

```
Agency:    Whipsaw Inc. (San Jose, CA)
Score:     82/100
Trigger:   New case study posted (consumer electronics headphones, 3 days ago)
Vertical:  Consumer electronics + footwear
Team size: ~22 employees
Tool signal: KeyShot mentioned in 4 employee LinkedIn profiles
Contact:   Dan Harden (Founder/Principal)
LinkedIn:  linkedin.com/in/danharden
Action:    HIGH PRIORITY. Send email Day 1, LinkedIn connect Day 2.
```

### Example Cold Email Output

**Subject line A:** How many renders were in your last pitch deck?
**Subject line B:** Whipsaw pitches on 4 renders. What if it were 40?

---

Dan,

The headphone project you posted last week has great form language. The temple-to-cup transition is clearly considered. Quick question: how many render variations did you show the client before landing on that direction?

Most ID studios we talk to pitch 3 to 5. The constraint is not ideas, it is render time. A Whipsaw designer sketches 40 directions, renders 4, and the client picks from 4.

Vizcom changes that math. Teams using it go from 5 renders per pitch to 40 to 50, without adding headcount or outsourcing. New Balance and Brooks use it for footwear colorway reviews. Breville uses it for CMF exploration before sampling.

Worth a 20-minute workflow session to see if it fits how Whipsaw works?

[Name]

---

### Example LinkedIn Connection Note

> Dan, the headphone project Whipsaw posted this week caught my eye. The surface language is really clean. I work with a few ID studios on render workflow tools and would love to connect. Always interesting to see how different teams approach the concept-to-client pipeline.

*(278 characters)*

---

## 07 Success Metrics and Evaluation

### Primary KPIs

| Metric | Target Month 1 | Target Month 3 |
|---|---|---|
| Qualified leads identified per week | 15 to 20 | 40 to 60 |
| Email open rate | >35% | >45% |
| Email reply rate | >5% | >8% |
| LinkedIn connection acceptance rate | >30% | >40% |
| Leads converted to demo/call | 3 to 5/month | 10 to 15/month |
| Cost per qualified lead (LLM + tools) | <$2.00 | <$1.00 |

### What Works / What Could Break

#### Expected to work well

- Signal detection. LinkedIn and Behance are rich, public, and consistently updated.
- Personalization. Claude generates genuinely non-generic emails when given specific agency context.
- Vertical specificity. Footwear agencies respond differently to footwear language than generic ID outreach.

#### Known risks

- LinkedIn rate limits. Automation accounts risk suspension. Need careful throttling and account warming.
- Email deliverability. Cold outreach on a new domain takes 4 to 6 weeks of warming before reliable inbox placement.
- Tool signal accuracy. KeyShot mentions in profiles may be outdated. Need recency filtering.
- Agency list coverage. IDSA directory is incomplete. Will need enrichment from Clutch, DesignRush, manual research.

#### How to improve with more time

- Add a vision model to score Behance render quality. Agencies with lower-quality renders are higher-priority targets.
- Integrate with Vizcom's product analytics to identify free-tier users at agencies and trigger upgrade sequences.
- Build a referral detection layer. When an agency signs up, automatically identify peer firms and trigger warm outreach citing the new customer.
- Add a conference signal layer. Monitor IDSA, Clerkenwell Design Week, Orgatec attendee lists for warm outreach timing.
