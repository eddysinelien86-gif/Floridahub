import base64
import json
import os
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from outreach import api, senders  # noqa: E402
from outreach.config import load_settings  # noqa: E402
from outreach.service import OutreachError, OutreachService  # noqa: E402
from outreach.store import Store, normalize_phone  # noqa: E402


class FakeResponse:
    def __init__(self, status: int, data: dict) -> None:
        self.status_code = status
        self._data = data
        self.text = json.dumps(data)

    def json(self) -> dict:
        return self._data


class OutreachTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "TELNYX_", "OUTREACH_"))}
        self.env = mock.patch.dict(os.environ, env, clear=True)
        self.env.start()
        settings = replace(
            load_settings(),
            db_path=Path(self.tmp.name) / "t.db",
            company="ForeFront Test",
            sender_name="Sam Lee",
            company_address="1 Main St, Sarasota, FL",
            google_places_api_key="test",
        )
        self.service = OutreachService(settings, Store(settings.db_path))
        # Tests should not depend on the wall clock.
        self.service._check_send_window = lambda: None
        self.lead = self.service.add_lead(
            {"trade": "roofing", "name": "Gulf Roofing", "phone": "(941) 555-0100", "email": "Owner@Gulf.test"}
        )

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    def test_normalize_phone(self) -> None:
        self.assertEqual(normalize_phone("(941) 555-0100"), "+19415550100")
        self.assertEqual(normalize_phone("1-941-555-0100"), "+19415550100")
        self.assertIsNone(normalize_phone("555-0100"))

    def test_template_draft_has_opt_out_and_footer(self) -> None:
        drafts = self.service.draft(self.lead["id"])
        sms = next(d for d in drafts if d["channel"] == "sms")
        email = next(d for d in drafts if d["channel"] == "email")
        self.assertEqual(sms["source"], "template")
        self.assertTrue(sms["body"].endswith("Reply STOP to opt out."))
        self.assertLessEqual(len(sms["body"]), 320)
        self.assertIn("ForeFront Test", sms["body"])
        self.assertIn("1 Main St, Sarasota, FL", email["body"])
        self.assertIn("unsubscribe", email["body"].lower())

    def test_dry_run_send_and_no_resend(self) -> None:
        sms = next(d for d in self.service.draft(self.lead["id"]) if d["channel"] == "sms")
        result = self.service.send(sms["id"])
        self.assertEqual(result["status"], "sent")
        self.assertTrue(result["provider_id"].startswith("dry-run"))
        with self.assertRaises(OutreachError):
            self.service.send(sms["id"])
        # A fresh draft to the same lead is blocked by the recontact window.
        sms2 = next(d for d in self.service.draft(self.lead["id"]) if d["channel"] == "sms")
        with self.assertRaises(OutreachError) as ctx:
            self.service.send(sms2["id"])
        self.assertIn("Already contacted", str(ctx.exception))

    def test_opted_out_contact_is_never_sent(self) -> None:
        self.service.store.add_opt_out("941-555-0100", "test")
        sms = next(d for d in self.service.draft(self.lead["id"]) if d["channel"] == "sms")
        with self.assertRaises(OutreachError):
            self.service.send(sms["id"])
        self.assertEqual(self.service.store.get_draft(sms["id"])["status"], "skipped")

    def test_edited_sms_must_keep_stop_line(self) -> None:
        sms = next(d for d in self.service.draft(self.lead["id"]) if d["channel"] == "sms")
        with self.assertRaises(OutreachError):
            self.service.send(sms["id"], body="Hi, want leads?")

    def test_daily_cap(self) -> None:
        self.service.settings = replace(self.service.settings, daily_sms_cap=0)
        sms = next(d for d in self.service.draft(self.lead["id"]) if d["channel"] == "sms")
        with self.assertRaises(OutreachError) as ctx:
            self.service.send(sms["id"])
        self.assertEqual(ctx.exception.status, 429)

    def test_live_sms_calls_telnyx(self) -> None:
        self.service.settings = replace(
            self.service.settings, dry_run=False, telnyx_api_key="KEY", telnyx_from_number="+19415550000"
        )
        sms = next(d for d in self.service.draft(self.lead["id"]) if d["channel"] == "sms")
        with mock.patch.object(senders.requests, "post", return_value=FakeResponse(200, {"data": {"id": "msg-1"}})) as post:
            result = self.service.send(sms["id"])
        self.assertEqual(result["provider_id"], "msg-1")
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["to"], "+19415550100")
        self.assertEqual(sent["from"], "+19415550000")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer KEY")

    def test_inbound_stop_opts_out(self) -> None:
        self.assertEqual(self.service.handle_inbound_sms("+19415550100", "Stop"), "opted_out")
        self.assertTrue(self.service.store.is_opted_out("(941) 555-0100"))
        self.assertEqual(self.service.handle_inbound_sms("+19415550100", "START"), "opted_in")
        self.assertFalse(self.service.store.is_opted_out("+19415550100"))
        self.assertEqual(self.service.handle_inbound_sms("+19415550100", "Sounds interesting"), "logged")

    def test_search_saves_leads(self) -> None:
        places = {"places": [{"id": "p1", "displayName": {"text": "Cool Air"}, "nationalPhoneNumber": "(941) 555-0199",
                              "formattedAddress": "Sarasota, FL", "businessStatus": "OPERATIONAL"},
                             {"id": "p2", "displayName": {"text": "Closed Co"}, "businessStatus": "CLOSED_PERMANENTLY"}]}
        with mock.patch("outreach.leads.requests.post", return_value=FakeResponse(200, places)):
            leads = self.service.search("ac_restoration", "Sarasota, FL", 5)
        self.assertEqual([l["name"] for l in leads], ["Cool Air"])
        self.assertEqual(leads[0]["phone"], "+19415550199")

    def test_telnyx_signature(self) -> None:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        key = Ed25519PrivateKey.generate()
        pub = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        body = json.dumps({"data": {"event_type": "message.received",
                                    "payload": {"from": {"phone_number": "+19415550100"}, "text": "STOP"}}}).encode()
        ts = str(int(time.time()))
        sig = base64.b64encode(key.sign(f"{ts}|".encode() + body)).decode()
        self.service.settings = replace(self.service.settings, telnyx_public_key=pub)

        with mock.patch.object(api, "_service", self.service):
            bad = api.handle("POST", "/api/outreach/webhooks/telnyx", {},
                             {"telnyx-signature-ed25519": sig, "telnyx-timestamp": ts}, body + b" ")
            self.assertEqual(bad[0], 401)
            ok = api.handle("POST", "/api/outreach/webhooks/telnyx", {},
                            {"telnyx-signature-ed25519": sig, "telnyx-timestamp": ts}, body)
        self.assertEqual(ok, (200, {"result": "opted_out"}))

    def test_admin_token_required_when_set(self) -> None:
        self.service.settings = replace(self.service.settings, admin_token="secret")
        with mock.patch.object(api, "_service", self.service):
            self.assertEqual(api.handle("GET", "/api/outreach/leads", {}, {}, b"")[0], 401)
            self.assertEqual(api.handle("GET", "/api/outreach/leads", {}, {"X-Outreach-Token": "secret"}, b"")[0], 200)


if __name__ == "__main__":
    unittest.main()
