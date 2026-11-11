from __future__ import annotations

import base64
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import threading
import time

from agents import run_content_agent, run_reply_agent
from ai import generate as ai_generate
from database import (
    add_lead,
    delete_draft,
    fetch_dashboard_payload,
    fetch_leadcount,
    init_db,
    list_drafts,
)

HOST = "0.0.0.0"
PORT = int(os.environ.get("MARKETHUB_PORT", "8000"))
WEB_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web"))

# Optional login for the dashboard. Set MARKETHUB_PASSWORD to turn it on; the
# public lead form (/lead, POST /api/lead) stays open so customers can submit.
AUTH_USER = os.environ.get("MARKETHUB_USER", "admin")
AUTH_PASS = os.environ.get("MARKETHUB_PASSWORD", "")
PUBLIC_GET = {"/lead", "/health"}
PUBLIC_POST = {"/api/lead"}


class MarketHubHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        if not AUTH_PASS:
            return True  # login disabled when no password is set
        header = self.headers.get("Authorization", "")
        if header.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(header[6:]).decode("utf-8").partition(":")
                if user == AUTH_USER and pw == AUTH_PASS:
                    return True
            except Exception:
                pass
        return False

    def _require_auth(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Insulation Lead Finders"')
        self.send_header("Content-Length", "0")
        self.end_headers()

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

    def _serve_qr(self, data: str) -> None:
        import qrcode

        qr = qrcode.QRCode(border=2)
        qr.add_data(data or "/lead")
        qr.make(fit=True)
        matrix = qr.get_matrix()
        n = len(matrix)
        scale = 8
        rects = []
        for y, row in enumerate(matrix):
            for x, filled in enumerate(row):
                if filled:
                    rects.append(f'<rect x="{x*scale}" y="{y*scale}" width="{scale}" height="{scale}"/>')
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{n*scale}" height="{n*scale}" '
            f'viewBox="0 0 {n*scale} {n*scale}"><rect width="100%" height="100%" fill="#fff"/>'
            f'<g fill="#000">{"".join(rects)}</g></svg>'
        )
        body = svg.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path not in PUBLIC_GET and not self._authed():
            self._require_auth()
            return
        if path == "/api/qr":
            query = parse_qs(urlparse(self.path).query)
            self._serve_qr(query.get("data", [""])[0])
            return

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

        if path == "/lead":
            self._serve_web("lead.html", "text/html; charset=utf-8")
            return

        self._send_json({"error": "not_found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path not in PUBLIC_POST and not self._authed():
            self._require_auth()
            return
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

        if path == "/api/agents/replies":
            # Reply Agent: draft replies for reviews without one.
            self._send_json(run_reply_agent())
            return

        if path == "/api/lead":
            # Lead-Capture Agent: a new inbound lead bumps hot leads.
            hot = add_lead(
                str(data.get("name", "")).strip(),
                str(data.get("contact", "")).strip(),
                str(data.get("service", "")).strip(),
            )
            self._send_json({"ok": True, "hot_leads": hot})
            return

        if path == "/api/drafts/delete":
            delete_draft(int(data.get("id", 0)))
            self._send_json({"ok": True})
            return

        self._send_json({"error": "not_found"}, status=404)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def _scheduler_loop() -> None:
    """Scheduler Agent: periodically run the Content Agent on its own.
    Set MARKETHUB_AUTODRAFT_HOURS=0 to turn it off (default: every 24h)."""
    try:
        hours = float(os.environ.get("MARKETHUB_AUTODRAFT_HOURS", "24"))
    except ValueError:
        hours = 24.0
    if hours <= 0:
        return
    while True:
        time.sleep(hours * 3600)
        try:
            run_content_agent(3)
            print("[scheduler] Content Agent ran — fresh drafts added.")
        except Exception as exc:  # keep the server alive no matter what
            print(f"[scheduler] skipped: {exc}")


def run_server() -> None:
    init_db()
    threading.Thread(target=_scheduler_loop, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), MarketHubHandler)
    print(f"MarketHub backend listening on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
