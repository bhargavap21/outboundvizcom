"""
Content generation via Claude Sonnet — all outreach copy for the channel sequence.

Channel sequence (from spec):
  Day 1   — Behance/ArtStation comment (no pitch, no link)
  Day 3   — Cold email to Design Director
  Day 7   — LinkedIn connection request note
  Day 14  — LinkedIn DM: share something useful, no ask
  Day 30  — Final email: acknowledges may not be right fit

Voice rules (enforced in every prompt):
  - Open with an observation that proves you looked, not a compliment
  - Name the pain as something felt, not a statistic
  - Never say: "caught my eye", "love to connect", "workflow session",
    "I noticed", "seamless", "game-changing", "revolutionary", "reach out",
    "AI", "machine learning", "technology"
  - Tone: senior ID director should forward this, not delete it
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import anthropic
import structlog

from config.settings import ANTHROPIC_API_KEY, MODEL_CONTENT
from agent.research.brief import AgencyBrief

log = structlog.get_logger()
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Real Vizcom customers to reference by vertical (from spec)
_CUSTOMER_REFERENCES: dict[str, str] = {
    "footwear":              "New Balance's footwear team cut their colorway review cycle in half",
    "consumer electronics":  "Breville uses it before committing to a single physical sample",
    "furniture":             "a furniture studio we work with stopped outsourcing renders entirely",
    "home goods":            "a home goods team we work with reviews 30 colorways before a single sample is cut",
    "automotive":            "a transportation design team we know reviews 40 directions before any clay work",
    "apparel accessories":   "a accessories studio cut their concept-to-client cycle from 3 weeks to 4 days",
}

_BANNED_WORDS = (
    '"caught my eye"', '"love to connect"', '"workflow session"', '"I noticed"',
    '"seamless"', '"game-changing"', '"revolutionary"', '"reach out"',
    '"AI"', '"machine learning"', '"technology"',
)


@dataclass
class ContentPackage:
    # Day 1: pre-email portfolio comment
    behance_comment: str = ""
    # Day 3: cold email
    cold_email_subject_a: str = ""
    cold_email_subject_b: str = ""
    cold_email_body: str = ""
    # Day 7: LinkedIn connection request
    linkedin_connection_note: str = ""
    # Day 14: LinkedIn DM
    linkedin_dm_day14: str = ""
    # Day 30: final email
    final_email_day30: str = ""


def generate_content(brief: AgencyBrief) -> ContentPackage:
    package = ContentPackage()

    recent = brief.recent_projects[0] if brief.recent_projects else {}
    vertical = (brief.verticals[0] if brief.verticals else "industrial design").lower()
    customer_ref = _customer_ref(vertical)
    tool_signal = _tool_signal(brief.tool_stack)

    package.behance_comment = _generate_portfolio_comment(brief, recent)

    package.cold_email_subject_a, package.cold_email_subject_b, package.cold_email_body = (
        _generate_cold_email(brief, recent, vertical, customer_ref, tool_signal)
    )

    package.linkedin_connection_note = _generate_connection_note(brief, recent)
    package.linkedin_dm_day14 = _generate_dm_day14(brief, vertical, customer_ref)
    package.final_email_day30 = _generate_final_email(brief)

    log.info(
        "content_generated",
        agency=brief.agency_name,
        contact=brief.contact_name,
        email_words=len(package.cold_email_body.split()),
        note_chars=len(package.linkedin_connection_note),
    )
    return package


# ---------------------------------------------------------------------------
# Individual generators
# ---------------------------------------------------------------------------

def _generate_portfolio_comment(brief: AgencyBrief, recent: dict) -> str:
    project_title = recent.get("title", "their recent project")
    project_summary = recent.get("summary") or recent.get("description") or ""

    prompt = f"""You are leaving a comment on a Behance or ArtStation portfolio post from {brief.agency_name}.

The project: "{project_title}"
Details: {project_summary[:300] or "a product design project"}

Write a single comment (40 to 60 words) that:
1. Makes one specific, opinionated observation about a design decision in this work
2. Asks a genuine question about their process or a choice they made
3. Sounds like a fellow senior designer, not a vendor or fan

Rules:
- No pitch. No link. No mention of any product or company.
- Never say: "caught my eye", "love to connect", "seamless", "game-changing"
- Output only the comment text, nothing else."""

    response = _client.messages.create(
        model=MODEL_CONTENT,
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def _generate_cold_email(
    brief: AgencyBrief,
    recent: dict,
    vertical: str,
    customer_ref: str,
    tool_signal: str,
) -> tuple[str, str, str]:
    project_title = recent.get("title", "")
    project_summary = recent.get("summary") or recent.get("description") or ""
    contact = brief.contact_name or "the Design Director"

    prompt = f"""You are writing outreach on behalf of Vizcom, a rendering tool built by industrial designers for industrial designers.

Vizcom's voice: peer-to-peer, not vendor-to-customer. Specific and sensory, never generic. Short sentences with weight. Never lead with AI. Write like someone who has actually used KeyShot and found it exhausting.

Agency context:
- Name: {brief.agency_name}
- Contact: {contact}{f", {brief.contact_title}" if getattr(brief, 'contact_title', None) else ""}
- Recent work: {project_title} — {project_summary[:200] or "product design work"}
- Tool signal: {tool_signal}
- Vertical: {vertical}

Write a 130 to 150 word cold email that:
1. Opens with one specific, opinionated observation about their actual work. Not a compliment. Something you can only say if you actually looked.
2. Names the render bottleneck as something they feel, in the language of their craft. Not a stat.
3. References this real customer in their vertical: {customer_ref}. Use their name and one concrete detail.
4. Closes with a question that invites pushback, not a meeting request.

Banned words and phrases (do not use any of these): "caught my eye", "love to connect", "workflow session", "I noticed", "seamless", "game-changing", "revolutionary", "reach out", "AI", "machine learning", "technology".

Do not ask for a meeting or demo. The closing question should invite the recipient to push back or share their own experience.

Generate two subject line variants:
- Subject A: a question
- Subject B: a short tension fragment (like "You sketched 30. You showed 4.")

Format exactly as:
SUBJECT_A: <subject line>
SUBJECT_B: <subject line>
BODY:
<email body>"""

    response = _client.messages.create(
        model=MODEL_CONTENT,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_email_response(response.content[0].text)


def _generate_connection_note(brief: AgencyBrief, recent: dict) -> str:
    project_title = recent.get("title", "their recent work")

    prompt = f"""Write a LinkedIn connection request note (max 300 characters) to a designer at {brief.agency_name}.

Reference their project: "{project_title}"

Rules:
- Sound like a curious peer designer, not a vendor
- Make one specific observation about the work
- Do not pitch anything. Do not mention any product or company.
- Banned phrases: "love to connect", "caught my eye", "seamless", "game-changing", "reach out", "workflow"
- Output only the note text, nothing else."""

    response = _client.messages.create(
        model=MODEL_CONTENT,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()[:300]


def _generate_dm_day14(brief: AgencyBrief, vertical: str, customer_ref: str) -> str:
    prompt = f"""Write a LinkedIn DM (under 100 words) to a designer at {brief.agency_name}, a {vertical} studio.

This is a follow-up sent 14 days after connecting. They have not replied to anything yet.

The message should:
1. Share one useful, specific observation or insight relevant to {vertical} design — something that makes them think, not sell
2. Reference this real customer example: {customer_ref}
3. End with a soft, optional question — not a meeting request

Banned phrases: "workflow session", "caught my eye", "love to connect", "seamless", "game-changing", "revolutionary", "reach out", "AI", "machine learning".

Output only the message text, nothing else."""

    response = _client.messages.create(
        model=MODEL_CONTENT,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def _generate_final_email(brief: AgencyBrief) -> str:
    contact = brief.contact_name or "the Design Director"

    prompt = f"""Write a final cold email (60 to 80 words) to {contact} at {brief.agency_name}.

This is the last touch in a sequence — they have not replied to anything. The email should:
1. Acknowledge they may not be the right fit right now
2. Leave the door open without pressure
3. Say something genuine and specific about their work
4. No CTA. No meeting request. No links.

Tone: gracious, not desperate. Peer-to-peer.
Banned: "caught my eye", "love to connect", "seamless", "game-changing", "reach out", "AI".

Output only the email body (no subject line), nothing else."""

    response = _client.messages.create(
        model=MODEL_CONTENT,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _customer_ref(vertical: str) -> str:
    for key, ref in _CUSTOMER_REFERENCES.items():
        if key in vertical:
            return ref
    return "a product studio we work with went from 4 renders per pitch to 40"


def _tool_signal(tool_stack: list[str]) -> str:
    if not tool_stack:
        return "unknown (likely outsourced or traditional pipeline)"
    tools = [t for t in tool_stack if t.lower() not in ("cad",)]
    if tools:
        return ", ".join(tools)
    return "CAD-based (likely KeyShot or Rhino)"


def _parse_email_response(text: str) -> tuple[str, str, str]:
    lines = text.strip().splitlines()
    subject_a, subject_b, body_lines = "", "", []
    in_body = False
    for line in lines:
        if line.startswith("SUBJECT_A:"):
            subject_a = line.removeprefix("SUBJECT_A:").strip()
        elif line.startswith("SUBJECT_B:"):
            subject_b = line.removeprefix("SUBJECT_B:").strip()
        elif line.strip() == "BODY:":
            in_body = True
        elif in_body:
            body_lines.append(line)
    return subject_a, subject_b, "\n".join(body_lines).strip()
