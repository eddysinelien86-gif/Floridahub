"""Twice-a-day social auto-poster for In & Out Insulation.

Posts a fresh, AI-written promo to the Facebook Page and Instagram (feed +
optional story), rotating the highlighted service each run, always ending with
the free-quote link.

Driven by the Flask app's /tasks/social-post endpoint (hit by a free external
cron twice a day), so it runs on Render alongside everything else.

Config comes from environment variables (set in Render):
    META_PAGE_ACCESS_TOKEN   Facebook Page access token (required)
    FB_PAGE_ID               default 100780832053532
    IG_USER_ID               auto-discovered from the Page if omitted
    LEAD_URL                 the public quote-form link (default baked in)
    IMAGE_URL                public image to attach (default: hosted flyer)
    ANTHROPIC_API_KEY        for AI captions (optional; template used otherwise)
    POST_IG_STORY            "1" to also post the image to the IG story
    GRAPH_VERSION            default v21.0

run() returns a list of log lines (shown in the browser when testing); it never
raises, so a bad token just reports the error instead of crashing the app.
"""

from __future__ import annotations

import datetime
import json
import os
import urllib.parse
import urllib.request

DEFAULT_LEAD = ("https://elio-insulation-hub.onrender.com/t/"
                "in-out-insulation-and-spray-foam-of-broward-llc")
# Instagram requires a JPEG with aspect ratio between 4:5 and 1.91:1, so we use
# a square JPEG (works for Facebook too). The tall PNG flyer is print-only.
DEFAULT_IMAGE = "https://elio-insulation-hub.onrender.com/static/social.jpg"

SERVICES = [
    ("attic insulation", "beat the Florida heat and lower your cooling bills"),
    ("spray foam insulation", "seal your home tight for year-round comfort"),
    ("crawlspace insulation", "stop moisture and drafts from under the house"),
    ("energy audits", "find exactly where your home is leaking money"),
]


def _cfg() -> dict:
    return {
        "graph": "https://graph.facebook.com/" + os.environ.get("GRAPH_VERSION", "v21.0"),
        "token": os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip(),
        "page_id": os.environ.get("FB_PAGE_ID", "100780832053532").strip(),
        "ig_id": os.environ.get("IG_USER_ID", "").strip(),
        "lead": os.environ.get("LEAD_URL", DEFAULT_LEAD).strip(),
        "image": os.environ.get("IMAGE_URL", DEFAULT_IMAGE).strip(),
        "story": os.environ.get("POST_IG_STORY", "").strip() in ("1", "true", "yes"),
    }


def _service_today() -> tuple[str, str]:
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
                messages=[{"role": "user", "content": f"Today's focus: {service} — {angle}."}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if text:
                return text
        except Exception as exc:
            print(f"[bot] AI caption failed, using template: {exc}")
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


def _discover_ig(c: dict) -> str:
    if c["ig_id"]:
        return c["ig_id"]
    try:
        q = urllib.parse.urlencode({"fields": "instagram_business_account", "access_token": c["token"]})
        data = _get(f"{c['graph']}/{c['page_id']}?{q}")
        return (data.get("instagram_business_account") or {}).get("id", "")
    except Exception as exc:
        return f""  # reported by caller


def run() -> list[str]:
    log: list[str] = []
    c = _cfg()
    if not c["token"]:
        log.append("META_PAGE_ACCESS_TOKEN not set — nothing posted. Add it in Render to go live.")
        return log
    service, angle = _service_today()
    caption = _ai_caption(service, angle)
    log.append(f"Service today: {service}")
    log.append(f"Caption:\n{caption}")

    # Facebook Page photo post
    fb_msg = f"{caption}\n\n➡️ Free quote: {c['lead']}"
    try:
        res = _post(f"{c['graph']}/{c['page_id']}/photos",
                    {"url": c["image"], "caption": fb_msg, "access_token": c["token"]})
        log.append(f"✅ Facebook posted (post id: {res.get('post_id') or res.get('id')})")
    except Exception as exc:
        log.append(f"❌ Facebook failed: {exc}")

    # Instagram feed post
    ig_id = _discover_ig(c)
    if not ig_id:
        log.append("⚠️ No linked Instagram Business account found on the Page — skipped IG.")
    else:
        ig_cap = f"{caption}\n\n➡️ Free quote — link in bio or: {c['lead']}"
        try:
            create = _post(f"{c['graph']}/{ig_id}/media",
                           {"image_url": c["image"], "caption": ig_cap, "access_token": c["token"]})
            cid = create.get("id")
            if not cid:
                log.append(f"❌ Instagram container failed: {create}")
            else:
                pub = _post(f"{c['graph']}/{ig_id}/media_publish",
                            {"creation_id": cid, "access_token": c["token"]})
                log.append(f"✅ Instagram posted (media id: {pub.get('id')})")
        except Exception as exc:
            log.append(f"❌ Instagram failed: {exc}")
        if c["story"]:
            try:
                s = _post(f"{c['graph']}/{ig_id}/media",
                          {"image_url": c["image"], "media_type": "STORIES", "access_token": c["token"]})
                if s.get("id"):
                    sp = _post(f"{c['graph']}/{ig_id}/media_publish",
                               {"creation_id": s["id"], "access_token": c["token"]})
                    log.append(f"✅ Instagram story posted (id: {sp.get('id')})")
            except Exception as exc:
                log.append(f"❌ Instagram story failed: {exc}")
    return log


if __name__ == "__main__":
    print("\n".join(run()))
