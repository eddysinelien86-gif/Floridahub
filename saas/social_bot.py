"""Twice-a-day social auto-poster for In & Out Insulation.

Posts a fresh, AI-written promo to the Facebook Page and Instagram (feed +
optional story), rotating the highlighted service each run, always ending with
the free-quote link. Designed to run from a GitHub Actions schedule.

Caption is written by Claude (Anthropic). If no ANTHROPIC_API_KEY is set, a
solid templated caption is used instead, so posting still works.

Required env (set as GitHub Actions secrets):
    META_PAGE_ACCESS_TOKEN   long-lived Facebook Page access token
Optional env (sensible defaults baked in):
    FB_PAGE_ID    default 100780832053532
    IG_USER_ID    auto-discovered from the Page if omitted
    LEAD_URL      the public quote-form link
    IMAGE_URL     public image to attach (the flyer)
    ANTHROPIC_API_KEY   for AI captions
    POST_IG_STORY        "1" to also post the image to the IG story
    GRAPH_VERSION        default v21.0

Nothing is posted (clean exit) if META_PAGE_ACCESS_TOKEN is missing, so the
scheduled job stays quiet until you connect Meta.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com/" + os.environ.get("GRAPH_VERSION", "v21.0")
TOKEN = os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "100780832053532").strip()
IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()
LEAD_URL = os.environ.get(
    "LEAD_URL",
    "https://elio-insulation-hub.onrender.com/t/in-out-insulation-and-spray-foam-of-broward-llc",
).strip()
IMAGE_URL = os.environ.get(
    "IMAGE_URL", "https://elio-insulation-hub.onrender.com/static/flyer.png"
).strip()
POST_IG_STORY = os.environ.get("POST_IG_STORY", "").strip() in ("1", "true", "yes")

SERVICES = [
    ("attic insulation", "beat the Florida heat and lower your cooling bills"),
    ("spray foam insulation", "seal your home tight for year-round comfort"),
    ("crawlspace insulation", "stop moisture and drafts from under the house"),
    ("energy audits", "find exactly where your home is leaking money"),
]


def _service_today() -> tuple[str, str]:
    # Rotate by day-of-year and AM/PM so the two daily posts differ.
    now = datetime.datetime.utcnow()
    idx = (now.timetuple().tm_yday * 2 + (1 if now.hour >= 18 else 0)) % len(SERVICES)
    return SERVICES[idx]


def _ai_caption(service: str, angle: str) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=key)
            resp = client.messages.create(
                model=os.environ.get("MARKETHUB_MODEL", "claude-opus-5-5"),
                max_tokens=320,
                system=(
                    "You write ONE short, upbeat social media caption for 'In & Out "
                    "Insulation & Spray Foam of Broward, LLC', a home insulation "
                    "contractor in Broward County, Florida. 2-4 sentences, friendly and "
                    "local, focused on the given service. End with a clear call to get a "
                    "free quote. Do NOT include the URL (it is appended separately). "
                    "Add 4-6 relevant hashtags on the last line. No preamble, no quotes."
                ),
                messages=[{
                    "role": "user",
                    "content": f"Today's focus: {service} — {angle}.",
                }],
            )
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if text:
                return text
        except Exception as exc:
            print(f"[bot] AI caption failed, using template: {exc}")
    # Fallback template
    return (
        f"🏠 Thinking about {service}? We can help you {angle}. "
        f"In & Out Insulation & Spray Foam of Broward serves all of Broward County — "
        f"fast, honest, local. Get your FREE quote in minutes! 👇\n"
        f"#Insulation #SprayFoam #Broward #EnergySavings #SouthFlorida #HomeImprovement"
    )


def _post(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=40) as r:
        return json.loads(r.read().decode())


def discover_ig_id() -> str:
    if IG_USER_ID:
        return IG_USER_ID
    try:
        q = urllib.parse.urlencode({"fields": "instagram_business_account", "access_token": TOKEN})
        data = _get(f"{GRAPH}/{FB_PAGE_ID}?{q}")
        return (data.get("instagram_business_account") or {}).get("id", "")
    except Exception as exc:
        print(f"[bot] could not discover IG account: {exc}")
        return ""


def post_facebook(caption: str) -> None:
    msg = f"{caption}\n\n➡️ Free quote: {LEAD_URL}"
    try:
        # Photo post (image + caption) gets more reach than a plain link post.
        res = _post(f"{GRAPH}/{FB_PAGE_ID}/photos",
                    {"url": IMAGE_URL, "caption": msg, "access_token": TOKEN})
        print(f"[bot] facebook posted: {res}")
    except Exception as exc:
        print(f"[bot] facebook post FAILED: {exc}")


def post_instagram(caption: str, ig_id: str) -> None:
    if not ig_id:
        print("[bot] no Instagram account id; skipping IG")
        return
    cap = f"{caption}\n\n➡️ Free quote — link in bio or: {LEAD_URL}"
    try:
        create = _post(f"{GRAPH}/{ig_id}/media",
                       {"image_url": IMAGE_URL, "caption": cap, "access_token": TOKEN})
        cid = create.get("id")
        if not cid:
            print(f"[bot] IG container failed: {create}")
            return
        pub = _post(f"{GRAPH}/{ig_id}/media_publish",
                    {"creation_id": cid, "access_token": TOKEN})
        print(f"[bot] instagram posted: {pub}")
    except Exception as exc:
        print(f"[bot] instagram post FAILED: {exc}")
    if POST_IG_STORY:
        try:
            s = _post(f"{GRAPH}/{ig_id}/media",
                      {"image_url": IMAGE_URL, "media_type": "STORIES", "access_token": TOKEN})
            scid = s.get("id")
            if scid:
                sp = _post(f"{GRAPH}/{ig_id}/media_publish",
                           {"creation_id": scid, "access_token": TOKEN})
                print(f"[bot] instagram story posted: {sp}")
        except Exception as exc:
            print(f"[bot] instagram story FAILED: {exc}")


def main() -> int:
    if not TOKEN:
        print("[bot] META_PAGE_ACCESS_TOKEN not set — nothing to post yet. "
              "Add it as a GitHub secret to go live.")
        return 0
    service, angle = _service_today()
    caption = _ai_caption(service, angle)
    print(f"[bot] today's service: {service}\n[bot] caption:\n{caption}\n")
    post_facebook(caption)
    post_instagram(caption, discover_ig_id())
    return 0


if __name__ == "__main__":
    sys.exit(main())
