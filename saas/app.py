"""MarketHub SaaS — multi-tenant lead-gen platform for contractors.

Any company signs up, gets an isolated account with its own dashboard and a
public lead form at /t/<their-slug>. Every row is scoped to a tenant_id so
companies never see each other's data. This is the sellable version; the
single-business Pi app under backend/ is separate and untouched.

Run:
    pip install -r requirements.txt
    python app.py              # http://localhost:9000
"""

from __future__ import annotations

import os
import re
import sqlite3

from flask import (
    Flask, abort, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from ai_helper import generate as ai_generate

app = Flask(__name__)
app.secret_key = os.environ.get("SAAS_SECRET", "dev-secret-change-me-in-production")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saas.db")

SERVICES = ["Attic insulation", "Spray foam", "Crawlspace", "Energy audit", "Other"]


# ---------------------------------------------------------------- db helpers
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            tagline TEXT DEFAULT 'Free quote — tell us about your project',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            name TEXT,
            contact TEXT,
            service TEXT,
            status TEXT DEFAULT 'New',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    conn.close()


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "company"


def unique_slug(conn: sqlite3.Connection, name: str) -> str:
    base = slugify(name)
    slug, i = base, 1
    while conn.execute("SELECT 1 FROM tenants WHERE slug = ?", (slug,)).fetchone():
        i += 1
        slug = f"{base}-{i}"
    return slug


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    conn = db()
    u = conn.execute(
        "SELECT u.id, u.email, u.tenant_id, t.slug AS tslug, t.name AS tname, t.tagline AS ttag "
        "FROM users u JOIN tenants t ON t.id = u.tenant_id WHERE u.id = ?",
        (uid,),
    ).fetchone()
    conn.close()
    return u


# ---------------------------------------------------------------- routes
@app.route("/")
def home():
    return render_template("home.html", user=current_user())


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        company = request.form.get("company", "").strip()
        if not (email and pw and company):
            return render_template("signup.html", error="Please fill in every field.")
        if len(pw) < 6:
            return render_template("signup.html", error="Password must be at least 6 characters.")
        conn = db()
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            conn.close()
            return render_template("signup.html", error="That email is already registered.")
        slug = unique_slug(conn, company)
        tid = conn.execute("INSERT INTO tenants (slug, name) VALUES (?, ?)", (slug, company)).lastrowid
        conn.execute(
            "INSERT INTO users (tenant_id, email, password_hash) VALUES (?, ?, ?)",
            (tid, email, generate_password_hash(pw)),
        )
        conn.commit()
        uid = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]
        conn.close()
        session["uid"] = uid
        return redirect(url_for("dashboard"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        conn = db()
        u = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        if u and check_password_hash(u["password_hash"], pw):
            session["uid"] = u["id"]
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Wrong email or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
def dashboard():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    conn = db()
    leads = conn.execute(
        "SELECT name, contact, service, status, created_at FROM leads "
        "WHERE tenant_id = ? ORDER BY id DESC",
        (u["tenant_id"],),
    ).fetchall()
    conn.close()
    form_url = request.host_url.rstrip("/") + url_for("public_form", slug=u["tslug"])
    return render_template("dashboard.html", user=u, leads=leads, form_url=form_url)


@app.route("/ai/generate", methods=["POST"])
def ai_generate_route():
    u = current_user()
    if not u:
        return {"error": "auth"}, 401
    data = request.get_json(force=True, silent=True) or {}
    return ai_generate(data.get("prompt", ""), u["tname"])


@app.route("/qr")
def qr():
    import qrcode

    data = request.args.get("data", "/")
    code = qrcode.QRCode(border=2)
    code.add_data(data)
    code.make(fit=True)
    matrix = code.get_matrix()
    n, scale = len(matrix), 8
    rects = "".join(
        f'<rect x="{x*scale}" y="{y*scale}" width="{scale}" height="{scale}"/>'
        for y, row in enumerate(matrix) for x, v in enumerate(row) if v
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{n*scale}" height="{n*scale}">'
        f'<rect width="100%" height="100%" fill="#fff"/><g fill="#000">{rects}</g></svg>'
    )
    return app.response_class(svg, mimetype="image/svg+xml")


@app.route("/t/<slug>")
def public_form(slug):
    conn = db()
    t = conn.execute("SELECT * FROM tenants WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    if not t:
        abort(404)
    return render_template("lead_form.html", tenant=t, services=SERVICES)


@app.route("/t/<slug>/lead", methods=["POST"])
def submit_lead(slug):
    conn = db()
    t = conn.execute("SELECT * FROM tenants WHERE slug = ?", (slug,)).fetchone()
    if not t:
        conn.close()
        abort(404)
    conn.execute(
        "INSERT INTO leads (tenant_id, name, contact, service) VALUES (?, ?, ?, ?)",
        (t["id"], request.form.get("name", "").strip(),
         request.form.get("contact", "").strip(), request.form.get("service", "").strip()),
    )
    conn.commit()
    conn.close()
    return render_template("lead_thanks.html", tenant=t)


# Ensure tables exist on import so it works under gunicorn (production) too.
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("SAAS_PORT", "9000")))
