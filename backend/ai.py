"""AI content generation for MarketHub.

This replaces the old hard-coded keyword responses with real generation from
Claude (Anthropic). It is designed to be safe and self-contained:

  * If ANTHROPIC_API_KEY is set, it calls Claude and returns real content.
  * If the key is missing, the SDK isn't installed, or the API call fails,
    it falls back to the built-in sample text so the dashboard still works.

Public API:
    generate(prompt: str) -> dict with keys {"text": str, "mode": str}

Environment variables:
    ANTHROPIC_API_KEY   your key from console.anthropic.com (enables real AI)
    MARKETHUB_MODEL     model id (default "claude-opus-5-5"; set
                        "claude-haiku-5-5" for a much cheaper always-on box)
    MARKETHUB_BRAND     business name used to flavor the content
"""

from __future__ import annotations

import os

MODEL = os.environ.get("MARKETHUB_MODEL", "claude-opus-5-5")
# Defaults to the insulation lead-gen business; override with MARKETHUB_BRAND.
BRAND = os.environ.get("MARKETHUB_BRAND", "an insulation & spray-foam company (lead generation)")

# Keep the three to four hundred token ceiling tight — this feeds a phone-sized
# screen and short social posts, not essays.
MAX_TOKENS = 400


def detect_mode(prompt: str) -> str:
    """Figure out what kind of content the user is asking for."""
    p = prompt.lower()
    if "caption" in p:
        return "caption"
    if "hashtag" in p:
        return "hashtag"
    if "review" in p:
        return "review"
    return "idea"


# System instructions per mode. Short, concrete, and in a small-business voice.
_SYSTEM = {
    "caption": (
        f"You write social media captions for {BRAND}. "
        "Return ONE caption only: warm, confident, 1-2 sentences, with a light "
        "call to action. No hashtags, no quotes around it, no preamble."
    ),
    "hashtag": (
        f"You generate hashtags for {BRAND}'s social posts. "
        "Return 5-8 relevant hashtags on one line, space-separated, each starting "
        "with #. No other text."
    ),
    "review": (
        f"You write friendly, professional replies to customer reviews for {BRAND}. "
        "Return ONE reply: thankful, specific, 1-2 sentences, never defensive. "
        "No preamble, no quotes."
    ),
    "idea": (
        f"You are a marketing strategist for {BRAND}. "
        "Return ONE concrete, actionable marketing idea in 1-2 sentences. "
        "No preamble, no list."
    ),
}


# Exact sample text used when real AI is unavailable (parity with the original
# MarketHub behavior, so the dashboard looks the same without a key).
def _fallback(prompt: str, mode: str) -> dict:
    samples = {
        "caption": "Capture the energy of the launch with a warm, confident caption "
        "that highlights transformation and momentum.",
        "hashtag": "#GrowthMindset #ModernBusiness #DigitalMarketing "
        "#BrandMomentum #AudienceFirst",
        "review": "Thank you for your feedback. We appreciate the trust you placed "
        "in us and look forward to helping your business grow.",
        "idea": f"A polished marketing idea for '{prompt or 'your business'}' could be "
        "a short video series featuring customer wins and behind-the-scenes momentum.",
    }
    return {"text": samples[mode], "mode": mode, "source": "sample"}


def generate(prompt: str) -> dict:
    """Generate marketing content for a prompt. Always returns a dict."""
    prompt = (prompt or "").strip()
    mode = detect_mode(prompt)

    # No key -> use the built-in samples (keeps the dashboard working offline).
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _fallback(prompt, mode)

    try:
        from anthropic import Anthropic

        client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=_SYSTEM[mode],
            output_config={"effort": "low"},  # snappy + cheap for short content
            messages=[{"role": "user", "content": prompt or "Give me a marketing idea."}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            return _fallback(prompt, mode)
        return {"text": text, "mode": mode, "source": "claude"}
    except Exception as exc:  # network down, bad key, SDK missing, etc.
        result = _fallback(prompt, mode)
        result["error"] = str(exc)  # surfaced for debugging; dashboard still works
        return result
