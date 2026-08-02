from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from database import fetch_dashboard_payload, init_db

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

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json({"status": "ok", "service": "MarketHub"})
            return

        if path == "/api/dashboard":
            self._send_json(fetch_dashboard_payload())
            return

        self._send_json({"error": "not_found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/ai/generate":
            self._send_json({"error": "not_found"}, status=404)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        data = json.loads(raw_body or "{}")
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
