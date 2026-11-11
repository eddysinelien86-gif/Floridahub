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

import datetime
import os
import re
import threading

from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ai_helper import generate as ai_generate
from db import execute, init_schema, query, query_one
from notify import send_lead_alert

app = Flask(__name__)
app.secret_key = os.environ.get("SAAS_SECRET", "dev-secret-change-me-in-production")

SERVICES = ["Attic insulation", "Spray foam", "Crawlspace", "Energy audit", "Other"]

# Cloudinary (photo/video uploads). Cloud name is public; uploads use an
# UNSIGNED preset so no secret is ever needed in the app.
CLOUDINARY_CLOUD = os.environ.get("CLOUDINARY_CLOUD_NAME", "bxnkdclt")
CLOUDINARY_PRESET = os.environ.get("CLOUDINARY_UPLOAD_PRESET", "ai_leadpilot")

# Google social login (optional). Set GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET
# in Render to enable the "Continue with Google" button.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
_oauth = None
if GOOGLE_ENABLED:
    try:
        from authlib.integrations.flask_client import OAuth

        _oauth = OAuth(app)
        _oauth.register(
            name="google",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    except Exception as exc:  # pragma: no cover
        print(f"[google] oauth init failed: {exc}")
        GOOGLE_ENABLED = False

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


def _lead_is_old(created_at, days: int = 30) -> bool:
    """True if a lead's created_at is more than `days` ago. Handles both the
    Postgres datetime and the SQLite text timestamp formats."""
    if not created_at:
        return False
    try:
        if isinstance(created_at, datetime.datetime):
            dt = created_at
        else:
            s = str(created_at).replace("T", " ").split(".")[0].strip()
            dt = datetime.datetime.fromisoformat(s)
        return (datetime.datetime.utcnow() - dt).days >= days
    except Exception:
        return False


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


def current_homeowner():
    hid = session.get("hid")
    if not hid:
        return None
    return query_one("SELECT id, name, email FROM homeowners WHERE id = ?", (hid,))


@app.context_processor
def _inject_homeowner():
    return {"homeowner": current_homeowner(), "google_enabled": GOOGLE_ENABLED}


@app.route("/auth/google")
def auth_google():
    if not GOOGLE_ENABLED:
        abort(404)
    base = (os.environ.get("APP_URL", "").strip() or request.host_url).rstrip("/")
    if base.startswith("http://"):
        base = "https://" + base[len("http://"):]
    return _oauth.google.authorize_redirect(base + "/auth/google/callback")


@app.route("/auth/google/callback")
def auth_google_callback():
    if not GOOGLE_ENABLED:
        abort(404)
    try:
        token = _oauth.google.authorize_access_token()
        info = token.get("userinfo") or {}
        email = (info.get("email") or "").strip().lower()
        name = info.get("name", "")
    except Exception as exc:
        print(f"[google] callback failed: {exc}")
        return redirect(url_for("enter"))
    if not email:
        return redirect(url_for("enter"))
    h = query_one("SELECT id FROM homeowners WHERE email = ?", (email,))
    if h:
        hid = h["id"]
    else:
        hid = execute("INSERT INTO homeowners (name, email, password_hash) VALUES (?, ?, ?)",
                      (name, email, generate_password_hash(os.urandom(16).hex())), returning=True)
    session["hid"] = hid
    return redirect(url_for("directory"))


@app.route("/")
def home():
    return render_template("home.html", user=current_user())


@app.route("/join", methods=["GET", "POST"])
def join():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        if not (email and pw):
            return render_template("join.html", error="Fill in every field.")
        if len(pw) < 6:
            return render_template("join.html", error="Password must be at least 6 characters.")
        if query_one("SELECT 1 AS x FROM homeowners WHERE email = ?", (email,)):
            return render_template("join.html", error="That email is already registered.")
        hid = execute("INSERT INTO homeowners (name, email, password_hash) VALUES (?, ?, ?)",
                      (name, email, generate_password_hash(pw)), returning=True)
        session["hid"] = hid
        return redirect(request.args.get("next") or url_for("directory"))
    return render_template("join.html", error=None)


@app.route("/enter", methods=["GET", "POST"])
def enter():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        h = query_one("SELECT * FROM homeowners WHERE email = ?", (email,))
        if h and check_password_hash(h["password_hash"], pw):
            session["hid"] = h["id"]
            return redirect(request.args.get("next") or url_for("directory"))
        return render_template("enter.html", error="Wrong email or password.")
    return render_template("enter.html", error=None)


@app.route("/leave")
def leave():
    session.pop("hid", None)
    return redirect(url_for("directory"))


@app.route("/favorites")
def favorites():
    h = current_homeowner()
    if not h:
        return redirect(url_for("enter", next=url_for("favorites")))
    rows = query(
        "SELECT t.* FROM favorites f JOIN tenants t ON t.id = f.tenant_id "
        "WHERE f.homeowner_id = ? ORDER BY f.id DESC",
        (h["id"],),
    )
    for t in rows:
        t["review_count"], t["rating"] = _company_stats(t["id"])
    return render_template("favorites.html", companies=rows)


@app.route("/c/<slug>/favorite", methods=["POST"])
def toggle_favorite(slug):
    h = current_homeowner()
    t = query_one("SELECT id FROM tenants WHERE slug = ?", (slug,))
    if not t:
        abort(404)
    if not h:
        return redirect(url_for("enter", next=url_for("company", slug=slug)))
    existing = query_one("SELECT id FROM favorites WHERE homeowner_id = ? AND tenant_id = ?",
                         (h["id"], t["id"]))
    if existing:
        execute("DELETE FROM favorites WHERE id = ?", (existing["id"],))
    else:
        execute("INSERT INTO favorites (homeowner_id, tenant_id) VALUES (?, ?)", (h["id"], t["id"]))
    return redirect(url_for("company", slug=slug))


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
    tid = u["tenant_id"]
    leads = query(
        "SELECT name, contact, service, status, created_at FROM leads "
        "WHERE tenant_id = ? ORDER BY id DESC",
        (tid,),
    )
    for lead in leads:
        lead["is_old"] = _lead_is_old(lead.get("created_at"))
        contact = (lead.get("contact") or "").strip()
        digits = "".join(ch for ch in contact if ch.isdigit())
        if "@" in contact:
            lead["ctype"], lead["tel"] = "email", ""
        elif len(digits) >= 7:
            lead["ctype"], lead["tel"] = "phone", digits
        else:
            lead["ctype"], lead["tel"] = "other", ""
    new_leads = sum(1 for l in leads if l["status"] == "New")
    leads_7d = sum(1 for l in leads if not _lead_is_old(l.get("created_at"), 7))
    email_leads = sum(1 for l in leads if l["ctype"] == "email")
    phone_leads = sum(1 for l in leads if l["ctype"] == "phone")
    review_count, rating = _company_stats(tid)
    reviews = query("SELECT * FROM reviews WHERE tenant_id = ? ORDER BY id DESC", (tid,))[:5]
    posts = query("SELECT * FROM posts WHERE tenant_id = ? ORDER BY id DESC", (tid,))
    socials = query("SELECT * FROM social_log WHERE tenant_id = ? ORDER BY id DESC", (tid,))[:6]
    social_total = query_one("SELECT COUNT(*) AS c FROM social_log WHERE tenant_id = ?", (tid,))["c"]
    pv = query("SELECT created_at FROM page_views WHERE tenant_id = ?", (tid,))
    views_total = len(pv)
    views_7d = sum(1 for r in pv if not _lead_is_old(r.get("created_at"), 7))
    conversion = round(100.0 * len(leads) / views_total, 1) if views_total else 0.0
    base = (os.environ.get("APP_URL", "").strip() or request.host_url).rstrip("/")
    import sms as _sms
    msgs = query("SELECT * FROM messages WHERE tenant_id = ? ORDER BY id DESC", (tid,))[:8]
    stats = {
        "leads": len(leads), "new": new_leads, "leads_7d": leads_7d,
        "reviews": review_count, "rating": rating, "posts": len(posts),
        "socials": social_total, "views": views_total, "views_7d": views_7d,
        "conversion": conversion, "email_leads": email_leads, "phone_leads": phone_leads,
    }
    return render_template(
        "dashboard.html", user=u, leads=leads[:10], stats=stats, reviews=reviews,
        posts=posts[:6], socials=socials, rating=rating, review_count=review_count,
        form_url=base + url_for("public_form", slug=u["tslug"]),
        profile_url=base + url_for("company", slug=u["tslug"]),
        billing_on=BILLING_ON, price_label=PLAN_PRICE_LABEL,
        emailed=request.args.get("emailed"), texted=request.args.get("texted"),
        sms_enabled=_sms.is_configured(), messages=msgs,
    )


def _track_view(tenant_id, kind):
    try:
        execute("INSERT INTO page_views (tenant_id, kind) VALUES (?, ?)", (tenant_id, kind))
    except Exception:
        pass


@app.route("/leads/email", methods=["POST"])
def leads_email():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    subject = request.form.get("subject", "").strip() or f"A message from {u['tname']}"
    body = request.form.get("message", "").strip()
    if not body:
        return redirect(url_for("dashboard"))
    import notify
    recipients = [
        l["contact"] for l in query("SELECT contact FROM leads WHERE tenant_id = ?", (u["tenant_id"],))
        if l["contact"] and "@" in l["contact"]
    ]
    sent = 0
    for to in set(recipients):
        try:
            notify.send_email(to, subject, body, from_name=u["tname"])
            sent += 1
        except Exception:
            pass
    return redirect(url_for("dashboard", emailed=sent))


@app.route("/leads/sms", methods=["POST"])
def leads_sms():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    body = request.form.get("message", "").strip()
    if not body:
        return redirect(url_for("dashboard"))
    import sms as smsmod
    phones = []
    for l in query("SELECT contact FROM leads WHERE tenant_id = ?", (u["tenant_id"],)):
        contact = (l["contact"] or "")
        digits = "".join(ch for ch in contact if ch.isdigit())
        if "@" not in contact and len(digits) >= 10:
            phones.append(contact)
    sent = 0
    for p in set(phones):
        try:
            smsmod.send_sms(p, body)
            execute("INSERT INTO messages (tenant_id, direction, phone, body) VALUES (?, ?, ?, ?)",
                    (u["tenant_id"], "out", p, body))
            sent += 1
        except Exception:
            pass
    return redirect(url_for("dashboard", texted=sent))


@app.route("/sms/incoming", methods=["POST"])
def sms_incoming():
    """Twilio posts here when someone texts your number. Logs the reply so it
    shows on the dashboard. Point your Twilio number's Messaging webhook here."""
    frm = request.form.get("From", "")
    body = request.form.get("Body", "")
    slug = os.environ.get("SMS_TENANT_SLUG", "in-out-insulation-and-spray-foam-of-broward-llc")
    row = query_one("SELECT id FROM tenants WHERE slug = ?", (slug,))
    try:
        execute("INSERT INTO messages (tenant_id, direction, phone, body) VALUES (?, ?, ?, ?)",
                ((row or {}).get("id"), "in", frm, body))
    except Exception:
        pass
    return app.response_class("<Response></Response>", mimetype="text/xml")


@app.route("/team")
def team():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    members = query(
        "SELECT id, email, created_at FROM users WHERE tenant_id = ? ORDER BY id",
        (u["tenant_id"],),
    )
    return render_template("team.html", user=u, members=members, error=None, ok=request.args.get("ok"))


@app.route("/team/add", methods=["POST"])
def team_add():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    email = request.form.get("email", "").strip().lower()
    pw = request.form.get("password", "")
    members = query("SELECT id, email, created_at FROM users WHERE tenant_id = ? ORDER BY id", (u["tenant_id"],))
    if not (email and pw):
        return render_template("team.html", user=u, members=members, error="Enter an email and a password.", ok=None)
    if len(pw) < 6:
        return render_template("team.html", user=u, members=members, error="Password must be at least 6 characters.", ok=None)
    if query_one("SELECT 1 AS x FROM users WHERE email = ?", (email,)):
        return render_template("team.html", user=u, members=members, error="That email is already in use.", ok=None)
    execute("INSERT INTO users (tenant_id, email, password_hash) VALUES (?, ?, ?)",
            (u["tenant_id"], email, generate_password_hash(pw)))
    return redirect(url_for("team", ok=1))


@app.route("/team/remove", methods=["POST"])
def team_remove():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    uid = request.form.get("uid", "")
    count = query_one("SELECT COUNT(*) AS c FROM users WHERE tenant_id = ?", (u["tenant_id"],))["c"]
    # Never remove yourself or the last remaining login.
    if str(uid) != str(u["id"]) and count > 1:
        execute("DELETE FROM users WHERE id = ? AND tenant_id = ?", (uid, u["tenant_id"]))
    return redirect(url_for("team"))


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
    _track_view(t["id"], "form")
    return render_template("lead_form.html", tenant=t, services=SERVICES)


@app.route("/t/<slug>/lead", methods=["POST"])
def submit_lead(slug):
    t = query_one("SELECT * FROM tenants WHERE slug = ?", (slug,))
    if not t:
        abort(404)
    name = request.form.get("name", "").strip()
    contact = request.form.get("contact", "").strip()
    service = request.form.get("service", "").strip()
    execute(
        "INSERT INTO leads (tenant_id, name, contact, service) VALUES (?, ?, ?, ?)",
        (t["id"], name, contact, service),
    )
    # Email every owner of this company, in the background so the thank-you
    # page returns instantly even if the mail server is slow.
    for owner in query("SELECT email FROM users WHERE tenant_id = ?", (t["id"],)):
        threading.Thread(
            target=send_lead_alert,
            args=(owner["email"], t["name"], name, contact, service),
            daemon=True,
        ).start()
    return render_template("lead_thanks.html", tenant=t)


# ---- Directory / company profiles / reviews / work gallery -------------------

def _company_stats(tenant_id):
    r = query_one(
        "SELECT COUNT(*) AS c, COALESCE(AVG(rating), 0) AS avg FROM reviews WHERE tenant_id = ?",
        (tenant_id,),
    )
    return int(r["c"] or 0), round(float(r["avg"] or 0), 1)


@app.route("/directory")
def directory():
    q = request.args.get("q", "").strip()
    companies = query("SELECT * FROM tenants ORDER BY id DESC")
    cards = []
    for c in companies:
        if q and q.lower() not in (
            (c["name"] or "") + " " + (c.get("city") or "") + " " + (c.get("services") or "")
        ).lower():
            continue
        count, avg = _company_stats(c["id"])
        post = query_one("SELECT image_url FROM posts WHERE tenant_id = ? ORDER BY id DESC", (c["id"],))
        cards.append({"t": c, "reviews": count, "rating": avg,
                      "cover": (post or {}).get("image_url")})
    return render_template("directory.html", cards=cards, q=q, user=current_user())


@app.route("/c/<slug>")
def company(slug):
    t = query_one("SELECT * FROM tenants WHERE slug = ?", (slug,))
    if not t:
        abort(404)
    _track_view(t["id"], "profile")
    count, avg = _company_stats(t["id"])
    posts = query("SELECT * FROM posts WHERE tenant_id = ? ORDER BY id DESC", (t["id"],))
    reviews = query("SELECT * FROM reviews WHERE tenant_id = ? ORDER BY id DESC", (t["id"],))
    h = current_homeowner()
    is_fav = bool(h and query_one(
        "SELECT 1 AS x FROM favorites WHERE homeowner_id = ? AND tenant_id = ?", (h["id"], t["id"])))
    return render_template("company.html", t=t, posts=posts, reviews=reviews,
                           review_count=count, rating=avg, user=current_user(), is_fav=is_fav)


@app.route("/c/<slug>/review", methods=["POST"])
def add_review(slug):
    t = query_one("SELECT id FROM tenants WHERE slug = ?", (slug,))
    if not t:
        abort(404)
    author = request.form.get("author", "").strip() or "Anonymous"
    try:
        rating = max(1, min(5, int(request.form.get("rating", "5"))))
    except ValueError:
        rating = 5
    comment = request.form.get("comment", "").strip()
    if comment:
        execute("INSERT INTO reviews (tenant_id, author, rating, comment) VALUES (?, ?, ?, ?)",
                (t["id"], author, rating, comment))
    return redirect(url_for("company", slug=slug))


@app.route("/profile", methods=["GET", "POST"])
def profile():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    if request.method == "POST":
        execute(
            "UPDATE tenants SET tagline = ?, city = ?, phone = ?, bio = ?, services = ?, logo_url = ? "
            "WHERE id = ?",
            (request.form.get("tagline", "").strip(), request.form.get("city", "").strip(),
             request.form.get("phone", "").strip(), request.form.get("bio", "").strip(),
             request.form.get("services", "").strip(), request.form.get("logo_url", "").strip(),
             u["tenant_id"]),
        )
        return redirect(url_for("profile", ok=1))
    t = query_one("SELECT * FROM tenants WHERE id = ?", (u["tenant_id"],))
    posts = query("SELECT * FROM posts WHERE tenant_id = ? ORDER BY id DESC", (u["tenant_id"],))
    return render_template("profile.html", user=u, t=t, posts=posts, ok=request.args.get("ok"),
                           cloud=CLOUDINARY_CLOUD, preset=CLOUDINARY_PRESET)


@app.route("/posts/add", methods=["POST"])
def add_post():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    image_url = request.form.get("image_url", "").strip()
    caption = request.form.get("caption", "").strip()
    if image_url:
        execute("INSERT INTO posts (tenant_id, image_url, caption) VALUES (?, ?, ?)",
                (u["tenant_id"], image_url, caption))
    return redirect(url_for("profile"))


@app.route("/posts/delete", methods=["POST"])
def delete_post():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    execute("DELETE FROM posts WHERE id = ? AND tenant_id = ?",
            (request.form.get("pid", ""), u["tenant_id"]))
    return redirect(url_for("profile"))


@app.route("/health")
def health():
    """Quick status check: which database is in use and whether it's connected."""
    import db
    info = {"database": "postgres (Neon) ✅" if db.USE_PG else "sqlite (TEMPORARY — not saved!) ⚠️"}
    try:
        db.query_one("SELECT 1 AS x")
        info["connected"] = True
        info["companies"] = db.query_one("SELECT COUNT(*) AS c FROM tenants")["c"]
        info["leads"] = db.query_one("SELECT COUNT(*) AS c FROM leads")["c"]
    except Exception as exc:
        info["connected"] = False
        info["error"] = str(exc)[:200]
    return info


_LAST_SOCIAL_LOG = ["(no run yet — trigger a post first)"]


@app.route("/tasks/social-post")
def social_post_task():
    """Hit by a free external cron twice a day to auto-post to FB + IG.
    Protected by CRON_SECRET. Runs in the background so the web request never
    times out; add &show=1 to read the result of the last run."""
    global _LAST_SOCIAL_LOG
    secret = os.environ.get("CRON_SECRET", "").strip()
    if not secret or request.args.get("key", "") != secret:
        abort(403)
    if request.args.get("show"):
        return app.response_class("\n".join(_LAST_SOCIAL_LOG), mimetype="text/plain")
    import threading

    import social_bot

    def _work():
        global _LAST_SOCIAL_LOG
        try:
            _LAST_SOCIAL_LOG = social_bot.run()
        except Exception:
            import traceback
            _LAST_SOCIAL_LOG = ["CRASH:", traceback.format_exc()]
        for ln in _LAST_SOCIAL_LOG:
            print("[social]", ln)

    threading.Thread(target=_work, daemon=True).start()
    return app.response_class(
        "Posting started. Wait about 60 seconds, then open this SAME link with "
        "&show=1 added to the end to see the result.",
        mimetype="text/plain")


# Create tables on import so it works under gunicorn (production) too.
init_schema()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("SAAS_PORT", "9000")))
