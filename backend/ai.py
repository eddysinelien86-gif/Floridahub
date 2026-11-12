"""AI content generation for MarketHub.

This replaces the old hard-coded keyword responses with real generation from
Claude (Anthropic). It is designed to be safe and self-contained:

  * If ANTHROPIC_API_KEY is set, it calls Claude and returns real content.
  * Otherwise (or if the Claude call fails) it asks a local Ollama model
    running on this machine, so the Pi can write content with no key at all.
  * If neither is available, it falls back to the built-in sample text so the
    dashboard still works.

Public API:
    generate(prompt: str) -> dict with keys {"text": str, "mode": str}

Environment variables:
    ANTHROPIC_API_KEY   your key from console.anthropic.com (enables real AI)
    MARKETHUB_MODEL     model id (default "claude-opus-5-5"; set
                        "claude-haiku-5-5" for a much cheaper always-on box)
    MARKETHUB_BRAND     business name used to flavor the content
    MARKETHUB_OLLAMA_MODEL  local model name (default "llama3.2:3b");
                            set to "off" to disable the local model
    OLLAMA_HOST         where Ollama listens (default "http://127.0.0.1:11434");
                        point it at another machine to borrow its speed
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

MODEL = os.environ.get("MARKETHUB_MODEL", "claude-opus-5-5")
# Defaults to the insulation lead-gen business; override with MARKETHUB_BRAND.
BRAND = os.environ.get("MARKETHUB_BRAND", "an insulation & spray-foam company (lead generation)")

# Keep the three to four hundred token ceiling tight — this feeds a phone-sized
# screen and short social posts, not essays.
MAX_TOKENS = 400

# A small model on a Pi needs time to load and write; don't give up too early.
OLLAMA_TIMEOUT = 180


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


def _ollama_settings() -> tuple[str, str]:
    """Return (base_url, model). An empty model means the local model is off."""
    model = os.environ.get("MARKETHUB_OLLAMA_MODEL", "llama3.2:3b").strip()
    if model.lower() in ("", "off", "none", "0", "false"):
        model = ""
    host = os.environ.get("OLLAMA_HOST", "").strip() or "http://127.0.0.1:11434"
    if "://" not in host:
        host = "http://" + host
    return host.rstrip("/"), model


def _ollama_generate(prompt: str, mode: str) -> str:
    """Ask the local Ollama model. Raises if it is off, unreachable or empty."""
    host, model = _ollama_settings()
    if not model:
        raise RuntimeError("local model disabled")
    body = json.dumps(
        {
            "model": model,
            "stream": False,
            "keep_alive": "30m",  # stay loaded so the next tap is quick
            "options": {"num_predict": MAX_TOKENS},
            "messages": [
                {"role": "system", "content": _SYSTEM[mode]},
                {"role": "user", "content": prompt or "Give me a marketing idea."},
            ],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        host + "/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = str((data.get("message") or {}).get("content", "")).strip().strip('"').strip()
    if not text:
        raise RuntimeError("local model returned no text")
    return text


def status() -> dict:
    """Say which writer the next request will use, for the Settings screen."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return {"provider": "claude", "label": f"Claude ({MODEL})"}
    host, model = _ollama_settings()
    if model:
        try:
            with urllib.request.urlopen(host + "/api/tags", timeout=2) as resp:
                names = [m.get("name", "") for m in json.loads(resp.read()).get("models", [])]
            if model in names or model + ":latest" in names:
                return {"provider": "ollama", "label": f"Local model on this Pi ({model})"}
            return {
                "provider": "sample",
                "label": f"Sample text (local model '{model}' is not downloaded)",
            }
        except Exception:
            pass
    return {"provider": "sample", "label": "Sample text (no AI connected)"}


def _claude_generate(prompt: str, mode: str) -> str:
    """Ask Claude. Raises if the SDK is missing, the call fails or it is empty."""
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
        raise RuntimeError("Claude returned no text")
    return text


def generate(prompt: str) -> dict:
    """Generate marketing content for a prompt. Always returns a dict.

    Order: Claude (when a key is set), then the local Ollama model, then the
    built-in samples.
    """
    prompt = (prompt or "").strip()
    mode = detect_mode(prompt)
    errors = []

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return {"text": _claude_generate(prompt, mode), "mode": mode, "source": "claude"}
        except Exception as exc:  # network down, bad key, SDK missing, etc.
            errors.append(f"claude: {exc}")

    if _ollama_settings()[1]:
        try:
            return {"text": _ollama_generate(prompt, mode), "mode": mode, "source": "ollama"}
        except Exception as exc:  # not installed, not running, model missing, etc.
            # With no key and no local model running, stay quiet: that is the
            # plain "samples only" setup, not a fault worth showing.
            not_running = isinstance(exc, urllib.error.URLError) and isinstance(
                getattr(exc, "reason", None), ConnectionRefusedError
            )
            if errors or not not_running:
                errors.append(f"ollama: {exc}")

    result = _fallback(prompt, mode)
    if errors:
        result["error"] = "; ".join(errors)  # surfaced for debugging
    return result
