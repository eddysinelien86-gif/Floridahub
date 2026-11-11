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

# --- Stripe billing config ---------------------------------------------------
# Keys come from the environment (Render env vars / secrets.env), never the repo.
# Without them, the app runs fine in "trial" mode and the Upgrade button explains
# that billing isn't connected yet — so nothing breaks before Stripe is set up.
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "").strip()
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
PLAN_PRICE_LABEL = os.environ.get("PLAN_PRICE_LABEL", "$49.99/mo")
BILLING_ON = bool(STRIPE_SECRET_KEY and STRIPE_PRICE_ID)

if STRIPE_SECRET_KEY:
    import stripe

    stripe.api_key = STRIPE_SECRET_KEY


def _base_url() -> str:
    return (os.environ.get("APP_URL", "").strip() or request.host_url).rstrip("/")


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
        "SELECT u.id, u.email, u.tenant_id, t.slug AS tslug, t.name AS tname, "
        "t.tagline AS ttag, t.plan AS plan "
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
    return render_template(
        "dashboard.html", user=u, leads=leads, form_url=form_url,
        billing_on=BILLING_ON, price_label=PLAN_PRICE_LABEL,
    )


@app.route("/subscribe", methods=["POST"])
def subscribe():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    if not BILLING_ON:
        return render_template(
            "billing_notice.html", user=u,
            message="Billing isn't connected yet. Add your Stripe keys to turn on paid plans.",
        )
    base = _base_url()
    sess = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        success_url=base + "/billing/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=base + "/dashboard",
        client_reference_id=str(u["tenant_id"]),
        customer_email=u["email"],
        allow_promotion_codes=True,
    )
    return redirect(sess.url, code=303)


@app.route("/billing/success")
def billing_success():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    sid = request.args.get("session_id", "")
    if sid and STRIPE_SECRET_KEY:
        try:
            cs = stripe.checkout.Session.retrieve(sid)
            if cs.get("payment_status") == "paid" or cs.get("status") == "complete":
                execute(
                    "UPDATE tenants SET plan = 'pro', stripe_customer_id = ? WHERE id = ?",
                    (cs.get("customer"), u["tenant_id"]),
                )
        except Exception:
            pass
    return redirect(url_for("dashboard"))


@app.route("/webhook", methods=["POST"])
def stripe_webhook():
    """Keeps plan status in sync when subscriptions start or end."""
    if not STRIPE_SECRET_KEY:
        return "", 200
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        else:
            event = request.get_json(force=True, silent=True) or {}
    except Exception:
        return "bad signature", 400
    etype = event.get("type", "")
    obj = (event.get("data", {}) or {}).get("object", {}) or {}
    customer = obj.get("customer")
    if etype == "checkout.session.completed":
        ref = obj.get("client_reference_id")
        if ref:
            execute("UPDATE tenants SET plan = 'pro', stripe_customer_id = ? WHERE id = ?",
                    (customer, ref))
    elif etype in ("customer.subscription.deleted", "customer.subscription.paused"):
        if customer:
            execute("UPDATE tenants SET plan = 'trial' WHERE stripe_customer_id = ?", (customer,))
    elif etype == "customer.subscription.updated":
        status = obj.get("status", "")
        new_plan = "pro" if status in ("active", "trialing") else "trial"
        if customer:
            execute("UPDATE tenants SET plan = ? WHERE stripe_customer_id = ?", (new_plan, customer))
    return "", 200


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
