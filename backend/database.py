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
