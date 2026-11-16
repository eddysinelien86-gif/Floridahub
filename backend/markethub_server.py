from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

import trends as trend_finder
from database import (
    fetch_dashboard_payload,
    fetch_trends,
    init_db,
    set_trend_status,
    store_trends,
)

HOST = "0.0.0.0"
PORT = int(os.environ.get("MARKETHUB_PORT", "8000"))


class MarketHubHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, filename: str) -> None:
        file_path = (WEB_DIR / filename).resolve()
        # Guard against path traversal: must stay inside WEB_DIR.
        if WEB_DIR not in file_path.parents or not file_path.is_file():
            self._send_json({"error": "not_found"}, status=404)
            return
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json({"status": "ok", "service": "MarketHub"})
            return

        if path in ("/", "/phone", "/phone.html"):
            self._send_html("phone.html")
            return

        if path in ("/dashboard", "/index.html"):
            self._send_html("index.html")
            return

        if path == "/api/dashboard":
            self._send_json(fetch_dashboard_payload())
            return

        if path == "/api/trends":
            self._send_json({"trends": fetch_trends()})
            return

        self._send_json({"error": "not_found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length else ""
        data = json.loads(raw_body or "{}")

        if path == "/api/trends/refresh":
            brand = str(data.get("brand") or trend_finder.DEFAULT_BRAND)
            limit = int(data.get("limit", 12))
            payload = trend_finder.gather_trends(limit=limit, brand=brand)
            inserted = store_trends(payload)
            self._send_json(
                {
                    "generated_at": payload["generated_at"],
                    "fetched": payload["count"],
                    "inserted": inserted,
                    "sources": payload["sources"],
                    "trends": fetch_trends(),
                }
            )
            return

        if path == "/api/trends/status":
            trend_id = data.get("id")
            status = str(data.get("status", "")).strip()
            allowed = {"draft", "approved", "posted", "skipped"}
            if not isinstance(trend_id, int) or status not in allowed:
                self._send_json({"error": "bad_request"}, status=400)
                return
            changed = set_trend_status(trend_id, status)
            self._send_json({"updated": changed, "id": trend_id, "status": status})
            return

        if path != "/api/ai/generate":
            self._send_json({"error": "not_found"}, status=404)
            return

        prompt = str(data.get("prompt", "")).strip().lower()

        if "caption" in prompt:
            response = {
                "text": "Capture the energy of the launch with a warm, confident caption that highlights transformation and momentum.",
                "mode": "caption",
            }
        elif "hashtag" in prompt:
            response = {
                "text": "#GrowthMindset #ModernBusiness #DigitalMarketing #BrandMomentum #AudienceFirst",
                "mode": "hashtag",
            }
        elif "review" in prompt:
            response = {
                "text": "Thank you for your feedback. We appreciate the trust you placed in us and look forward to helping your business grow.",
                "mode": "review",
            }
        else:
            response = {
                "text": f"A polished marketing idea for '{prompt or 'your business'}' could be a short video series featuring customer wins and behind-the-scenes momentum.",
                "mode": "idea",
            }

        self._send_json(response)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def run_server() -> None:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), MarketHubHandler)
    print(f"MarketHub backend listening on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
