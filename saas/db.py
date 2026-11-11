"""Database layer that works with SQLite (local) and Postgres (production).

If DATABASE_URL is set (e.g. a free Neon/Render Postgres), it uses Postgres so
data persists across redeploys. Otherwise it falls back to a local SQLite file
for development. All queries use '?' placeholders; they're translated to '%s'
for Postgres automatically.
"""

from __future__ import annotations

import os
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))
if USE_PG and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saas.db")

if USE_PG:
    import psycopg
    from psycopg.rows import dict_row


def _conn():
    if USE_PG:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _sql(sql: str) -> str:
    return sql.replace("?", "%s") if USE_PG else sql


def query(sql: str, params: tuple = ()) -> list[dict]:
    conn = _conn()
    try:
        if USE_PG:
            cur = conn.cursor()
            cur.execute(_sql(sql), params)
            return list(cur.fetchall())
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = (), returning: bool = False):
    """Run INSERT/UPDATE/DELETE. With returning=True, returns the new row id."""
    conn = _conn()
    try:
        if USE_PG:
            cur = conn.cursor()
            cur.execute(_sql(sql) + (" RETURNING id" if returning else ""), params)
            new_id = cur.fetchone()["id"] if returning else None
            conn.commit()
            return new_id
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid if returning else None
    finally:
        conn.close()


def init_schema() -> None:
    pk = "SERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    ts = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP" if USE_PG else "TEXT DEFAULT CURRENT_TIMESTAMP"
    stmts = [
        f"""CREATE TABLE IF NOT EXISTS tenants (
            id {pk}, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
            tagline TEXT DEFAULT 'Free quote — tell us about your project',
            plan TEXT DEFAULT 'trial', stripe_customer_id TEXT,
            created_at {ts})""",
        f"""CREATE TABLE IF NOT EXISTS users (
            id {pk}, tenant_id INTEGER NOT NULL, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, created_at {ts})""",
        f"""CREATE TABLE IF NOT EXISTS leads (
            id {pk}, tenant_id INTEGER NOT NULL, name TEXT, contact TEXT,
            service TEXT, status TEXT DEFAULT 'New', created_at {ts})""",
        f"""CREATE TABLE IF NOT EXISTS reviews (
            id {pk}, tenant_id INTEGER NOT NULL, author TEXT, rating INTEGER DEFAULT 5,
            comment TEXT, created_at {ts})""",
        f"""CREATE TABLE IF NOT EXISTS posts (
            id {pk}, tenant_id INTEGER NOT NULL, image_url TEXT, caption TEXT,
            created_at {ts})""",
        f"""CREATE TABLE IF NOT EXISTS homeowners (
            id {pk}, name TEXT, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
            created_at {ts})""",
        f"""CREATE TABLE IF NOT EXISTS favorites (
            id {pk}, homeowner_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL,
            created_at {ts})""",
        f"""CREATE TABLE IF NOT EXISTS social_log (
            id {pk}, tenant_id INTEGER, platforms TEXT, caption TEXT, media_url TEXT,
            created_at {ts})""",
        f"""CREATE TABLE IF NOT EXISTS page_views (
            id {pk}, tenant_id INTEGER NOT NULL, kind TEXT, created_at {ts})""",
        f"""CREATE TABLE IF NOT EXISTS messages (
            id {pk}, tenant_id INTEGER, direction TEXT, phone TEXT, body TEXT,
            created_at {ts})""",
        f"""CREATE TABLE IF NOT EXISTS prospects (
            id {pk}, tenant_id INTEGER NOT NULL, title TEXT, org TEXT, location TEXT,
            due TEXT, score INTEGER DEFAULT 50, url TEXT, created_at {ts})""",
    ]
    conn = _conn()
    try:
        cur = conn.cursor() if USE_PG else conn
        for s in stmts:
            cur.execute(s)
        conn.commit()
    finally:
        conn.close()
    # Best-effort migrations for databases created before these columns existed.
    # Each runs in its own connection so a failure (column already there) never
    # poisons the rest — important on Postgres, where a bad statement aborts the tx.
    migrations = [
        "ALTER TABLE tenants ADD COLUMN plan TEXT DEFAULT 'trial'",
        "ALTER TABLE tenants ADD COLUMN stripe_customer_id TEXT",
        "ALTER TABLE tenants ADD COLUMN city TEXT",
        "ALTER TABLE tenants ADD COLUMN phone TEXT",
        "ALTER TABLE tenants ADD COLUMN bio TEXT",
        "ALTER TABLE tenants ADD COLUMN services TEXT",
        "ALTER TABLE tenants ADD COLUMN logo_url TEXT",
    ]
    for m in migrations:
        c = _conn()
        try:
            (c.cursor() if USE_PG else c).execute(m)
            c.commit()
        except Exception:
            pass
        finally:
            c.close()
