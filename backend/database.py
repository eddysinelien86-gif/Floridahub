from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).with_name("markethub.db")


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
            wifi_password TEXT
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
            new_alert INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT NOT NULL,
            contact TEXT NOT NULL,
            status TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            link TEXT,
            summary TEXT,
            source TEXT,
            published TEXT,
            score INTEGER DEFAULT 0,
            caption TEXT,
            hashtags TEXT,
            status TEXT DEFAULT 'draft',
            fetched_at TEXT
        );
        """
    )

    conn.execute(
        "INSERT OR IGNORE INTO profiles (id, name, tagline, wifi_ssid, wifi_password) VALUES (?, ?, ?, ?, ?)",
        (1, "MarketHub", "Growth dashboard for modern businesses", "MarketHub-Setup", "markethub123"),
    )

    conn.execute("DELETE FROM metrics")
    conn.executemany(
        "INSERT INTO metrics (category, label, value, change) VALUES (?, ?, ?, ?)",
        [
            ("social", "Instagram", "18.2K", "+12%"),
            ("social", "TikTok", "9.4K", "+28%"),
            ("social", "Facebook", "7.1K", "+6%"),
            ("social", "YouTube", "4.8K", "+9%"),
            ("analytics", "Website visitors", "42.4K", "+18%"),
            ("analytics", "Social engagement", "93%", "+11%"),
            ("analytics", "Leads generated", "321", "+24%"),
            ("analytics", "Sales", "$18.2K", "+15%"),
        ],
    )

    conn.execute("DELETE FROM reviews")
    conn.executemany(
        "INSERT INTO reviews (platform, rating, author, comment, new_alert) VALUES (?, ?, ?, ?, ?)",
        [
            ("Google", 4.9, "Mina K.", "Fast response and beautifully styled launch content.", 1),
            ("Facebook", 4.8, "Luca P.", "The team made our campaign feel polished and premium.", 1),
        ],
    )

    conn.execute("DELETE FROM customers")
    conn.executemany(
        "INSERT INTO customers (name, company, contact, status) VALUES (?, ?, ?, ?)",
        [
            ("Ava Brooks", "Northstar Studio", "ava@northstar.co", "Lead"),
            ("Jorge Silva", "Lumen Labs", "jorge@lumenlabs.io", "Quote"),
            ("Riley Chen", "Pine & Pixel", "riley@pinepixel.com", "Appointment"),
        ],
    )

    conn.commit()
    conn.close()


def fetch_dashboard_payload() -> dict[str, Any]:
    conn = get_connection()
    profile = conn.execute("SELECT * FROM profiles WHERE id = 1").fetchone()
    metrics = conn.execute("SELECT category, label, value, change FROM metrics ORDER BY id").fetchall()
    reviews = conn.execute("SELECT platform, rating, author, comment, new_alert FROM reviews ORDER BY id").fetchall()
    customers = conn.execute("SELECT name, company, contact, status FROM customers ORDER BY id").fetchall()
    conn.close()

    return {
        "profile": {
            "name": profile["name"],
            "tagline": profile["tagline"],
            "wifi_ssid": profile["wifi_ssid"],
            "wifi_password": profile["wifi_password"],
        },
        "metrics": [
            {
                "category": row["category"],
                "label": row["label"],
                "value": row["value"],
                "change": row["change"],
            }
            for row in metrics
        ],
        "reviews": [
            {
                "platform": row["platform"],
                "rating": row["rating"],
                "author": row["author"],
                "comment": row["comment"],
                "new_alert": bool(row["new_alert"]),
            }
            for row in reviews
        ],
        "customers": [
            {
                "name": row["name"],
                "company": row["company"],
                "contact": row["contact"],
                "status": row["status"],
            }
            for row in customers
        ],
        "cards": [
            "Social Media",
            "Reviews",
            "AI Assistant",
            "Customers",
            "Analytics",
            "QR Center",
            "Marketing",
            "Settings",
        ],
    }


def store_trends(payload: dict[str, Any]) -> int:
    """Persist a batch of gathered trends.

    De-duplicates against what is already stored by (title, link) so a refresh
    does not pile up repeats, and preserves the status of any item that was
    already marked (e.g. 'posted') instead of resetting it to 'draft'.
    Returns the number of new rows inserted.
    """
    trends = payload.get("trends", [])
    fetched_at = payload.get("generated_at")
    conn = get_connection()
    existing = {
        (row["title"], row["link"])
        for row in conn.execute("SELECT title, link FROM trends").fetchall()
    }
    inserted = 0
    for item in trends:
        key = (item.get("title"), item.get("link", ""))
        if key in existing:
            continue
        conn.execute(
            """
            INSERT INTO trends
                (title, link, summary, source, published, score, caption, hashtags, status, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)
            """,
            (
                item.get("title"),
                item.get("link", ""),
                item.get("summary", ""),
                item.get("source", ""),
                item.get("published"),
                int(item.get("score", 0)),
                item.get("caption", ""),
                " ".join(item.get("hashtags", [])),
                fetched_at,
            ),
        )
        inserted += 1
    conn.commit()
    conn.close()
    return inserted


def fetch_trends(limit: int = 25, status: str | None = None) -> list[dict[str, Any]]:
    """Return stored trends, highest score first."""
    conn = get_connection()
    if status:
        rows = conn.execute(
            "SELECT * FROM trends WHERE status = ? ORDER BY score DESC, id DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM trends ORDER BY score DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "link": row["link"],
            "summary": row["summary"],
            "source": row["source"],
            "published": row["published"],
            "score": row["score"],
            "caption": row["caption"],
            "hashtags": row["hashtags"].split() if row["hashtags"] else [],
            "status": row["status"],
            "fetched_at": row["fetched_at"],
        }
        for row in rows
    ]


def set_trend_status(trend_id: int, status: str) -> bool:
    """Mark a trend as draft/approved/posted/skipped. Returns True if a row changed."""
    conn = get_connection()
    cur = conn.execute("UPDATE trends SET status = ? WHERE id = ?", (status, trend_id))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed
