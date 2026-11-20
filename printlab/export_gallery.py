"""Package every built design into out/gallery/ for the Print Lab page in the Claude app.

    python3 printlab/export_gallery.py

Writes designs.json, preview images, and files/<design>.json holding the design's
3MF, STLs and report as base64 (the Claude app can't host .stl or .3mf directly, so
the page decodes them for the 3D view and zips them in the browser for download).
"""
import base64
import json
import os
import shutil

import dashboard

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
GAL = os.path.join(OUT, "gallery")


def main() -> None:
    shutil.rmtree(GAL, ignore_errors=True)
    for d in ("img", "files"):
        os.makedirs(os.path.join(GAL, d))
    items = []
    for d in dashboard.list_designs():
        rep = d["report"]
        if not rep or d["stale"]:
            print(f"skip {d['name']}: build it first")
            continue
        name = d["name"]
        shutil.copy(os.path.join(OUT, f"{name}.png"), os.path.join(GAL, "img", f"{name}.png"))
        stls = [p["stl"] for p in rep["parts"]]
        with_stl = sum(os.path.getsize(os.path.join(OUT, n)) for n in stls) < 6_000_000
        names = [f"{name}.3mf"] + (stls if with_stl else []) + [f"{name}_report.txt"]
        payload = {n: base64.b64encode(open(os.path.join(OUT, n), "rb").read()).decode() for n in names}
        with open(os.path.join(GAL, "files", f"{name}.json"), "w") as f:
            json.dump(payload, f)
        items.append({k: d[k] for k in ("name", "title", "notes", "params")} | {"report": rep, "stl_included": with_stl})
    with open(os.path.join(GAL, "designs.json"), "w") as f:
        json.dump({"designs": items}, f, indent=1)
    print(f"packaged {len(items)} designs into {GAL}")


if __name__ == "__main__":
    main()
