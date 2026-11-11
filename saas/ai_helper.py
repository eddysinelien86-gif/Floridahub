"""Per-company AI content generation for the MarketHub SaaS.

generate(prompt, brand) writes content in the voice of each tenant's business.
Uses Claude when ANTHROPIC_API_KEY is set, otherwise returns sample text so the
feature still demos without a key.
"""

from __future__ import annotations

import os

MODEL = os.environ.get("MARKETHUB_MODEL", "claude-opus-5-5")
MAX_TOKENS = 400


def detect_mode(prompt: str) -> str:
    p = (prompt or "").lower()
    if "caption" in p:
        return "caption"
    if "hashtag" in p:
        return "hashtag"
    if "review" in p:
        return "review"
    return "idea"


def _system(mode: str, brand: str) -> str:
    return {
        "caption": (f"You write ONE short, warm social media caption for {brand}. "
                    "1-2 sentences with a light call to action. No hashtags, no quotes, no preamble."),
        "hashtag": (f"You generate 5-8 relevant hashtags for {brand}'s social posts, on one line, "
                    "space-separated, each starting with #. No other text."),
        "review": (f"You write ONE short, friendly reply to a customer review for {brand}. "
                   "1-2 sentences, thankful and specific, never defensive. No preamble, no quotes."),
        "idea": (f"You are a marketing strategist for {brand}. Give ONE concrete, actionable "
                 "marketing idea in 1-2 sentences. No preamble, no list."),
    }[mode]


def _fallback(prompt: str, mode: str, brand: str) -> dict:
    samples = {
        "caption": f"Comfortable home, lower bills — that's what {brand} delivers. Book your free quote today!",
        "hashtag": "#Insulation #EnergySavings #HomeImprovement #SprayFoam #LocalBusiness #LowerBills",
        "review": "Thank you so much for the kind words — it was a pleasure working with you, and we're always here if you need us.",
        "idea": f"Run a free inspection offer this month and post before/after photos — {brand} can turn curiosity into booked jobs.",
    }
    return {"text": samples[mode], "mode": mode, "source": "sample"}


def generate(prompt: str, brand: str = "your business") -> dict:
    prompt = (prompt or "").strip()
    mode = detect_mode(prompt)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _fallback(prompt, mode, brand)
    try:
        from anthropic import Anthropic

        client = Anthropic()
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=_system(mode, brand),
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt or "Give me a marketing idea."}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            return _fallback(prompt, mode, brand)
        return {"text": text, "mode": mode, "source": "claude"}
    except Exception as exc:
        result = _fallback(prompt, mode, brand)
        result["error"] = str(exc)
        return result
