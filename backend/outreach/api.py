"""HTTP routing for /api/outreach/* and the Telnyx webhook, used by markethub_server."""
from __future__ import annotations

import hmac
import json
import re
from typing import Any

from .senders import verify_telnyx_signature
from .service import OutreachError, OutreachService

_service: OutreachService | None = None


def get_service() -> OutreachService:
    global _service
    if _service is None:
        _service = OutreachService()
    return _service


def _authorized(service: OutreachService, headers: Any) -> bool:
    token = service.settings.admin_token
    if not token:
        return True
    supplied = headers.get("X-Outreach-Token", "")
    return hmac.compare_digest(supplied, token)


def handle(method: str, path: str, query: dict[str, list[str]], headers: Any, raw_body: bytes) -> tuple[int, dict]:
    service = get_service()

    if path == "/api/outreach/webhooks/telnyx" and method == "POST":
        return _telnyx_webhook(service, headers, raw_body)

    if not _authorized(service, headers):
        return 401, {"error": "unauthorized"}

    try:
        body: dict[str, Any] = json.loads(raw_body or b"{}") if method == "POST" else {}
    except json.JSONDecodeError:
        return 400, {"error": "invalid JSON"}

    try:
        if method == "GET":
            if path == "/api/outreach/status":
                return 200, service.status()
            if path == "/api/outreach/leads":
                return 200, {"leads": service.store.list_leads((query.get("trade") or [None])[0])}
            if path == "/api/outreach/drafts":
                return 200, {"drafts": service.store.list_drafts((query.get("status") or [None])[0])}
            if path == "/api/outreach/optouts":
                return 200, {"opt_outs": service.store.list_opt_outs()}
            if path == "/api/outreach/inbound":
                return 200, {"messages": service.store.list_inbound()}

        if method == "POST":
            if path == "/api/outreach/search":
                trade, city = body.get("trade", "").strip(), body.get("city", "").strip()
                if not trade or not city:
                    return 400, {"error": "trade and city are required"}
                max_results = max(1, min(int(body.get("max_results", 20)), 60))
                return 200, {"leads": service.search(trade, city, max_results)}
            if path == "/api/outreach/leads":
                return 200, {"lead": service.add_lead(body)}
            if m := re.fullmatch(r"/api/outreach/leads/(\d+)/email", path):
                service.store.update_lead_email(int(m[1]), str(body.get("email", "")))
                return 200, {"lead": service.store.get_lead(int(m[1]))}
            if m := re.fullmatch(r"/api/outreach/leads/(\d+)/draft", path):
                return 200, {"drafts": service.draft(int(m[1]))}
            if m := re.fullmatch(r"/api/outreach/drafts/(\d+)/send", path):
                return 200, {"draft": service.send(int(m[1]), body.get("body"), body.get("subject"))}
            if m := re.fullmatch(r"/api/outreach/drafts/(\d+)/skip", path):
                service.store.mark_draft(int(m[1]), "skipped")
                return 200, {"draft": service.store.get_draft(int(m[1]))}
            if path == "/api/outreach/optouts":
                contact = str(body.get("contact", "")).strip()
                if not contact:
                    return 400, {"error": "contact is required"}
                service.store.add_opt_out(contact, body.get("reason") or "manual")
                return 200, {"ok": True}
    except OutreachError as exc:
        return exc.status, {"error": str(exc)}

    return 404, {"error": "not_found"}


def _telnyx_webhook(service: OutreachService, headers: Any, raw_body: bytes) -> tuple[int, dict]:
    public_key = service.settings.telnyx_public_key
    if public_key:
        ok = verify_telnyx_signature(
            public_key,
            headers.get("telnyx-signature-ed25519", ""),
            headers.get("telnyx-timestamp", "0"),
            raw_body,
        )
        if not ok:
            return 401, {"error": "bad signature"}
    try:
        event = json.loads(raw_body or b"{}").get("data", {})
    except json.JSONDecodeError:
        return 400, {"error": "invalid JSON"}
    if event.get("event_type") != "message.received":
        return 200, {"ignored": event.get("event_type")}
    payload = event.get("payload", {})
    from_number = payload.get("from", {}).get("phone_number", "")
    text = payload.get("text", "")
    if not from_number:
        return 400, {"error": "missing sender"}
    return 200, {"result": service.handle_inbound_sms(from_number, text)}
