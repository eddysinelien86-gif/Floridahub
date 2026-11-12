"""SQLite storage and link parsing for the Florida Water 2.0 video hub.

Videos are never downloaded or re-hosted. A submission stores a link to the
original post on a supported platform, and the site plays it through that
platform's official embed player.
"""
from __future__ import annotations

import os
import re
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DB_PATH = Path(os.environ.get("HUB_DB", Path(__file__).with_name("hub.db")))

_ID = r"[A-Za-z0-9_-]"


def parse_video_url(url: str) -> dict | None:
    """Turn a share link into provider, embed URL and thumbnail.

    Returns None when the link is not from a supported platform. The embed URL
    is always built here from the extracted ID, so a submitter can never make
    the site frame an arbitrary page.
    """
    try:
        parts = urlparse(url.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower()
    for prefix in ("www.", "m."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    path = parts.path

    if host in ("youtube.com", "music.youtube.com", "youtu.be"):
        vid = None
        if host == "youtu.be":
            m = re.fullmatch(rf"/({_ID}{{11}})", path)
            vid = m.group(1) if m else None
        elif path == "/watch":
            cand = parse_qs(parts.query).get("v", [""])[0]
            vid = cand if re.fullmatch(rf"{_ID}{{11}}", cand) else None
        else:
            m = re.fullmatch(rf"/(?:shorts|embed|live)/({_ID}{{11}})", path)
            vid = m.group(1) if m else None
        if not vid:
            return None
        return {
            "provider": "youtube",
            "video_ref": vid,
            "embed_url": f"https://www.youtube-nocookie.com/embed/{vid}",
            "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "source_url": f"https://www.youtube.com/watch?v={vid}",
        }

    if host == "vimeo.com":
        m = re.fullmatch(r"/(\d{5,12})", path.rstrip("/"))
        if not m:
            return None
        vid = m.group(1)
        return {
            "provider": "vimeo",
            "video_ref": vid,
            "embed_url": f"https://player.vimeo.com/video/{vid}",
            "thumbnail": "",
            "source_url": f"https://vimeo.com/{vid}",
        }

    if host == "tiktok.com":
        m = re.fullmatch(r"/(@[A-Za-z0-9_.]{1,40})/video/(\d{8,24})", path.rstrip("/"))
        if not m:
            return None
        user, vid = m.groups()
        return {
            "provider": "tiktok",
            "video_ref": vid,
            "embed_url": f"https://www.tiktok.com/embed/v2/{vid}",
            "thumbnail": "",
            "source_url": f"https://www.tiktok.com/{user}/video/{vid}",
        }

    if host == "instagram.com":
        m = re.fullmatch(rf"/(p|reel|reels)/({_ID}{{5,20}})", path.rstrip("/"))
        if not m:
            return None
        code = m.group(2)
        return {
            "provider": "instagram",
            "video_ref": code,
            "embed_url": f"https://www.instagram.com/p/{code}/embed",
            "thumbnail": "",
            "source_url": f"https://www.instagram.com/p/{code}/",
        }

    return None


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, and always close it."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL,
                provider TEXT NOT NULL,
                video_ref TEXT NOT NULL,
                embed_url TEXT NOT NULL,
                thumbnail TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL,
                submitter_name TEXT NOT NULL DEFAULT '',
                contact TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                featured INTEGER NOT NULL DEFAULT 0,
                sponsored INTEGER NOT NULL DEFAULT 0,
                views INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                published_at INTEGER,
                UNIQUE(provider, video_ref)
            );
            CREATE INDEX IF NOT EXISTS idx_videos_feed ON videos(status, published_at);
            CREATE TABLE IF NOT EXISTS inquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                business TEXT NOT NULL DEFAULT '',
                contact TEXT NOT NULL,
                package TEXT NOT NULL DEFAULT '',
                message TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL
            );
            """
        )


PUBLIC_FIELDS = (
    "id, title, description, category, provider, embed_url, thumbnail, source_url, "
    "submitter_name, featured, sponsored, views, published_at"
)


def create_submission(data: dict, parsed: dict) -> int | None:
    """Insert a pending video. Returns None if that video was already submitted."""
    try:
        with connect() as conn:
            cur = conn.execute(
                """INSERT INTO videos (title, description, category, provider, video_ref,
                   embed_url, thumbnail, source_url, submitter_name, contact, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    data["title"], data["description"], data["category"],
                    parsed["provider"], parsed["video_ref"], parsed["embed_url"],
                    parsed["thumbnail"], parsed["source_url"],
                    data["submitter_name"], data["contact"], int(time.time()),
                ),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def list_videos(category: str = "", query: str = "", sort: str = "new",
                page: int = 1, per_page: int = 24) -> dict:
    where, args = ["status = 'published'"], []
    if category:
        where.append("category = ?")
        args.append(category)
    if query:
        where.append("(title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\')")
        like = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        args += [like, like]
    order = "views DESC, published_at DESC" if sort == "top" else "published_at DESC, id DESC"
    clause = " AND ".join(where)
    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM videos WHERE {clause}", args).fetchone()[0]
        rows = conn.execute(
            f"SELECT {PUBLIC_FIELDS} FROM videos WHERE {clause} ORDER BY {order} LIMIT ? OFFSET ?",
            args + [per_page, (page - 1) * per_page],
        ).fetchall()
        featured = conn.execute(
            f"SELECT {PUBLIC_FIELDS} FROM videos WHERE status = 'published' AND featured = 1 "
            "ORDER BY published_at DESC LIMIT 4"
        ).fetchall()
    return {
        "videos": [dict(r) for r in rows],
        "featured": [dict(r) for r in featured],
        "total": total,
        "page": page,
        "pages": max(1, -(-total // per_page)),
    }


def get_video(video_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            f"SELECT {PUBLIC_FIELDS} FROM videos WHERE id = ? AND status = 'published'", (video_id,)
        ).fetchone()
    return dict(row) if row else None


def add_view(video_id: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE videos SET views = views + 1 WHERE id = ? AND status = 'published'", (video_id,))


def admin_list(status: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM videos WHERE status = ? ORDER BY created_at DESC LIMIT 200", (status,)
        ).fetchall()
    return [dict(r) for r in rows]


ADMIN_ACTIONS = {
    "approve": "UPDATE videos SET status = 'published', published_at = COALESCE(published_at, ?) WHERE id = ?",
    "reject": "UPDATE videos SET status = 'rejected', featured = 0 WHERE id = ?",
    "feature": "UPDATE videos SET featured = 1 WHERE id = ? AND status = 'published'",
    "unfeature": "UPDATE videos SET featured = 0 WHERE id = ?",
    "sponsor": "UPDATE videos SET sponsored = 1 WHERE id = ?",
    "unsponsor": "UPDATE videos SET sponsored = 0 WHERE id = ?",
    "delete": "DELETE FROM videos WHERE id = ?",
}


def admin_action(video_id: int, action: str) -> bool:
    sql = ADMIN_ACTIONS.get(action)
    if not sql:
        return False
    args = (int(time.time()), video_id) if action == "approve" else (video_id,)
    with connect() as conn:
        return conn.execute(sql, args).rowcount > 0


def create_inquiry(data: dict) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO inquiries (name, business, contact, package, message, created_at) VALUES (?,?,?,?,?,?)",
            (data["name"], data["business"], data["contact"], data["package"], data["message"], int(time.time())),
        )
        return cur.lastrowid


def list_inquiries() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM inquiries ORDER BY created_at DESC LIMIT 200").fetchall()
    return [dict(r) for r in rows]
