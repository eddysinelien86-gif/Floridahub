"""Outreach workflow: search -> draft -> human review -> send one message, with compliance guards."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from . import drafter, leads, senders
from .config import Settings, load_settings
from .store import Store, normalize_phone

STOP_WORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit", "optout", "opt out", "revoke"}
START_WORDS = {"start", "unstop", "yes"}


class OutreachError(RuntimeError):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class OutreachService:
    def __init__(self, settings: Settings | None = None, store: Store | None = None) -> None:
        self.settings = settings or load_settings()
        self.store = store or Store(self.settings.db_path)

    # ---- discovery & drafting ---------------------------------------
    def search(self, trade: str, city: str, max_results: int = 20) -> list[dict[str, Any]]:
        try:
            found = leads.search_places(self.settings.google_places_api_key, trade, city, max_results)
        except leads.PlacesError as exc:
            raise OutreachError(str(exc), 502) from exc
        saved = []
        for lead in found:
            lead_id = self.store.upsert_lead(lead)
            saved.append(self.store.get_lead(lead_id))
        return saved

    def add_lead(self, data: dict[str, Any]) -> dict[str, Any]:
        if not data.get("name") or not data.get("trade"):
            raise OutreachError("name and trade are required")
        lead_id = self.store.upsert_lead({**data, "source": "manual"})
        return self.store.get_lead(lead_id)

    def draft(self, lead_id: int) -> list[dict[str, Any]]:
        lead = self.store.get_lead(lead_id)
        if not lead:
            raise OutreachError("lead not found", 404)
        copy, source = drafter.draft_for_lead(lead, self.settings)
        ids = []
        if lead.get("phone"):
            ids.append(self.store.add_draft(lead_id, "sms", copy.sms))
        ids.append(self.store.add_draft(lead_id, "email", copy.email_body, copy.email_subject))
        return [{**self.store.get_draft(i), "source": source} for i in ids]

    # ---- sending (one message per call; there is deliberately no bulk send) ---
    def _check_send_window(self) -> None:
        local = datetime.now(ZoneInfo(self.settings.timezone))
        if local.weekday() == 6 or not (self.settings.send_window_start <= local.hour < self.settings.send_window_end):
            raise OutreachError(
                f"Outside sending hours ({self.settings.send_window_start}:00-{self.settings.send_window_end}:00 "
                f"Mon-Sat, {self.settings.timezone}). Try again later.",
                409,
            )

    def _check_daily_cap(self, channel: str) -> None:
        tz = ZoneInfo(self.settings.timezone)
        midnight = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        cap = self.settings.daily_sms_cap if channel == "sms" else self.settings.daily_email_cap
        if self.store.sent_count_since(channel, midnight) >= cap:
            raise OutreachError(f"Daily {channel} cap of {cap} reached", 429)

    def send(self, draft_id: int, body: str | None = None, subject: str | None = None) -> dict[str, Any]:
        draft = self.store.get_draft(draft_id)
        if not draft:
            raise OutreachError("draft not found", 404)
        if draft["status"] != "draft":
            raise OutreachError(f"draft already {draft['status']}", 409)
        if body is not None:
            if draft["channel"] == "sms" and "stop" not in body.lower():
                raise OutreachError("Text messages must keep the 'Reply STOP to opt out.' line")
            self.store.edit_draft(draft_id, body, subject)
            draft = self.store.get_draft(draft_id)

        lead = self.store.get_lead(draft["lead_id"])
        channel = draft["channel"]
        contact = normalize_phone(lead.get("phone")) if channel == "sms" else lead.get("email")
        if not contact:
            raise OutreachError(f"Lead has no {'phone number' if channel == 'sms' else 'email address'}")
        if self.store.is_opted_out(contact):
            self.store.mark_draft(draft_id, "skipped", error="contact opted out")
            raise OutreachError("This contact opted out; message not sent", 409)
        if self.store.recently_contacted(lead["id"], channel, self.settings.recontact_days):
            raise OutreachError(f"Already contacted by {channel} in the last {self.settings.recontact_days} days", 409)
        self._check_send_window()
        self._check_daily_cap(channel)

        try:
            if channel == "sms":
                provider_id = senders.send_sms(self.settings, contact, draft["body"])
            else:
                provider_id = senders.send_email(self.settings, contact, draft["subject"] or "", draft["body"])
        except senders.SendError as exc:
            self.store.mark_draft(draft_id, "failed", error=str(exc))
            raise OutreachError(str(exc), 502) from exc

        self.store.mark_draft(draft_id, "sent", provider_id=provider_id)
        return {**self.store.get_draft(draft_id), "dry_run": self.settings.dry_run}

    # ---- inbound / opt-outs -----------------------------------------
    def handle_inbound_sms(self, from_number: str, text: str) -> str:
        self.store.log_inbound(from_number, text)
        word = " ".join(text.lower().split()).strip(".! ")
        if word in STOP_WORDS:
            self.store.add_opt_out(from_number, f"sms reply: {text[:40]}")
            return "opted_out"
        if word in START_WORDS:
            self.store.remove_opt_out(from_number)
            return "opted_in"
        return "logged"

    def status(self) -> dict[str, Any]:
        s = self.settings
        return {
            "dry_run": s.dry_run,
            "sms_configured": s.sms_configured,
            "email_configured": s.email_configured,
            "places_configured": bool(s.google_places_api_key),
            "claude_configured": bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")),
            "company_address_set": bool(s.company_address),
            "send_window": f"{s.send_window_start}:00-{s.send_window_end}:00 Mon-Sat {s.timezone}",
            "daily_caps": {"sms": s.daily_sms_cap, "email": s.daily_email_cap},
            "trades": list(leads.TRADE_QUERIES),
        }
