"""printlab dashboard: browse, tweak and rebuild your Bambu Lab designs on a big screen.

    python3 printlab/dashboard.py            # http://localhost:8765, opens your browser
    python3 printlab/dashboard.py --lan      # also reachable from your phone/TV on Wi-Fi

Press F11 in the browser for full screen on the TV.
Uses only the Python standard library (plus printlab's own deps to build designs).
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
DESIGNS = os.path.join(ROOT, "designs")
OUT = os.path.join(ROOT, "out")
PRINTERS = ["P1S", "P1P", "P2S", "X1C", "X1E", "A1", "A1mini", "H2D"]
NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
PARAM_RE = re.compile(r"^(?P<name>[A-Z][A-Z0-9_]*)(?P<sp>\s*=\s*)(?P<value>[-+]?\d+(?:\.\d+)?)(?P<rest>\s*(?:#\s*(?P<comment>.*))?)$")
_build_lock = threading.Lock()


# ---------------------------------------------------------------- designs

def design_path(name: str) -> str | None:
    if not NAME_RE.match(name or ""):
        return None
    p = os.path.join(DESIGNS, name + ".py")
    return p if os.path.isfile(p) else None


def read_params(src: str) -> list[dict]:
    """UPPERCASE = <number>  # comment   lines at module level are editable parameters."""
    params = []
    for line in src.splitlines():
        m = PARAM_RE.match(line)
        if m:
            params.append({"name": m["name"], "value": float(m["value"]),
                           "comment": (m["comment"] or "").strip()})
    return params


def write_params(src: str, values: dict) -> str:
    out = []
    for line in src.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        m = PARAM_RE.match(body)
        if m and m["name"] in values:
            v = float(values[m["name"]])
            txt = str(int(v)) if v.is_integer() else repr(round(v, 4))
            line = f"{m['name']}{m['sp']}{txt}{m['rest']}" + line[len(body):]
        out.append(line)
    return "".join(out)


def describe(name: str) -> dict:
    path = design_path(name)
    src = open(path, encoding="utf-8").read()
    try:
        doc = (ast.get_docstring(ast.parse(src)) or "").strip()
    except SyntaxError:
        doc = ""
    title, _, notes = doc.partition("\n")
    title = title.strip().rstrip(".")
    report = None
    rp = os.path.join(OUT, f"{name}_report.json")
    if os.path.isfile(rp):
        try:
            report = json.load(open(rp, encoding="utf-8"))
        except ValueError:
            report = None
    stale = report is None or os.path.getmtime(path) > report.get("built_at", 0) + 1
    return {"name": name, "title": title or name.replace("_", " ").title(),
            "notes": notes.strip(), "params": read_params(src), "report": report,
            "stale": stale, "modified": os.path.getmtime(path)}


def list_designs() -> list[dict]:
    names = sorted(f[:-3] for f in os.listdir(DESIGNS)
                   if f.endswith(".py") and not f.startswith("_"))
    items = [describe(n) for n in names]
    items.sort(key=lambda d: -max(d["modified"], (d["report"] or {}).get("built_at", 0)))
    return items


def build(name: str, printer: str) -> dict:
    path = design_path(name)
    env = dict(os.environ, BAMBU_PRINTER=printer, MPLBACKEND="Agg")
    t0 = time.time()
    with _build_lock:
        try:
            r = subprocess.run([sys.executable, path], cwd=ROOT, env=env,
                               capture_output=True, text=True, timeout=300)
            ok, log = r.returncode == 0, (r.stdout + r.stderr)[-6000:]
        except subprocess.TimeoutExpired:
            ok, log = False, "Build took longer than 5 minutes and was stopped."
    return {"ok": ok, "log": log, "seconds": round(time.time() - t0, 1)}


def open_in_slicer(name: str) -> dict:
    f = os.path.join(OUT, f"{name}.3mf")
    if not os.path.isfile(f):
        return {"ok": False, "log": "Build the design first."}
    try:
        if sys.platform.startswith("win"):
            os.startfile(f)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", f])
        else:
            subprocess.Popen(["xdg-open", f])
        return {"ok": True, "log": f"Opening {name}.3mf with your default app (Bambu Studio)."}
    except OSError as e:
        return {"ok": False, "log": f"Could not open it: {e}"}


# ---------------------------------------------------------------- http

class Handler(BaseHTTPRequestHandler):
    server_version = "printlab"

    def log_message(self, fmt, *args):  # quieter console
        if "/api/" in (args[0] if args else ""):
            sys.stderr.write("  " + (fmt % args) + "\n")

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _local_only(self) -> bool:
        if self.client_address[0] in ("127.0.0.1", "::1"):
            return True
        self._json({"ok": False, "log": "Only allowed from the laptop itself."}, 403)
        return False

    def do_GET(self):
        url = urlparse(self.path)
        p = unquote(url.path)
        if p in ("/", "/index.html"):
            html = open(os.path.join(ROOT, "dashboard.html"), "rb").read()
            return self._send(200, html, "text/html; charset=utf-8")
        if p == "/api/designs":
            return self._json({"designs": list_designs(), "printers": PRINTERS,
                               "default_printer": os.environ.get("BAMBU_PRINTER", "P1S")})
        if p.startswith("/files/"):
            fname = os.path.basename(p[len("/files/"):])
            f = os.path.join(OUT, fname)
            if not os.path.isfile(f):
                return self._send(404, b"not found", "text/plain")
            ctype = {".png": "image/png", ".stl": "model/stl", ".3mf": "model/3mf",
                     ".json": "application/json", ".txt": "text/plain"}.get(
                os.path.splitext(f)[1], "application/octet-stream")
            extra = {}
            if "download" in url.query:
                extra["Content-Disposition"] = f'attachment; filename="{fname}"'
            return self._send(200, open(f, "rb").read(), ctype, extra)
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self._json({"ok": False, "log": "bad request"}, 400)
        name = data.get("name", "")
        if not design_path(name):
            return self._json({"ok": False, "log": "unknown design"}, 404)
        if p == "/api/build":
            if not self._local_only():
                return
            printer = data.get("printer") if data.get("printer") in PRINTERS else "P1S"
            params = data.get("params") or {}
            try:
                params = {k: float(v) for k, v in params.items() if re.match(r"^[A-Z][A-Z0-9_]*$", k)}
            except (TypeError, ValueError):
                return self._json({"ok": False, "log": "Parameters must be numbers."}, 400)
            if params:
                path = design_path(name)
                src = open(path, encoding="utf-8").read()
                new = write_params(src, params)
                if new != src:
                    open(path, "w", encoding="utf-8").write(new)
            res = build(name, printer)
            res["design"] = describe(name)
            return self._json(res)
        if p == "/api/open":
            if not self._local_only():
                return
            return self._json(open_in_slicer(name))
        self._json({"ok": False, "log": "not found"}, 404)


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "your-laptop-ip"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--lan", action="store_true",
                    help="listen on your Wi-Fi so a phone/TV browser can view it (building stays laptop-only)")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    host = "0.0.0.0" if a.lan else "127.0.0.1"
    srv = ThreadingHTTPServer((host, a.port), Handler)
    url = f"http://localhost:{a.port}"
    print(f"printlab dashboard on {url}")
    if a.lan:
        print(f"  on your Wi-Fi: http://{lan_ip()}:{a.port}  (view only; build from the laptop)")
    print("  press F11 in the browser for full screen. Ctrl+C to stop.")
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
