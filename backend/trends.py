"""Trend finder for the Floridahub / MarketHub promo page.

Pulls fresh hip-hop and entertainment headlines from free, no-API-key RSS
sources, scores them by recency and relevance, removes duplicates, and drafts
a ready-to-post caption plus hashtags for each one.

Standard-library only (urllib + xml) so it runs anywhere the rest of the
backend runs, including a Raspberry Pi, with no extra installs. Outbound
requests honor the http(s)_proxy environment variables automatically.
"""

from __future__ import annotations

import html
import re
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree

# Default brand voice. Override by passing brand=... into the generators.
DEFAULT_BRAND = "Floridahub"

# Free RSS sources. Google News search feeds are reliable, proxy-friendly, and
# let us target topics directly. Add or remove lines to retune the beat.
SOURCES: list[tuple[str, str]] = [
    ("Google News: Hip-Hop", "https://news.google.com/rss/search?q=hip+hop+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: Rap", "https://news.google.com/rss/search?q=rap+music+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: Entertainment", "https://news.google.com/rss/search?q=entertainment+news+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: Florida Culture", "https://news.google.com/rss/search?q=Florida+music+OR+Florida+rapper+when:7d&hl=en-US&gl=US&ceid=US:en"),
    ("XXL", "https://www.xxlmag.com/feed/"),
    ("HotNewHipHop", "https://www.hotnewhiphop.com/rss/all"),
]

# Words that mark a story as on-beat for a hip-hop / entertainment page.
RELEVANCE_KEYWORDS = {
    "hip hop": 5, "hip-hop": 5, "rap": 5, "rapper": 5, "album": 3, "mixtape": 3,
    "single": 2, "verse": 2, "freestyle": 3, "drop": 2, "release": 2, "tour": 2,
    "concert": 2, "festival": 2, "chart": 3, "billboard": 3, "grammy": 4,
    "beef": 4, "diss": 4, "feature": 2, "producer": 2, "streaming": 2,
    "viral": 4, "trending": 4, "tiktok": 3, "music video": 3, "collab": 2,
    "florida": 3, "miami": 2, "atlanta": 2,
}

# Hashtag pools. The generator mixes evergreen tags with ones pulled from the
# headline so every post is a little different (repeating identical tag blocks
# is what platforms flag as spammy).
BASE_HASHTAGS = [
    "#Floridahub", "#HipHop", "#Rap", "#Entertainment", "#MusicNews",
    "#NewMusic", "#Culture", "#Trending",
]
KEYWORD_HASHTAGS = {
    "album": "#NewAlbum", "mixtape": "#Mixtape", "tour": "#OnTour",
    "grammy": "#Grammys", "billboard": "#Billboard", "video": "#MusicVideo",
    "florida": "#Florida", "miami": "#Miami", "atlanta": "#Atlanta",
    "viral": "#Viral", "freestyle": "#Freestyle", "producer": "#Producer",
}

# Caption openers (hooks). A scroll-stopping first line matters more than
# anything else for reach, so we rotate through strong ones.
HOOKS = [
    "🚨 This just dropped:",
    "👀 Everybody's talking about this:",
    "🔥 Hot off the timeline:",
    "📰 Today in the culture:",
    "💬 Real question for the comments:",
    "⚡ You didn't hear it from us... okay, you did:",
]

CALLS_TO_ACTION = [
    "Follow {brand} so you never miss a drop. 👇",
    "Tap in with {brand} for the latest every day. 🔔",
    "Save this and share it with someone who needs to know. 🔁",
    "What's your take? Drop it in the comments. 💭",
    "Follow {brand} — we keep you first on everything. 🙌",
]

_USER_AGENT = "FloridahubTrendBot/1.0 (+https://floridahub.local)"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _fetch(url: str, timeout: int = 12) -> bytes:
    """Fetch a URL's bytes, raising on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted RSS hosts)
        return resp.read()


def _clean_text(value: str) -> str:
    """Strip HTML tags/entities and collapse whitespace."""
    if not value:
        return ""
    value = html.unescape(value)
    value = _TAG_RE.sub(" ", value)
    return _WS_RE.sub(" ", value).strip()


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _normalize_title(title: str) -> str:
    """Key used to detect duplicate stories across sources."""
    return re.sub(r"[^a-z0-9]+", "", title.lower())[:80]


def _parse_feed(raw: bytes, source: str) -> list[dict[str, Any]]:
    """Parse an RSS/Atom feed into a list of item dicts."""
    items: list[dict[str, Any]] = []
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return items

    # RSS 2.0: channel/item ; Atom: entry
    nodes = root.findall(".//item")
    is_atom = False
    if not nodes:
        nodes = [n for n in root.iter() if n.tag.endswith("}entry")]
        is_atom = True

    for node in nodes:
        if is_atom:
            title = _find_text(node, "title")
            link = _find_atom_link(node)
            published = _find_text(node, "published") or _find_text(node, "updated")
            summary = _find_text(node, "summary") or _find_text(node, "content")
        else:
            title = _find_text(node, "title")
            link = _find_text(node, "link")
            published = _find_text(node, "pubDate")
            summary = _find_text(node, "description")

        title = _clean_text(title)
        if not title:
            continue
        items.append(
            {
                "title": title,
                "link": (link or "").strip(),
                "summary": _clean_text(summary)[:300],
                "published_dt": _parse_date(published),
                "source": source,
            }
        )
    return items


def _find_text(node: ElementTree.Element, tag: str) -> str:
    for child in node:
        if child.tag == tag or child.tag.endswith("}" + tag):
            return child.text or ""
    return ""


def _find_atom_link(node: ElementTree.Element) -> str:
    for child in node:
        if child.tag.endswith("}link") or child.tag == "link":
            href = child.get("href")
            if href:
                return href
    return ""


def _relevance_score(text: str) -> int:
    lowered = text.lower()
    return sum(weight for word, weight in RELEVANCE_KEYWORDS.items() if word in lowered)


def _recency_score(published: datetime | None) -> int:
    if published is None:
        return 0
    age_hours = (datetime.now(timezone.utc) - published).total_seconds() / 3600
    if age_hours < 6:
        return 10
    if age_hours < 24:
        return 7
    if age_hours < 48:
        return 4
    if age_hours < 72:
        return 2
    return 0


def generate_hashtags(title: str, brand: str = DEFAULT_BRAND, limit: int = 8) -> list[str]:
    tags: list[str] = [f"#{brand.replace(' ', '')}"]
    lowered = title.lower()
    for word, tag in KEYWORD_HASHTAGS.items():
        if word in lowered and tag not in tags:
            tags.append(tag)
    for tag in BASE_HASHTAGS:
        if tag not in tags:
            tags.append(tag)
        if len(tags) >= limit:
            break
    return tags[:limit]


def generate_caption(item: dict[str, Any], brand: str = DEFAULT_BRAND, seed: int = 0) -> str:
    """Draft an engaging, post-ready caption for a story.

    Deterministic given the same seed so re-runs don't reshuffle existing
    drafts. Swap this body for an LLM call later; the shape stays the same.
    """
    title = item["title"]
    hook = HOOKS[seed % len(HOOKS)]
    cta = CALLS_TO_ACTION[seed % len(CALLS_TO_ACTION)].format(brand=brand)
    hashtags = " ".join(generate_hashtags(title, brand=brand))
    return f"{hook} {title}\n\n{cta}\n\n{hashtags}"


def gather_trends(limit: int = 12, brand: str = DEFAULT_BRAND) -> dict[str, Any]:
    """Fetch, score, dedupe, and caption the latest on-beat stories.

    Returns a dict with the ranked items and a per-source status report so the
    caller can see which feeds responded.
    """
    collected: list[dict[str, Any]] = []
    status: list[dict[str, Any]] = []

    for name, url in SOURCES:
        try:
            raw = _fetch(url)
            items = _parse_feed(raw, name)
            status.append({"source": name, "ok": True, "count": len(items)})
            collected.extend(items)
        except Exception as exc:  # noqa: BLE001 - one bad feed must not sink the batch
            status.append({"source": name, "ok": False, "error": str(exc)[:120]})

    # Dedupe by normalized title, keeping the most recent copy.
    best: dict[str, dict[str, Any]] = {}
    for item in collected:
        key = _normalize_title(item["title"])
        if not key:
            continue
        existing = best.get(key)
        if existing is None:
            best[key] = item
            continue
        new_dt = item["published_dt"]
        old_dt = existing["published_dt"]
        if new_dt and (old_dt is None or new_dt > old_dt):
            best[key] = item

    scored: list[dict[str, Any]] = []
    for item in best.values():
        relevance = _relevance_score(f"{item['title']} {item['summary']}")
        recency = _recency_score(item["published_dt"])
        item["score"] = relevance + recency
        scored.append(item)

    scored.sort(key=lambda it: (it["score"], it["published_dt"] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    top = scored[:limit]

    results: list[dict[str, Any]] = []
    for idx, item in enumerate(top):
        published_dt = item["published_dt"]
        results.append(
            {
                "title": item["title"],
                "link": item["link"],
                "summary": item["summary"],
                "source": item["source"],
                "published": published_dt.isoformat() if published_dt else None,
                "score": item["score"],
                "caption": generate_caption(item, brand=brand, seed=idx),
                "hashtags": generate_hashtags(item["title"], brand=brand),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "brand": brand,
        "count": len(results),
        "sources": status,
        "trends": results,
    }


if __name__ == "__main__":
    import json

    payload = gather_trends(limit=8)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
