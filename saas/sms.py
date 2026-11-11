"""Send SMS via Twilio's REST API (no SDK dependency — plain HTTPS).

Configure in Render:
    TWILIO_SID    your Account SID (starts AC...)
    TWILIO_TOKEN  your Auth Token
    TWILIO_FROM   your Twilio phone number, e.g. +19545551234

send_sms() raises on failure so callers can count successes; is_configured()
lets the UI show/hide the texting features.
"""

from __future__ import annotations

import base64
import os
import urllib.parse
import urllib.request

API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def _cfg() -> dict:
    return {
        "sid": os.environ.get("TWILIO_SID", "").strip(),
        "token": os.environ.get("TWILIO_TOKEN", "").strip(),
        "from": os.environ.get("TWILIO_FROM", "").strip(),
    }


def is_configured() -> bool:
    c = _cfg()
    return bool(c["sid"] and c["token"] and c["from"])


def _normalize(phone: str) -> str:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if phone.strip().startswith("+"):
        return "+" + digits
    if len(digits) == 10:
        return "+1" + digits          # assume US
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return "+" + digits


def send_sms(to_phone: str, body: str) -> None:
    c = _cfg()
    if not is_configured():
        raise RuntimeError("Twilio not configured")
    data = urllib.parse.urlencode(
        {"To": _normalize(to_phone), "From": c["from"], "Body": body}).encode()
    req = urllib.request.Request(API.format(sid=c["sid"]), data=data, method="POST")
    auth = base64.b64encode(f"{c['sid']}:{c['token']}".encode()).decode()
    req.add_header("Authorization", "Basic " + auth)
    with urllib.request.urlopen(req, timeout=25) as r:
        r.read()
