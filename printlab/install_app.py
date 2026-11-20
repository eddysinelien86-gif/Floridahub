"""Put Print Lab on your desktop and in your app list (Start menu / Applications / app grid).

    python3 printlab/install_app.py            # install
    python3 printlab/install_app.py --remove   # uninstall

Clicking the icon starts the dashboard in the background and opens it in its own window.
"""
from __future__ import annotations

import importlib.util
import os
import plistlib
import shutil
import stat
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
LAUNCH = os.path.join(ROOT, "launch.py")
ASSETS = os.path.join(ROOT, "assets")
APP_NAME = "Print Lab"


def ensure_deps() -> None:
    missing = [m for m in ("manifold3d", "trimesh", "numpy", "matplotlib", "networkx", "lxml", "PIL")
               if importlib.util.find_spec(m) is None]
    if missing:
        print("Installing Python packages:", ", ".join(missing))
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r",
                               os.path.join(ROOT, "requirements.txt")])


# ---------------------------------------------------------------- Windows

def _ps(cmd: str) -> str:
    return subprocess.check_output(["powershell", "-NoProfile", "-Command", cmd], text=True).strip()


def windows(remove: bool) -> list[str]:
    desktop = _ps("[Environment]::GetFolderPath('Desktop')")
    programs = _ps("[Environment]::GetFolderPath('Programs')")
    paths = [os.path.join(desktop, APP_NAME + ".lnk"), os.path.join(programs, APP_NAME + ".lnk")]
    if remove:
        for p in paths:
            if os.path.exists(p):
                os.remove(p)
        return paths
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    target = pyw if os.path.isfile(pyw) else sys.executable
    icon = os.path.join(ASSETS, "printlab.ico")
    for p in paths:
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
              "$s.TargetPath='{t}';$s.Arguments='\"{a}\"';$s.WorkingDirectory='{w}';"
              "$s.IconLocation='{i}';$s.Description='Design and print parts on your Bambu Lab';$s.Save()"
              ).format(lnk=p.replace("'", "''"), t=target.replace("'", "''"),
                       a=LAUNCH.replace("'", "''"), w=ROOT.replace("'", "''"), i=icon.replace("'", "''"))
        _ps(ps)
    return paths


# ---------------------------------------------------------------- macOS

def mac(remove: bool) -> list[str]:
    app = os.path.expanduser(f"~/Applications/{APP_NAME}.app")
    link = os.path.expanduser(f"~/Desktop/{APP_NAME}.app")
    if remove:
        if os.path.islink(link) or os.path.exists(link):
            os.remove(link) if os.path.islink(link) else shutil.rmtree(link)
        shutil.rmtree(app, ignore_errors=True)
        return [app, link]
    shutil.rmtree(app, ignore_errors=True)
    os.makedirs(os.path.join(app, "Contents", "MacOS"))
    os.makedirs(os.path.join(app, "Contents", "Resources"))
    exe = os.path.join(app, "Contents", "MacOS", "printlab")
    with open(exe, "w") as f:
        f.write(f'#!/bin/sh\nexec "{sys.executable}" "{LAUNCH}"\n')
    os.chmod(exe, 0o755)
    shutil.copy(os.path.join(ASSETS, "printlab.icns"), os.path.join(app, "Contents", "Resources", "printlab.icns"))
    with open(os.path.join(app, "Contents", "Info.plist"), "wb") as f:
        plistlib.dump({"CFBundleName": APP_NAME, "CFBundleDisplayName": APP_NAME,
                       "CFBundleIdentifier": "local.printlab.dashboard", "CFBundleExecutable": "printlab",
                       "CFBundleIconFile": "printlab", "CFBundlePackageType": "APPL",
                       "CFBundleVersion": "1.0", "LSUIElement": True}, f)
    if os.path.islink(link):
        os.remove(link)
    if not os.path.exists(link):
        os.symlink(app, link)
    return [app, link]


# ---------------------------------------------------------------- Linux

def _try(cmd: list[str]) -> None:
    """Run an optional desktop helper; fine if this desktop doesn't have it."""
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except OSError:
        pass


def linux(remove: bool) -> list[str]:
    try:
        desktop = subprocess.check_output(["xdg-user-dir", "DESKTOP"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        desktop = os.path.expanduser("~/Desktop")
    apps = os.path.expanduser("~/.local/share/applications")
    paths = [os.path.join(apps, "printlab.desktop"), os.path.join(desktop, "printlab.desktop")]
    if remove:
        for p in paths:
            if os.path.exists(p):
                os.remove(p)
        return paths
    entry = (
        "[Desktop Entry]\nType=Application\nName=Print Lab\n"
        "Comment=Design and print parts on your Bambu Lab\n"
        f'Exec="{sys.executable}" "{LAUNCH}"\nPath={ROOT}\n'
        f"Icon={os.path.join(ASSETS, 'printlab.png')}\nTerminal=false\n"
        "Categories=Graphics;3DGraphics;Engineering;\nStartupWMClass=localhost\n")
    for p in paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(entry)
        os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    _try(["gio", "set", paths[1], "metadata::trusted", "true"])  # GNOME: allow launching
    _try(["update-desktop-database", apps])
    return paths


def main() -> None:
    remove = "--remove" in sys.argv
    if not remove:
        ensure_deps()
    fn = windows if sys.platform.startswith("win") else mac if sys.platform == "darwin" else linux
    paths = fn(remove)
    verb = "Removed" if remove else "Installed"
    print(f"{verb} {APP_NAME}:")
    for p in paths:
        print("  " + p)
    if not remove:
        print("\nDouble-click 'Print Lab' on your desktop, or find it in your app list.")


if __name__ == "__main__":
    main()
