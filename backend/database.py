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
            new_alert INTEGER DEFAULT 0
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

    conn.execute("DELETE FROM profiles")
    conn.execute(
        "INSERT INTO profiles (id, name, tagline, wifi_ssid, wifi_password, hot_leads) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (1, "Insulation Lead Finders", "Spray foam & insulation — lead generation",
         "MarketHub-Setup", "markethub123", 15),
    )

    conn.execute("DELETE FROM metrics")
    conn.executemany(
        "INSERT INTO metrics (category, label, value, change) VALUES (?, ?, ?, ?)",
        [
            ("analytics", "Hot leads", "15", "+3"),
            ("analytics", "Drafts", "0", ""),   # value is replaced live with the real count
            ("analytics", "Appointments", "9", "+2"),
            ("analytics", "Jobs booked", "$42.6K", "+18%"),
            ("social", "Facebook leads", "142", "+21%"),
            ("social", "Google LSA", "98", "+12%"),
            ("social", "Referrals", "54", "+8%"),
            ("social", "Website form", "61", "+15%"),
        ],
    )

    conn.execute("DELETE FROM reviews")
    conn.executemany(
        "INSERT INTO reviews (platform, rating, author, comment, new_alert) VALUES (?, ?, ?, ?, ?)",
        [
            ("Google", 5.0, "Dana R.", "Crew sealed our attic fast — energy bill already dropped.", 1),
            ("Facebook", 4.9, "Marcus T.", "Great quote, clean install, very professional team.", 1),
        ],
    )

    conn.execute("DELETE FROM customers")
    conn.executemany(
        "INSERT INTO customers (name, company, contact, status) VALUES (?, ?, ?, ?)",
        [
            ("Ava Brooks", "Attic insulation", "ava@email.com", "Hot lead"),
            ("Jorge Silva", "Spray foam quote", "jorge@email.com", "Quote sent"),
            ("Riley Chen", "Crawlspace job", "riley@email.com", "Scheduled"),
        ],
    )

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


def fetch_dashboard_payload() -> dict[str, Any]:
    conn = get_connection()
    profile = conn.execute("SELECT * FROM profiles WHERE id = 1").fetchone()
    metrics = conn.execute("SELECT category, label, value, change FROM metrics ORDER BY id").fetchall()
    reviews = conn.execute("SELECT platform, rating, author, comment, new_alert FROM reviews ORDER BY id").fetchall()
    customers = conn.execute("SELECT name, company, contact, status FROM customers ORDER BY id").fetchall()
    conn.close()

    drafts = list_drafts()
    draft_count = len(drafts)

    metric_list = []
    for r in metrics:
        value = str(draft_count) if r["label"] == "Drafts" else r["value"]
        metric_list.append({"category": r["category"], "label": r["label"], "value": value, "change": r["change"]})

    return {
        "profile": {
            "name": profile["name"],
            "tagline": profile["tagline"],
            "wifi_ssid": profile["wifi_ssid"],
            "wifi_password": profile["wifi_password"],
        },
        "leadboard": {"hot_leads": profile["hot_leads"], "drafts": draft_count},
        "metrics": metric_list,
        "drafts": drafts,
        "reviews": [
            {
                "platform": r["platform"], "rating": r["rating"], "author": r["author"],
                "comment": r["comment"], "new_alert": bool(r["new_alert"]),
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
    row = conn.execute("SELECT hot_leads FROM profiles WHERE id = 1").fetchone()
    conn.close()
    return {"hot_leads": row["hot_leads"] if row else 0, "drafts": count_drafts()}
