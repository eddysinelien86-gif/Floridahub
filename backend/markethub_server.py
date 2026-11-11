from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from agents import run_content_agent
from ai import generate as ai_generate
from database import (
    delete_draft,
    fetch_dashboard_payload,
    fetch_leadcount,
    init_db,
    list_drafts,
)

HOST = "0.0.0.0"
PORT = int(os.environ.get("MARKETHUB_PORT", "8000"))
WEB_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web"))


class MarketHubHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        # CORS preflight for cross-origin POSTs from the web dashboard.
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _serve_web(self, filename: str, content_type: str) -> None:
        full = os.path.normpath(os.path.join(WEB_DIR, filename))
        if not full.startswith(WEB_DIR) or not os.path.isfile(full):
            self._send_json({"error": "not_found"}, status=404)
            return
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
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

        if path == "/api/leadcount":
            self._send_json(fetch_leadcount())
            return

        if path == "/api/drafts":
            self._send_json({"drafts": list_drafts()})
            return

        if path in ("/", "/index.html"):
            self._serve_web("index.html", "text/html; charset=utf-8")
            return

        self._send_json({"error": "not_found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length else ""
        data = json.loads(raw_body or "{}")

        if path == "/api/ai/generate":
            prompt = str(data.get("prompt", "")).strip()
            self._send_json(ai_generate(prompt))
            return

        if path == "/api/agents/content":
            # Content Agent: auto-write a batch of insulation post drafts.
            self._send_json(run_content_agent(data.get("n", 3)))
            return

        if path == "/api/drafts/delete":
            delete_draft(int(data.get("id", 0)))
            self._send_json({"ok": True})
            return

        self._send_json({"error": "not_found"}, status=404)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def run_server() -> None:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), MarketHubHandler)
    print(f"MarketHub backend listening on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
