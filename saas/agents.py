"""AI agents for AI LeadPilot.

- find_opportunities(): the Lead Finder agent — searches the web for local
  bids, contracts, and jobs the business could win, scored and dated.
- coach(): the Growth Coach agent — reviews the business's numbers and gives
  concrete steps to "reach the top peak."

Both use Claude when ANTHROPIC_API_KEY is set; otherwise they return helpful
sample output so the feature still demos.
"""

from __future__ import annotations

import json
import os

MODEL = os.environ.get("MARKETHUB_MODEL", "claude-opus-5-5")


def _client():
    from anthropic import Anthropic
    return Anthropic()


def _sample_opportunities(area: str) -> list[dict]:
    return [
        {"title": "Weatherization Assistance Program — subcontractors",
         "org": "County Community Action", "location": area, "due": "Rolling",
         "score": 82, "url": ""},
        {"title": "School district attic insulation — bid",
         "org": "Local School District", "location": area, "due": "Check portal",
         "score": 74, "url": ""},
        {"title": "New construction spray-foam subcontractor needed",
         "org": "Regional home builder", "location": area, "due": "Open",
         "score": 68, "url": ""},
    ]


def find_opportunities(area: str, brand: str = "an insulation contractor") -> dict:
    area = (area or "your area").strip()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"items": _sample_opportunities(area), "source": "sample"}
    prompt = (
        f"You are a lead-finding agent for {brand} in {area}. Search the web for REAL, current "
        "opportunities this contractor could win: government/municipal insulation or weatherization "
        "bids and RFPs, school/hospital facility projects, weatherization assistance programs, and "
        "builders or GCs seeking insulation/spray-foam subcontractors near that area. "
        "Return ONLY a JSON array (no prose) of up to 8 objects with keys: "
        "title, org, location, due (deadline or 'Rolling'/'Open'), score (0-100 fit for an "
        "insulation contractor), url. Prefer items with real URLs."
    )
    try:
        client = _client()
        resp = client.messages.create(
            model=MODEL, max_tokens=2000,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        start, end = text.find("["), text.rfind("]")
        items = json.loads(text[start:end + 1]) if start != -1 and end != -1 else []
        clean = []
        for it in items[:8]:
            clean.append({
                "title": str(it.get("title", ""))[:200],
                "org": str(it.get("org", ""))[:120],
                "location": str(it.get("location", area))[:120],
                "due": str(it.get("due", "Open"))[:60],
                "score": int(it.get("score", 50)) if str(it.get("score", "")).strip().isdigit() else 50,
                "url": str(it.get("url", ""))[:400],
            })
        return {"items": clean or _sample_opportunities(area), "source": "claude"}
    except Exception as exc:
        out = {"items": _sample_opportunities(area), "source": "sample"}
        out["error"] = str(exc)
        return out


def coach(context: str, brand: str = "your business") -> dict:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"text": (
            "Here's how to climb to the top:\n"
            "1. Post your work daily — photos of finished jobs build trust fast.\n"
            "2. Ask every happy customer for a review; aim for 10+.\n"
            "3. Follow up with every lead within the hour — speed wins jobs.\n"
            "4. Put your QR flyer on your truck and at every job site.\n\n"
            f"(Connect your Claude API key for advice tailored to {brand}'s live numbers.)"),
            "source": "sample"}
    try:
        client = _client()
        resp = client.messages.create(
            model=MODEL, max_tokens=500,
            system=(f"You are the Growth Coach agent for {brand}, a home-services contractor. "
                    "Using their DATA, give 3-5 specific, prioritized actions to get more leads and "
                    "jobs this month. Be concrete and encouraging. Short numbered list."),
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": f"DATA:\n{context}\n\nGive me my growth plan."}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        return {"text": text or "Keep posting your work and following up fast!", "source": "claude"}
    except Exception as exc:
        return {"text": f"Couldn't reach the coach ({exc}).", "source": "error"}
