"""Email alerts for new leads.

Sends an email the moment a lead comes in, using SMTP settings from the
environment. If email isn't configured it just logs (never blocks a lead).

Set in secrets.env:
    ALERT_TO     = where alerts go (e.g. you@gmail.com)
    SMTP_USER    = the sending account (e.g. you@gmail.com)
    SMTP_PASS    = an app password (Gmail: Account > Security > App passwords)
    SMTP_HOST    = smtp.gmail.com   (default)
    SMTP_PORT    = 587              (default)
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def send_lead_alert(name: str, contact: str, service: str) -> None:
    to = os.environ.get("ALERT_TO", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    pw = os.environ.get("SMTP_PASS", "").strip()
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))

    if not (to and user and pw):
        print(f"[alert] new lead — {name or '(no name)'} / {contact} / {service} "
              f"(email not configured; set ALERT_TO/SMTP_USER/SMTP_PASS)")
        return

    msg = EmailMessage()
    msg["Subject"] = f"🔥 New lead: {name or contact}"
    msg["From"] = user
    msg["To"] = to
    msg.set_content(
        "You have a new lead from your form:\n\n"
        f"Name:    {name or '(not given)'}\n"
        f"Contact: {contact or '(not given)'}\n"
        f"Service: {service or '(not given)'}\n\n"
        "Call them fast — the first to respond usually wins the job.\n"
    )
    try:
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(user, pw)
            s.send_message(msg)
        print(f"[alert] emailed new lead to {to}")
    except Exception as exc:
        print(f"[alert] email failed: {exc}")
