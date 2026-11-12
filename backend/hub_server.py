"""Florida Water 2.0 video hub: serves the website in ../site and its JSON API.

Run:  HUB_ADMIN_TOKEN=choose-a-long-secret python hub_server.py
"""
from __future__ import annotations

import hmac
import json
import mimetypes
import os
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import hub_db

HOST = os.environ.get("HUB_HOST", "0.0.0.0")
PORT = int(os.environ.get("HUB_PORT", "8080"))
SITE_DIR = Path(__file__).resolve().parent.parent / "site"
CONFIG = json.loads(Path(__file__).with_name("hub_config.json").read_text("utf-8"))
ADMIN_TOKEN = os.environ.get("HUB_ADMIN_TOKEN", "")
MAX_BODY = 16 * 1024

# Public forms: at most RATE_LIMIT posts per address per RATE_WINDOW seconds.
RATE_LIMIT, RATE_WINDOW = 10, 3600
_hits: dict[str, list[float]] = {}
_hits_lock = threading.Lock()


def rate_limited(ip: str) -> bool:
    now = time.time()
    with _hits_lock:
        recent = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
        if len(recent) >= RATE_LIMIT:
            _hits[ip] = recent
            return True
        recent.append(now)
        _hits[ip] = recent
        return False


def clean(value: object, limit: int) -> str:
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", str(value or ""))
    return text.strip()[:limit]


class HubHandler(BaseHTTPRequestHandler):
    server_version = "FloridaWaterHub"

    # ---- helpers -----------------------------------------------------
    def _json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0 or length > MAX_BODY:
            return None
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _is_admin(self) -> bool:
        given = self.headers.get("X-Admin-Token", "")
        return bool(ADMIN_TOKEN) and hmac.compare_digest(given.encode(), ADMIN_TOKEN.encode())

    def _static(self, path: str) -> None:
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (SITE_DIR / rel).resolve()
        if SITE_DIR not in target.parents or not target.is_file():
            self._json({"error": "not_found"}, 404)
            return
        body = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' https://i.ytimg.com data:; "
            "frame-src https://www.youtube-nocookie.com https://player.vimeo.com "
            "https://www.tiktok.com https://www.instagram.com; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    # ---- routes ------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        path, qs = url.path, parse_qs(url.query)

        if path == "/api/meta":
            self._json({k: CONFIG[k] for k in ("brand", "tagline", "categories", "packages")})
        elif path == "/api/videos":
            category = clean(qs.get("category", [""])[0], 40)
            if category not in CONFIG["categories"]:
                category = ""
            try:
                page = min(max(int(qs.get("page", ["1"])[0]), 1), 10000)
            except ValueError:
                page = 1
            self._json(hub_db.list_videos(
                category=category,
                query=clean(qs.get("q", [""])[0], 80),
                sort="top" if qs.get("sort", [""])[0] == "top" else "new",
                page=page,
            ))
        elif m := re.fullmatch(r"/api/videos/(\d{1,12})", path):
            video = hub_db.get_video(int(m.group(1)))
            self._json(video or {"error": "not_found"}, 200 if video else 404)
        elif path == "/api/admin/videos":
            if not self._is_admin():
                self._json({"error": "unauthorized"}, 401)
                return
            status = qs.get("status", ["pending"])[0]
            if status not in ("pending", "published", "rejected"):
                status = "pending"
            self._json({"videos": hub_db.admin_list(status)})
        elif path == "/api/admin/inquiries":
            if not self._is_admin():
                self._json({"error": "unauthorized"}, 401)
                return
            self._json({"inquiries": hub_db.list_inquiries()})
        elif path.startswith("/api/"):
            self._json({"error": "not_found"}, 404)
        else:
            self._static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        ip = self.client_address[0]

        if m := re.fullmatch(r"/api/videos/(\d{1,12})/view", path):
            hub_db.add_view(int(m.group(1)))
            self._json({"ok": True})
            return

        if m := re.fullmatch(r"/api/admin/videos/(\d{1,12})", path):
            if not self._is_admin():
                self._json({"error": "unauthorized"}, 401)
                return
            data = self._body() or {}
            ok = hub_db.admin_action(int(m.group(1)), str(data.get("action", "")))
            self._json({"ok": ok}, 200 if ok else 400)
            return

        if path not in ("/api/submissions", "/api/inquiries"):
            self._json({"error": "not_found"}, 404)
            return
        data = self._body()
        if data is None:
            self._json({"error": "Send a JSON body under 16 KB."}, 400)
            return
        if rate_limited(ip):
            self._json({"error": "Too many submissions from this address. Try again in an hour."}, 429)
            return

        if path == "/api/submissions":
            self._submit(data)
        else:
            self._inquire(data)

    def _submit(self, data: dict) -> None:
        parsed = hub_db.parse_video_url(clean(data.get("url"), 300))
        if not parsed:
            self._json({"error": "Paste a YouTube, TikTok, Instagram or Vimeo video link."}, 400)
            return
        fields = {
            "title": clean(data.get("title"), 120),
            "description": clean(data.get("description"), 1000),
            "category": clean(data.get("category"), 40),
            "submitter_name": clean(data.get("submitter_name"), 60),
            "contact": clean(data.get("contact"), 120),
        }
        if len(fields["title"]) < 3:
            self._json({"error": "Give the video a title of at least 3 characters."}, 400)
            return
        if fields["category"] not in CONFIG["categories"]:
            self._json({"error": "Pick a category from the list."}, 400)
            return
        if not fields["contact"]:
            self._json({"error": "Add an email or social handle so we can reach you."}, 400)
            return
        if data.get("rights_confirmed") is not True:
            self._json({"error": "Confirm that this is your video or that you have permission to share it."}, 400)
            return
        new_id = hub_db.create_submission(fields, parsed)
        if new_id is None:
            self._json({"error": "That video has already been submitted."}, 409)
            return
        self._json({"ok": True, "id": new_id}, 201)

    def _inquire(self, data: dict) -> None:
        fields = {
            "name": clean(data.get("name"), 80),
            "business": clean(data.get("business"), 120),
            "contact": clean(data.get("contact"), 120),
            "package": clean(data.get("package"), 40),
            "message": clean(data.get("message"), 2000),
        }
        if not fields["name"] or not fields["contact"]:
            self._json({"error": "Add your name and a way to reach you."}, 400)
            return
        if fields["package"] not in {p["id"] for p in CONFIG["packages"]}:
            fields["package"] = ""
        self._json({"ok": True, "id": hub_db.create_inquiry(fields)}, 201)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def run_server() -> None:
    global ADMIN_TOKEN
    hub_db.init_db()
    if not ADMIN_TOKEN:
        ADMIN_TOKEN = secrets.token_urlsafe(24)
        print(f"HUB_ADMIN_TOKEN not set. One-time admin token for this run: {ADMIN_TOKEN}")
    server = ThreadingHTTPServer((HOST, PORT), HubHandler)
    print(f"Florida Water 2.0 hub on http://{HOST}:{PORT}  (admin page: /#/admin)")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
