"""LeadPilot — multi-tenant lead-gen platform for contractors.

Any company signs up, gets an isolated account with its own dashboard and a
public lead form at /t/<their-slug>. Every row is scoped to a tenant_id so
companies never see each other's data. Uses Postgres in production (persists)
and SQLite locally — see db.py.

Run:
    pip install -r requirements.txt
    python app.py              # http://localhost:9000
"""

from __future__ import annotations

import os
import re

from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ai_helper import generate as ai_generate
from db import execute, init_schema, query, query_one

app = Flask(__name__)
app.secret_key = os.environ.get("SAAS_SECRET", "dev-secret-change-me-in-production")

SERVICES = ["Attic insulation", "Spray foam", "Crawlspace", "Energy audit", "Other"]


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "company"


def unique_slug(name: str) -> str:
    base = slugify(name)
    slug, i = base, 1
    while query_one("SELECT 1 AS x FROM tenants WHERE slug = ?", (slug,)):
        i += 1
        slug = f"{base}-{i}"
    return slug


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return query_one(
        "SELECT u.id, u.email, u.tenant_id, t.slug AS tslug, t.name AS tname, t.tagline AS ttag "
        "FROM users u JOIN tenants t ON t.id = u.tenant_id WHERE u.id = ?",
        (uid,),
    )


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
        if query_one("SELECT 1 AS x FROM users WHERE email = ?", (email,)):
            return render_template("signup.html", error="That email is already registered.")
        slug = unique_slug(company)
        tid = execute("INSERT INTO tenants (slug, name) VALUES (?, ?)", (slug, company), returning=True)
        uid = execute(
            "INSERT INTO users (tenant_id, email, password_hash) VALUES (?, ?, ?)",
            (tid, email, generate_password_hash(pw)), returning=True,
        )
        session["uid"] = uid
        return redirect(url_for("dashboard"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        u = query_one("SELECT * FROM users WHERE email = ?", (email,))
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
    leads = query(
        "SELECT name, contact, service, status, created_at FROM leads "
        "WHERE tenant_id = ? ORDER BY id DESC",
        (u["tenant_id"],),
    )
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
    t = query_one("SELECT * FROM tenants WHERE slug = ?", (slug,))
    if not t:
        abort(404)
    return render_template("lead_form.html", tenant=t, services=SERVICES)


@app.route("/t/<slug>/lead", methods=["POST"])
def submit_lead(slug):
    t = query_one("SELECT * FROM tenants WHERE slug = ?", (slug,))
    if not t:
        abort(404)
    execute(
        "INSERT INTO leads (tenant_id, name, contact, service) VALUES (?, ?, ?, ?)",
        (t["id"], request.form.get("name", "").strip(),
         request.form.get("contact", "").strip(), request.form.get("service", "").strip()),
    )
    return render_template("lead_thanks.html", tenant=t)


# Create tables on import so it works under gunicorn (production) too.
init_schema()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("SAAS_PORT", "9000")))
