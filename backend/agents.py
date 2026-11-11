"""Automated agents for MarketHub — run small jobs on the Pi.

Content Agent: generates a batch of insulation post drafts via the AI layer
and saves them, so the "Drafts" queue (and the box count) fills up on its own.
Free to run — the only cost is the AI calls (pennies on Haiku).
"""

from __future__ import annotations

import random

from ai import generate
from database import add_draft, count_drafts, reviews_needing_reply, set_review_reply

TOPICS = [
    "attic insulation saves on winter heating bills",
    "signs your home needs more insulation",
    "spray foam vs blown-in insulation, which is right",
    "free insulation inspection offer this month",
    "lower your energy bills with proper insulation",
    "crawlspace insulation and moisture control",
    "is your attic losing heat — schedule an energy audit",
    "insulation rebates and tax credits for homeowners",
    "stay cooler this summer with better insulation",
    "new construction spray foam insulation",
    "drafty rooms? air sealing and insulation fix",
    "protect your pipes with crawlspace insulation",
]


def run_content_agent(n: int = 3) -> dict:
    """Generate n insulation post drafts and save them."""
    try:
        n = max(1, min(int(n), 6))
    except (TypeError, ValueError):
        n = 3
    picks = random.sample(TOPICS, min(n, len(TOPICS)))
    created = []
    for topic in picks:
        res = generate("caption: " + topic)
        text = res.get("text", "").strip()
        if text:
            add_draft(text, topic)
            created.append({"topic": topic, "text": text, "source": res.get("source")})
    return {"created": created, "total_drafts": count_drafts()}


def run_reply_agent() -> dict:
    """Draft a friendly reply for every review that doesn't have one yet."""
    pending = reviews_needing_reply()
    replied = []
    for rv in pending:
        prompt = (
            f"review: Write a short, warm reply to this {rv['rating']}-star review "
            f"from {rv['author']} on {rv['platform']}: \"{rv['comment']}\""
        )
        res = generate(prompt)
        text = res.get("text", "").strip()
        if text:
            set_review_reply(rv["id"], text)
            replied.append({"author": rv["author"], "reply": text, "source": res.get("source")})
    return {"replied": replied, "count": len(replied)}
