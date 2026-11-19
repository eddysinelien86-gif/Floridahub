"""Delivery: Telnyx for SMS, SMTP for email. Both honor dry-run mode."""
from __future__ import annotations

import base64
import smtplib
import time
import uuid
from email.message import EmailMessage

import requests

from .config import Settings

TELNYX_MESSAGES_URL = "https://api.telnyx.com/v2/messages"


class SendError(RuntimeError):
    pass


def send_sms(settings: Settings, to: str, text: str) -> str:
    """Send one SMS via Telnyx. Returns the provider message id."""
    if settings.dry_run:
        return f"dry-run-{uuid.uuid4().hex[:12]}"
    if not settings.sms_configured:
        raise SendError("TELNYX_API_KEY and TELNYX_FROM_NUMBER must be set (or enable OUTREACH_DRY_RUN)")
    payload = {"from": settings.telnyx_from_number, "to": to, "text": text}
    if settings.telnyx_messaging_profile_id:
        payload["messaging_profile_id"] = settings.telnyx_messaging_profile_id
    resp = requests.post(
        TELNYX_MESSAGES_URL,
        json=payload,
        headers={"Authorization": f"Bearer {settings.telnyx_api_key}"},
        timeout=20,
    )
    if resp.status_code >= 300:
        raise SendError(f"Telnyx {resp.status_code}: {resp.text[:300]}")
    return resp.json().get("data", {}).get("id", "")


def send_email(settings: Settings, to: str, subject: str, body: str) -> str:
    """Send one plain-text email via SMTP. Returns the Message-ID."""
    message_id = f"<{uuid.uuid4().hex}@{settings.smtp_from.split('@')[-1] or 'localhost'}>"
    if settings.dry_run:
        return f"dry-run-{message_id}"
    if not settings.email_configured:
        raise SendError("SMTP_HOST and SMTP_FROM must be set (or enable OUTREACH_DRY_RUN)")
    if not settings.company_address:
        raise SendError("OUTREACH_COMPANY_ADDRESS is required for commercial email (CAN-SPAM)")
    msg = EmailMessage()
    msg["From"] = f"{settings.sender_name} <{settings.smtp_from}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = message_id
    msg["List-Unsubscribe"] = f"<mailto:{settings.smtp_from}?subject=unsubscribe>"
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        raise SendError(f"SMTP error: {exc}") from exc
    return message_id


def verify_telnyx_signature(public_key_b64: str, signature_b64: str, timestamp: str, raw_body: bytes,
                            tolerance_seconds: int = 300) -> bool:
    """Verify Telnyx's ed25519 webhook signature over '{timestamp}|{body}'."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        if abs(time.time() - int(timestamp)) > tolerance_seconds:
            return False
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        key.verify(base64.b64decode(signature_b64), f"{timestamp}|".encode() + raw_body)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
