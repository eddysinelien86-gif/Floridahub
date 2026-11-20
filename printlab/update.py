"""Update Print Lab on this computer to the newest version (no git needed).

    .venv/bin/python printlab/update.py          # Linux / Mac, from the Floridahub folder

Downloads the latest designs and app from GitHub, keeps your .venv, built files (out/)
and your own photos (inputs/), then rebuilds every design so the dashboard is ready.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

REPO = "eddysinelien86-gif/Floridahub"
BRANCH = os.environ.get("PRINTLAB_BRANCH", "claude/awesome-hopper-trkgkn")
HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)                       # the Floridahub folder
KEEP = {".venv", "out", "inputs", "__pycache__", ".git"}


def main() -> None:
    url = f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip"
    print("Downloading the latest Print Lab...")
    data = urllib.request.urlopen(url, timeout=60).read()
    with tempfile.TemporaryDirectory() as tmp:
        zipfile.ZipFile(io.BytesIO(data)).extractall(tmp)
        src = os.path.join(tmp, os.listdir(tmp)[0])
        for name in os.listdir(src):
            s, d = os.path.join(src, name), os.path.join(TOP, name)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True,
                                ignore=lambda folder, names: [n for n in names if n in KEEP])
            else:
                shutil.copy2(s, d)
        # new files inside inputs/ (like its README) without touching your photos
        new_inputs = os.path.join(src, "printlab", "inputs")
        if os.path.isdir(new_inputs):
            for n in os.listdir(new_inputs):
                if not os.path.exists(os.path.join(HERE, "inputs", n)):
                    shutil.copy2(os.path.join(new_inputs, n), os.path.join(HERE, "inputs", n))
    print("Updating Python packages...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", os.path.join(HERE, "requirements.txt")])
    # restart the dashboard so it runs the new code
    if sys.platform != "win32":
        subprocess.run(["pkill", "-f", "printlab/dashboard.py"], stderr=subprocess.DEVNULL)
    print("Rebuilding designs (the jars take about a minute each)...")
    designs = sorted(f for f in os.listdir(os.path.join(HERE, "designs")) if f.endswith(".py"))
    failed = []
    for f in designs:
        print("  building", f[:-3])
        r = subprocess.run([sys.executable, os.path.join(HERE, "designs", f)], cwd=HERE,
                           capture_output=True, text=True)
        if r.returncode != 0:
            failed.append(f[:-3])
    subprocess.run([sys.executable, os.path.join(HERE, "install_app.py")], stdout=subprocess.DEVNULL)
    print("\nDone. Open Print Lab from your desktop.")
    if failed:
        print("These didn't build (see the dashboard for details):", ", ".join(failed))
    missing = [n for n in ("gta6_cutout.png", "mug_cutout.png", "mug_mask.png", "case_photo.jpg")
               if not os.path.exists(os.path.join(HERE, "inputs", n))]
    if missing:
        print("Designs with your pictures need these files in printlab/inputs/:", ", ".join(missing))
        print("Without them those designs build without the picture.")


if __name__ == "__main__":
    main()
