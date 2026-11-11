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
            hot_leads INTEGER DEFAULT 0,
            drafts INTEGER DEFAULT 0
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
        """
    )

    # Business profile. Change these to your real business any time (or via the
    # dashboard later). hot_leads / drafts feed the ESP32 lead-finder box.
    conn.execute("DELETE FROM profiles")
    conn.execute(
        "INSERT INTO profiles (id, name, tagline, wifi_ssid, wifi_password, hot_leads, drafts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, "Insulation Lead Finders", "Spray foam & insulation — lead generation",
         "MarketHub-Setup", "markethub123", 15, 24),
    )

    # Pipeline overview (shown on Home) + lead sources (shown under Sources).
    conn.execute("DELETE FROM metrics")
    conn.executemany(
        "INSERT INTO metrics (category, label, value, change) VALUES (?, ?, ?, ?)",
        [
            ("analytics", "Hot leads", "15", "+3"),
            ("analytics", "Drafts", "24", "+5"),
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
        "leadboard": {
            "hot_leads": profile["hot_leads"],
            "drafts": profile["drafts"],
        },
        "metrics": [
            {"category": r["category"], "label": r["label"], "value": r["value"], "change": r["change"]}
            for r in metrics
        ],
        "reviews": [
            {
                "platform": r["platform"],
                "rating": r["rating"],
                "author": r["author"],
                "comment": r["comment"],
                "new_alert": bool(r["new_alert"]),
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
    row = conn.execute("SELECT hot_leads, drafts FROM profiles WHERE id = 1").fetchone()
    conn.close()
    return {"hot_leads": row["hot_leads"] if row else 0, "drafts": row["drafts"] if row else 0}
