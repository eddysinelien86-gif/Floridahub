"""Write a personalized SMS and email for one lead with Claude (template fallback when unavailable)."""
from __future__ import annotations

import logging
import os
from typing import Any

from pydantic import BaseModel, Field

from .config import Settings

log = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
SMS_MAX_CHARS = 320
SMS_OPT_OUT = "Reply STOP to opt out."

TRADE_LABELS = {
    "ac_restoration": "AC restoration",
    "roofing": "roofing",
    "general_contractor": "general contracting",
    "insulation": "insulation",
}

SYSTEM_PROMPT = """You write short, honest first-touch business-to-business outreach for a small marketing company.

Rules:
- Address the business by name. Sound like one person writing to one business owner, not a mass blast.
- Use only facts given in the pitch and lead details. Never invent numbers, results, clients, guarantees or urgency.
- Identify the sender by first name and company in the text message.
- The text message must be under 260 characters, plain text, no links, no emojis, no hashtags.
  Do not add an opt-out line; one is appended automatically.
- The email has a specific subject line (under 60 characters, no clickbait) and a body of 60-120 words
  ending in a single low-pressure question. No footer or signature block; one is appended automatically.
"""


class OutreachCopy(BaseModel):
    sms: str = Field(description="Text message body, under 260 characters, without an opt-out line")
    email_subject: str
    email_body: str


def _lead_brief(lead: dict[str, Any]) -> str:
    parts = [
        f"Business name: {lead['name']}",
        f"Trade: {TRADE_LABELS.get(lead['trade'], lead['trade'])}",
        f"Area: {lead.get('city') or lead.get('address') or 'unknown'}",
    ]
    if lead.get("rating"):
        parts.append(f"Google rating: {lead['rating']}")
    if lead.get("website"):
        parts.append(f"Website: {lead['website']}")
    return "\n".join(parts)


def template_copy(lead: dict[str, Any], settings: Settings) -> OutreachCopy:
    trade = TRADE_LABELS.get(lead["trade"], lead["trade"])
    first = settings.sender_name.split()[0]
    sms = (
        f"Hi {lead['name']}, this is {first} with {settings.company}. {settings.pitch} "
        f"Open to a quick call about {trade} jobs in your area?"
    )
    body = (
        f"Hi {lead['name']} team,\n\n"
        f"I'm {settings.sender_name} with {settings.company}. {settings.pitch}\n\n"
        f"We're looking for one {trade} partner in your area. "
        f"Would you be open to a 10-minute call this week to see if it's a fit?"
    )
    return OutreachCopy(sms=sms, email_subject=f"{trade.title()} jobs in your area", email_body=body)


def _claude_copy(lead: dict[str, Any], settings: Settings) -> OutreachCopy | None:
    import anthropic

    client = anthropic.Anthropic()
    user = (
        f"Sender: {settings.sender_name}, {settings.company}\n"
        f"Pitch: {settings.pitch}\n\n"
        f"Lead details:\n{_lead_brief(lead)}\n\n"
        "Write the text message and the email."
    )
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
        output_format=OutreachCopy,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        log.warning("Claude did not return copy for lead %s (stop_reason=%s)", lead["id"], response.stop_reason)
        return None
    return response.parsed_output


def finalize_sms(text: str, settings: Settings) -> str:
    text = " ".join(text.split())
    if settings.company.lower() not in text.lower():
        text = f"{settings.company}: {text}"
    room = SMS_MAX_CHARS - len(SMS_OPT_OUT) - 1
    if len(text) > room:
        text = text[: room - 1].rstrip() + "…"
    return f"{text} {SMS_OPT_OUT}"


def email_footer(settings: Settings) -> str:
    lines = ["", "--", settings.sender_name, settings.company]
    if settings.company_address:
        lines.append(settings.company_address)
    lines.append('Not interested? Reply "unsubscribe" and we won\'t email you again.')
    return "\n".join(lines)


def draft_for_lead(lead: dict[str, Any], settings: Settings) -> tuple[OutreachCopy, str]:
    """Return (copy, source) where source is 'claude' or 'template'."""
    copy: OutreachCopy | None = None
    source = "template"
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        try:
            copy = _claude_copy(lead, settings)
            source = "claude" if copy else "template"
        except Exception as exc:  # network/auth/rate-limit: fall back to template rather than fail the batch
            log.warning("Claude drafting failed for lead %s: %s", lead["id"], exc)
    if copy is None:
        copy = template_copy(lead, settings)
    copy.sms = finalize_sms(copy.sms, settings)
    copy.email_body = copy.email_body.rstrip() + "\n" + email_footer(settings)
    return copy, source
