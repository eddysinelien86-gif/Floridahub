from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade TEXT NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    website TEXT,
    address TEXT,
    city TEXT,
    rating REAL,
    source TEXT NOT NULL DEFAULT 'manual',
    place_id TEXT UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id),
    channel TEXT NOT NULL CHECK (channel IN ('sms', 'email')),
    subject TEXT,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    error TEXT,
    provider_id TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT
);

CREATE TABLE IF NOT EXISTS opt_outs (
    contact TEXT PRIMARY KEY,
    reason TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inbound_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_contact TEXT NOT NULL,
    body TEXT NOT NULL,
    received_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_phone(raw: str | None) -> str | None:
    """Return a US number in E.164 (+1XXXXXXXXXX), or None if it isn't one."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return f"+1{digits}"


def normalize_contact(contact: str) -> str:
    contact = contact.strip()
    if "@" in contact:
        return contact.lower()
    return normalize_phone(contact) or contact


class Store:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:  # commits on success, rolls back on error
                yield conn
        finally:
            conn.close()

    # ---- leads -------------------------------------------------------
    def upsert_lead(self, lead: dict[str, Any]) -> int:
        phone = normalize_phone(lead.get("phone"))
        email = (lead.get("email") or "").strip().lower() or None
        with self._conn() as conn:
            if lead.get("place_id"):
                row = conn.execute("SELECT id FROM leads WHERE place_id = ?", (lead["place_id"],)).fetchone()
                if row:
                    conn.execute(
                        "UPDATE leads SET name=?, phone=COALESCE(?, phone), website=COALESCE(?, website),"
                        " address=?, rating=? WHERE id=?",
                        (lead["name"], phone, lead.get("website"), lead.get("address"), lead.get("rating"), row["id"]),
                    )
                    return int(row["id"])
            cur = conn.execute(
                "INSERT INTO leads (trade, name, phone, email, website, address, city, rating, source, place_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    lead["trade"],
                    lead["name"],
                    phone,
                    email,
                    lead.get("website"),
                    lead.get("address"),
                    lead.get("city"),
                    lead.get("rating"),
                    lead.get("source", "manual"),
                    lead.get("place_id"),
                    now_iso(),
                ),
            )
            return int(cur.lastrowid)

    def update_lead_email(self, lead_id: int, email: str) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE leads SET email=? WHERE id=?", (email.strip().lower() or None, lead_id))

    def get_lead(self, lead_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        return dict(row) if row else None

    def list_leads(self, trade: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM leads"
        args: tuple = ()
        if trade:
            sql += " WHERE trade = ?"
            args = (trade,)
        with self._conn() as conn:
            rows = conn.execute(sql + " ORDER BY id DESC", args).fetchall()
        return [dict(r) for r in rows]

    # ---- drafts ------------------------------------------------------
    def add_draft(self, lead_id: int, channel: str, body: str, subject: str | None = None) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO drafts (lead_id, channel, subject, body, created_at) VALUES (?, ?, ?, ?, ?)",
                (lead_id, channel, subject, body, now_iso()),
            )
            return int(cur.lastrowid)

    def get_draft(self, draft_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        return dict(row) if row else None

    def list_drafts(self, status: str | None = None) -> list[dict[str, Any]]:
        sql = (
            "SELECT d.*, l.name AS lead_name, l.trade, l.phone, l.email, l.website, l.address"
            " FROM drafts d JOIN leads l ON l.id = d.lead_id"
        )
        args: tuple = ()
        if status:
            sql += " WHERE d.status = ?"
            args = (status,)
        with self._conn() as conn:
            rows = conn.execute(sql + " ORDER BY d.id DESC", args).fetchall()
        return [dict(r) for r in rows]

    def edit_draft(self, draft_id: int, body: str, subject: str | None = None) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE drafts SET body=?, subject=COALESCE(?, subject) WHERE id=? AND status='draft'",
                (body, subject, draft_id),
            )

    def mark_draft(self, draft_id: int, status: str, *, error: str | None = None, provider_id: str | None = None) -> None:
        sent_at = now_iso() if status == "sent" else None
        with self._conn() as conn:
            conn.execute(
                "UPDATE drafts SET status=?, error=?, provider_id=?, sent_at=COALESCE(?, sent_at) WHERE id=?",
                (status, error, provider_id, sent_at, draft_id),
            )

    def sent_count_since(self, channel: str, since: datetime) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM drafts WHERE channel=? AND status='sent' AND sent_at >= ?",
                (channel, since.astimezone(timezone.utc).isoformat(timespec="seconds")),
            ).fetchone()
        return int(row["n"])

    def recently_contacted(self, lead_id: int, channel: str, days: int) -> bool:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM drafts WHERE lead_id=? AND channel=? AND status='sent' AND sent_at >= ? LIMIT 1",
                (lead_id, channel, since),
            ).fetchone()
        return row is not None

    # ---- opt-outs ----------------------------------------------------
    def add_opt_out(self, contact: str, reason: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO opt_outs (contact, reason, created_at) VALUES (?, ?, ?)",
                (normalize_contact(contact), reason, now_iso()),
            )

    def remove_opt_out(self, contact: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM opt_outs WHERE contact=?", (normalize_contact(contact),))

    def is_opted_out(self, contact: str | None) -> bool:
        if not contact:
            return False
        with self._conn() as conn:
            row = conn.execute("SELECT 1 FROM opt_outs WHERE contact=?", (normalize_contact(contact),)).fetchone()
        return row is not None

    def list_opt_outs(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM opt_outs ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def log_inbound(self, from_contact: str, body: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO inbound_messages (from_contact, body, received_at) VALUES (?, ?, ?)",
                (normalize_contact(from_contact), body, now_iso()),
            )

    def list_inbound(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM inbound_messages ORDER BY id DESC LIMIT 200").fetchall()
        return [dict(r) for r in rows]
