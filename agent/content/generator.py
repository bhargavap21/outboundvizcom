"""Content generation via Claude API — email, LinkedIn note, DM sequence."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import anthropic
import structlog

from config.settings import ANTHROPIC_API_KEY, MODEL_CONTENT
from agent.research.brief import AgencyBrief

log = structlog.get_logger()
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


@dataclass
class ContentPackage:
    cold_email_subject_a: str = ""
    cold_email_subject_b: str = ""
    cold_email_body: str = ""
    linkedin_connection_note: str = ""
    linkedin_dm_day3: str = ""
    linkedin_dm_day7: str = ""
    linkedin_dm_day14: str = ""


def generate_content(brief: AgencyBrief) -> ContentPackage:
    package = ContentPackage()

    package.cold_email_subject_a, package.cold_email_subject_b, package.cold_email_body = (
        _generate_cold_email(brief)
    )
    package.linkedin_connection_note = _generate_connection_note(brief)
    dm1, dm2, dm3 = _generate_dm_sequence(brief)
    package.linkedin_dm_day3 = dm1
    package.linkedin_dm_day7 = dm2
    package.linkedin_dm_day14 = dm3

    return package


def _generate_cold_email(brief: AgencyBrief) -> tuple[str, str, str]:
    recent = brief.recent_projects[0] if brief.recent_projects else {}
    tool_hint = ", ".join(brief.tool_stack) if brief.tool_stack else "traditional rendering tools"

    prompt = f"""You are a GTM specialist for Vizcom, an AI rendering tool for product designers.
Write a 140 to 160 word cold email to {brief.contact_name or "the Design Director"} at {brief.agency_name}, a
{brief.team_size or "boutique"}-person {", ".join(brief.verticals) or "industrial design"} studio.

Their recent work: {recent.get("summary", "high-quality product design work")}.
They appear to use {tool_hint} for rendering.

The email must:
1. Open with a specific observation about their work
2. Introduce the core pain: how many renders did they have in their last pitch deck?
3. State the value: agencies using Vizcom go from 3 to 5 renders per pitch to 40 to 50
4. Soft CTA: offer a 20-min workflow session, not a demo

Do not mention AI or machine learning.
Tone: direct, peer-to-peer, not salesy.
Generate two subject line variants.

Format your response exactly as:
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


def _generate_connection_note(brief: AgencyBrief) -> str:
    recent = brief.recent_projects[0] if brief.recent_projects else {}
    prompt = f"""Write a LinkedIn connection request note (max 280 characters) to a designer at {brief.agency_name}.
Reference their most recent project: {recent.get("summary", "their recent product design work")}.
Tone: curious designer peer, not a vendor. Do not pitch anything. Just connect.
Output only the note text, nothing else."""

    response = _client.messages.create(
        model=MODEL_CONTENT,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()[:280]


def _generate_dm_sequence(brief: AgencyBrief) -> tuple[str, str, str]:
    vertical = ", ".join(brief.verticals) or "industrial design"
    prompt = f"""Write a 3-message LinkedIn DM sequence for a design director at {brief.agency_name}, a {vertical} studio.

Message 1 (Day 3 after connecting): Share a relevant insight or render comparison for their vertical. No ask.
Message 2 (Day 7): Reference a specific Vizcom customer in their vertical with a one-line result.
Message 3 (Day 14): Soft ask — "Would a 20-min workflow session be useful?" with placeholder for calendar link.

Tone: peer-to-peer, not salesy. Keep each message under 100 words.

Format:
MSG1:
<message>
MSG2:
<message>
MSG3:
<message>"""

    response = _client.messages.create(
        model=MODEL_CONTENT,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_dm_response(response.content[0].text)


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


def _parse_dm_response(text: str) -> tuple[str, str, str]:
    msgs: dict[str, list[str]] = {"MSG1": [], "MSG2": [], "MSG3": []}
    current = None
    for line in text.strip().splitlines():
        key = line.strip().rstrip(":")
        if key in msgs:
            current = key
        elif current:
            msgs[current].append(line)
    return (
        "\n".join(msgs["MSG1"]).strip(),
        "\n".join(msgs["MSG2"]).strip(),
        "\n".join(msgs["MSG3"]).strip(),
    )
