from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).with_name("markethub.db")


# Demo rows that older versions seeded on every start (removed by init_db).
_DEMO_CUSTOMERS = [
    ("Ava Brooks", "ava@email.com"),
    ("Jorge Silva", "jorge@email.com"),
    ("Riley Chen", "riley@email.com"),
]
_DEMO_REVIEWS = [
    ("Dana R.", "Crew sealed our attic fast — energy bill already dropped."),
    ("Marcus T.", "Great quote, clean install, very professional team."),
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            tagline TEXT NOT NULL,
            wifi_ssid TEXT,
            wifi_password TEXT,
            hot_leads INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            label TEXT NOT NULL,
            value TEXT NOT NULL,
            change TEXT
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            rating REAL NOT NULL,
            author TEXT NOT NULL,
            comment TEXT NOT NULL,
            new_alert INTEGER DEFAULT 0,
            reply TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT NOT NULL,
            contact TEXT NOT NULL,
            status TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            text TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # add hot_leads to older profiles tables that predate it (prevents the
    # "table profiles has no column named hot_leads" error on upgraded DBs)
    try:
        conn.execute("ALTER TABLE profiles ADD COLUMN hot_leads INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Keep whatever is already saved. Earlier versions wiped these tables and
    # re-inserted demo rows on every start, which threw away real leads.
    if conn.execute("SELECT COUNT(*) AS c FROM profiles WHERE id = 1").fetchone()["c"] == 0:
        conn.execute(
            "INSERT INTO profiles (id, name, tagline, wifi_ssid, wifi_password, hot_leads) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (1, "Insulation Lead Finders", "Spray foam & insulation — lead generation",
             "MarketHub-Setup", "markethub123", 0),
        )

    # Migrate older DBs that predate the reply column.
    try:
        conn.execute("ALTER TABLE reviews ADD COLUMN reply TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    # One-time cleanup of the demo rows older versions inserted. Matched on
    # their exact text so real leads and reviews are never touched.
    conn.executemany("DELETE FROM customers WHERE name = ? AND contact = ?", _DEMO_CUSTOMERS)
    conn.executemany("DELETE FROM reviews WHERE author = ? AND comment = ?", _DEMO_REVIEWS)
    # The numbers on the tiles are now counted live (see _live_metrics).
    conn.execute("DELETE FROM metrics")

    # Seed a few starter drafts so the box shows a count before the agent runs.
    if conn.execute("SELECT COUNT(*) AS c FROM drafts").fetchone()["c"] == 0:
        conn.executemany(
            "INSERT INTO drafts (topic, text) VALUES (?, ?)",
            [
                ("attic insulation", "Cold floors and high bills? Your attic may be under-insulated. Book a free inspection this week."),
                ("spray foam", "Spray foam seals the gaps blown-in insulation misses — lower bills, quieter home."),
                ("free inspection", "Free insulation inspection for homeowners this month. We'll show you exactly where heat escapes."),
            ],
        )

    conn.commit()
    conn.close()


# ---------- drafts (used by the Content Agent) ----------
def add_draft(text: str, topic: str = "") -> None:
    conn = get_connection()
    conn.execute("INSERT INTO drafts (topic, text) VALUES (?, ?)", (topic, text))
    conn.commit()
    conn.close()


def list_drafts(limit: int = 30) -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, topic, text, created_at FROM drafts ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [{"id": r["id"], "topic": r["topic"], "text": r["text"], "created_at": r["created_at"]} for r in rows]


def count_drafts() -> int:
    conn = get_connection()
    c = conn.execute("SELECT COUNT(*) AS c FROM drafts").fetchone()["c"]
    conn.close()
    return int(c)


def delete_draft(draft_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
    conn.commit()
    conn.close()


# ---------- reviews (used by the Reply Agent) ----------
def reviews_needing_reply() -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, author, platform, rating, comment FROM reviews "
        "WHERE reply IS NULL OR reply = '' ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_review_reply(review_id: int, text: str) -> None:
    conn = get_connection()
    conn.execute("UPDATE reviews SET reply = ? WHERE id = ?", (text, review_id))
    conn.commit()
    conn.close()


# ---------- leads (used by the Lead-Capture Agent) ----------
def add_lead(name: str, contact: str, service: str) -> int:
    """Add an inbound lead and bump the hot-leads counter."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO customers (name, company, contact, status) VALUES (?, ?, ?, ?)",
        (name or "New lead", service or "Insulation", contact or "", "Hot lead"),
    )
    conn.commit()
    hot = _count_hot_leads(conn)
    conn.close()
    return hot


def _count_hot_leads(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM customers WHERE status = 'Hot lead'").fetchone()
    return int(row["c"])


def _live_metrics(conn: sqlite3.Connection, draft_count: int) -> list[dict[str, str]]:
    """Tile numbers counted from what is really saved — no made-up figures."""
    total = conn.execute("SELECT COUNT(*) AS c FROM customers").fetchone()["c"]
    reviews = conn.execute("SELECT COUNT(*) AS c FROM reviews").fetchone()["c"]
    rows = [
        ("analytics", "Hot leads", str(_count_hot_leads(conn)), ""),
        ("analytics", "Drafts", str(draft_count), ""),
        ("analytics", "Total leads", str(total), ""),
        ("analytics", "Reviews", str(reviews), ""),
        ("social", "Website form", str(total), "live"),
        ("social", "Facebook leads", "—", "not connected"),
        ("social", "Google LSA", "—", "not connected"),
        ("social", "Referrals", "—", "not connected"),
    ]
    return [{"category": c, "label": l, "value": v, "change": ch} for c, l, v, ch in rows]


def fetch_dashboard_payload() -> dict[str, Any]:
    conn = get_connection()
    profile = conn.execute("SELECT * FROM profiles WHERE id = 1").fetchone()
    reviews = conn.execute("SELECT id, platform, rating, author, comment, new_alert, reply FROM reviews ORDER BY id").fetchall()
    customers = conn.execute("SELECT name, company, contact, status FROM customers ORDER BY id").fetchall()
    drafts = list_drafts()
    draft_count = count_drafts()
    metric_list = _live_metrics(conn, draft_count)
    hot_leads = _count_hot_leads(conn)
    conn.close()

    return {
        "profile": {
            "name": profile["name"],
            "tagline": profile["tagline"],
            "wifi_ssid": profile["wifi_ssid"],
            "wifi_password": profile["wifi_password"],
        },
        "leadboard": {"hot_leads": hot_leads, "drafts": draft_count},
        "public_url": os.environ.get("MARKETHUB_PUBLIC_URL", ""),
        "metrics": metric_list,
        "drafts": drafts,
        "reviews": [
            {
                "id": r["id"], "platform": r["platform"], "rating": r["rating"], "author": r["author"],
                "comment": r["comment"], "new_alert": bool(r["new_alert"]), "reply": r["reply"] or "",
            }
            for r in reviews
        ],
        "customers": [
            {"name": r["name"], "company": r["company"], "contact": r["contact"], "status": r["status"]}
            for r in customers
        ],
        "cards": [
            "Lead Sources", "Reviews", "AI Assistant", "Customers",
            "Analytics", "QR Center", "Marketing", "Settings",
        ],
    }


def fetch_leadcount() -> dict[str, int]:
    """Tiny payload for the ESP32 lead-finder box."""
    conn = get_connection()
    hot = _count_hot_leads(conn)
    conn.close()
    return {"hot_leads": hot, "drafts": count_drafts()}
