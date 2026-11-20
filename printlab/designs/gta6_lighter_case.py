"""GTA VI lighter case

A sleeve for a BIC Maxi (about 82 x 25 x 15 mm) with the art bulging out all around.
Print upright in PETG, no supports. Slide the lighter in from the top; push it out
through the hole in the bottom. The metal top and flame stay uncovered.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from printlab import *

# ---- lighter (BIC Maxi) ----
LIGHTER_W = 25.2    # lighter width
LIGHTER_D = 15.2    # lighter thickness
FIT = 0.35          # gap around the lighter
SLEEVE_H = 64       # sleeve height (BIC Maxi is 82 tall; this leaves the metal top free)

# ---- case ----
WALL = 1.6          # sleeve wall
FLOOR = 1.6         # bottom thickness
PUSH_HOLE = 10      # hole in the bottom to push the lighter out

# ---- art ----
ART_H = 56          # picture height
RAISE = 0.8         # how far the whole picture bulges out
DETAIL = 1.0        # extra bulge for light parts
TEXTURE = 0.35      # swirl lines around the back
ART = "gta6_cutout.png"

ROOT = os.path.join(os.path.dirname(__file__), "..")
A_in, B_in = LIGHTER_W / 2 + FIT, LIGHTER_D / 2 + FIT
A, B = A_in + WALL, B_in + WALL


def ellipse(a, b, n=240):
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return CrossSection([np.column_stack([a * np.cos(t), b * np.sin(t)])])


sleeve = Manifold.extrude(ellipse(A, B), SLEEVE_H) - \
    Manifold.extrude(ellipse(A_in, B_in), SLEEVE_H).translate([0, 0, FLOOR])
sleeve -= cylinder(PUSH_HOLE, FLOOR * 3).translate([0, 0, -FLOOR])
# lead-in bevel at the top so the lighter slides in easily
sleeve -= hull(Manifold.extrude(ellipse(A_in, B_in), 0.01).translate([0, 0, SLEEVE_H - 1.0]),
               Manifold.extrude(ellipse(A_in + 0.8, B_in + 0.8), 0.01).translate([0, 0, SLEEVE_H]))

# ---- art wrapped all the way around the oval ----
# arc-length table along the outside: start at the back (seam), go left side -> front -> right side
t = np.linspace(math.pi / 2, math.pi / 2 + 2 * math.pi, 2001)
px, py = A * np.cos(t), B * np.sin(t)
nx, ny = B * np.cos(t), A * np.sin(t)
nl = np.hypot(nx, ny); nx, ny = nx / nl, ny / nl
s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(px), np.diff(py)))])
perim = s[-1]


def swirl(xs, ys):
    f = np.sin(0.55 * xs + 2.2 * np.sin(0.09 * ys + 0.05 * xs) + 1.5 * np.sin(0.04 * xs - 0.07 * ys))
    return (f > 0.72).astype(float)


src = os.path.join(ROOT, "inputs", ART)
if os.path.isfile(src):
    from PIL import Image, ImageFilter
    from scipy import ndimage as ndi
    step = 0.25
    band_h = SLEEVE_H - 6
    width = perim - 0.6                                 # hairline gap at the back seam
    gx, gy = int(width / step), int(band_h / step)
    xs, ys = np.meshgrid(np.arange(gx) * step, np.arange(gy)[::-1] * step)
    embed = 0.6
    hz = embed + TEXTURE * swirl(xs * 1.3, ys * 1.3)
    im = Image.open(src)
    aw = ART_H * im.width / im.height
    ax, ay = int(aw / step), int(ART_H / step)
    alpha = np.asarray(im.getchannel("A").resize((ax, ay), Image.LANCZOS), float) / 255 > 0.5
    g = np.asarray(im.convert("L").resize((ax, ay), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.8)), float) / 255
    g = (g - g[alpha].min()) / max(1e-6, np.ptp(g[alpha]))
    x0 = int((perim / 2 - aw / 2) / step)               # front center sits half way round
    y0 = (gy - ay) // 2
    reg = hz[y0:y0 + ay, x0:x0 + ax]
    halo = ndi.binary_dilation(alpha, iterations=int(1.0 / step)) & ~alpha
    reg[halo] = embed
    reg[alpha] = embed + RAISE + DETAIL * g[alpha]
    plate = heightmap(hz, width)
    z0 = 3.0

    def wrap(p):
        x, y, h = p
        u = x + 0.3
        X, Y = np.interp(u, s, px), np.interp(u, s, py)
        NX, NY = np.interp(u, s, nx), np.interp(u, s, ny)
        k = h - embed
        return (X + NX * k, Y + NY * k, z0 + y)

    sleeve = sleeve + plate.warp(wrap)


def make_label(out_dir):
    """Full-color wrap label as an alternative to painting the relief."""
    if not os.path.isfile(src):
        return
    from PIL import Image, ImageDraw
    dpi = 300
    mm = lambda v: round(v / 25.4 * dpi)
    W, H = mm(perim), mm(SLEEVE_H - 6)
    yy, xx = np.mgrid[0:H, 0:W]
    lines = swirl(xx / dpi * 25.4 * 1.3, (H - yy) / dpi * 25.4 * 1.3)
    base = np.dstack([18 + 30 * yy / H, 10 + 4 * yy / H, 40 + 40 * yy / H])
    img = (base * (1 - lines[..., None] * 0.6) + np.array([150, 60, 200]) * lines[..., None] * 0.6).clip(0, 255).astype(np.uint8)
    label = Image.fromarray(img)
    art = Image.open(src)
    ah = mm(ART_H)
    art = art.resize((round(art.width * ah / art.height), ah), Image.LANCZOS)
    label.paste(art, ((W - art.width) // 2, (H - ah) // 2), art)
    ImageDraw.Draw(label).rectangle((0, 0, W - 1, H - 1), outline=(160, 160, 160), width=2)
    label.save(os.path.join(out_dir, "gta6_lighter_case_label.png"), dpi=(dpi, dpi))
    print(f"label: {perim:.1f} x {SLEEVE_H - 6} mm, print at 100%")


if __name__ == "__main__":
    out = os.path.join(ROOT, "out")
    export({"gta6_lighter_case": sleeve}, "gta6_lighter_case", out_dir=out)
    make_label(out)
    print(f"inside: {2 * A_in:.1f} x {2 * B_in:.1f} mm, outside with art: about {2 * A + 2 * (RAISE + DETAIL):.0f} x {2 * B + 2 * (RAISE + DETAIL):.0f} mm")
