"""Email lead alerts for LeadPilot.

When a lead comes in, the company owner gets an email the moment it happens, so
nobody has to sit watching the dashboard. One sending account (set by the
platform operator via env vars) delivers alerts for every company; each alert
goes to that company's own signup email.

Env vars (set on Render):
    SMTP_USER   the Gmail address that sends alerts (e.g. yourbiz@gmail.com)
    SMTP_PASS   a Gmail "App Password" (NOT your normal password)
    SMTP_HOST   default smtp.gmail.com
    SMTP_PORT   default 587
    ALERT_FROM  optional "From" address; defaults to SMTP_USER

If SMTP isn't configured, alerts are skipped gracefully and just logged.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def _cfg() -> dict:
    user = os.environ.get("SMTP_USER", "").strip()
    return {
        "host": os.environ.get("SMTP_HOST", "smtp.gmail.com").strip(),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": user,
        "pw": os.environ.get("SMTP_PASS", "").strip(),
        "frm": os.environ.get("ALERT_FROM", user).strip() or user,
    }


def send_lead_alert(to_email: str, company: str, name: str, contact: str, service: str) -> None:
    c = _cfg()
    if not (c["user"] and c["pw"] and to_email):
        print(f"[notify] new lead for {company} (email alerts not configured): "
              f"{name or '—'} / {contact or '—'} / {service or '—'}")
        return
    msg = EmailMessage()
    msg["Subject"] = f"🔥 New lead for {company}"
    msg["From"] = c["frm"]
    msg["To"] = to_email
    msg.set_content(
        "You've got a new lead on LeadPilot!\n\n"
        f"Name:    {name or '—'}\n"
        f"Contact: {contact or '—'}\n"
        f"Service: {service or '—'}\n\n"
        "Log in to your dashboard to follow up fast — leads close best within the hour.\n"
    )
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(c["host"], c["port"], timeout=20) as s:
            s.starttls(context=ctx)
            s.login(c["user"], c["pw"])
            s.send_message(msg)
        print(f"[notify] lead alert sent to {to_email}")
    except Exception as exc:
        print(f"[notify] alert send failed: {exc}")


def send_email(to_email: str, subject: str, body: str, from_name: str = "") -> None:
    """Generic email (used for messaging leads). Raises if SMTP isn't configured
    or the send fails, so the caller can count successes."""
    c = _cfg()
    if not (c["user"] and c["pw"] and to_email):
        raise RuntimeError("email not configured")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{c['frm']}>" if from_name else c["frm"]
    msg["To"] = to_email
    msg.set_content(body)
    ctx = ssl.create_default_context()
    with smtplib.SMTP(c["host"], c["port"], timeout=20) as s:
        s.starttls(context=ctx)
        s.login(c["user"], c["pw"])
        s.send_message(msg)
