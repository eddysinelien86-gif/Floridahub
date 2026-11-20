"""Start the Print Lab dashboard (if it isn't already running) and open it in its own
app window. This is what the desktop icon runs."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PRINTLAB_PORT", "8765"))
URL = f"http://localhost:{PORT}"


def running() -> bool:
    try:
        with urllib.request.urlopen(URL + "/api/designs", timeout=1) as r:
            return r.status == 200
    except OSError:
        return False


def start_server() -> None:
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    log = open(os.path.join(ROOT, "out", "dashboard.log"), "a")
    py = sys.executable
    kw: dict = {"cwd": ROOT, "stdout": log, "stderr": log, "stdin": subprocess.DEVNULL}
    if sys.platform.startswith("win"):
        pyw = os.path.join(os.path.dirname(py), "pythonw.exe")
        py = pyw if os.path.isfile(pyw) else py
        kw["creationflags"] = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
    else:
        kw["start_new_session"] = True
    subprocess.Popen([py, os.path.join(ROOT, "dashboard.py"), "--no-browser", "--port", str(PORT)], **kw)


def find_app_browser() -> str | None:
    """Chrome-family browsers can open a page as a standalone app window."""
    names = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
             "microsoft-edge", "microsoft-edge-stable", "brave-browser", "chrome", "msedge"]
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    pf = [os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData")]
    candidates = [os.path.join(b, *p) for b in pf if b for p in (
        ("Google", "Chrome", "Application", "chrome.exe"),
        ("Microsoft", "Edge", "Application", "msedge.exe"),
        ("BraveSoftware", "Brave-Browser", "Application", "brave.exe"))]
    candidates += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                   "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                   "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                   "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    return next((c for c in candidates if os.path.isfile(c)), None)


def main() -> None:
    if not running():
        start_server()
        for _ in range(60):
            if running():
                break
            time.sleep(0.25)
        else:
            print(f"The dashboard did not start. See {os.path.join(ROOT, 'out', 'dashboard.log')}")
            sys.exit(1)
    browser = find_app_browser()
    if browser:
        subprocess.Popen([browser, f"--app={URL}", "--window-size=1600,950"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        webbrowser.open(URL)


if __name__ == "__main__":
    main()
