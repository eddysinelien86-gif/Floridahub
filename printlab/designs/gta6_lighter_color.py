"""GTA VI lighter case, color

A chunky BIC Maxi sleeve with two full-color GTA VI badges (front and back) printed flat
on an AMS like enamel pins, then glued into matching pockets. Badge colors: black, white,
pink, orange. Case: any color, PETG. No supports.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from printlab import *

# ---- lighter (BIC Maxi, 82 x 25 x 15 mm) ----
LIGHTER_W = 25.2    # lighter width
LIGHTER_D = 15.2    # lighter thickness
FIT = 0.35          # gap around the lighter

# ---- case ----
CASE_W = 36         # case width
CASE_D = 22         # case thickness
CASE_H = 66         # case height (leaves the lighter's metal top free)
CORNER_R = 3        # corner rounding
FLOOR = 1.6         # bottom thickness
PUSH_HOLE = 10      # hole in the bottom to push the lighter out

# ---- badges ----
BADGE_W = 29        # badge width (height follows the picture)
BADGE_BASE = 1.4    # badge base thickness (sits in the pocket)
BADGE_COLOR = 0.6   # colored top layer thickness
POCKET = 0.8        # pocket depth in the case
CLEAR = 0.15        # gap around the badge in its pocket
PIXEL = 0.15        # color detail size
MIN_SPECK = 0.5     # color spots smaller than this (mm2) are merged into neighbors
ART = "gta6_cutout.png"

# filament colors for the badges (name: approximate RGB). The first one is also the badge base.
PALETTE = {"black": (25, 22, 30), "white": (240, 238, 235), "pink": (225, 45, 150), "orange": (245, 140, 45)}

ROOT = os.path.join(os.path.dirname(__file__), "..")
A_in, B_in = LIGHTER_W / 2 + FIT, LIGHTER_D / 2 + FIT


def ellipse(a, b, n=240):
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return CrossSection([np.column_stack([a * np.cos(t), b * np.sin(t)])])


def centered_rbox(w, d, h, r):
    return rounded_box(w, d, h, r).translate([-w / 2, -d / 2, 0])


# ------------------------------------------------------------------ case
c = 0.8
case = hull(centered_rbox(CASE_W - 2 * c, CASE_D - 2 * c, 0.01, CORNER_R - c),
            centered_rbox(CASE_W, CASE_D, CASE_H - 2 * c, CORNER_R).translate([0, 0, c]),
            centered_rbox(CASE_W - 2 * c, CASE_D - 2 * c, 0.01, CORNER_R - c).translate([0, 0, CASE_H - 0.01]))
case -= Manifold.extrude(ellipse(A_in, B_in), CASE_H).translate([0, 0, FLOOR])
case -= cylinder(PUSH_HOLE, FLOOR * 3).translate([0, 0, -FLOOR])
case -= hull(Manifold.extrude(ellipse(A_in, B_in), 0.01).translate([0, 0, CASE_H - 1.0]),
             Manifold.extrude(ellipse(A_in + 0.8, B_in + 0.8), 0.01).translate([0, 0, CASE_H]))


# ------------------------------------------------------------------ badge colors
def to_lab(c):
    c = np.asarray(c, float) / 255
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.9505, 1, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def mask_to_cs(mask):
    """Binary pixel mask (row 0 = top) -> CrossSection in mm, x right, y up."""
    import contourpy
    m = np.pad(mask.astype(float), 1)
    lines = contourpy.contour_generator(z=m).lines(0.5)
    h = mask.shape[0]
    polys = [np.column_stack([(l[:, 0] - 1) * PIXEL, (h - (l[:, 1] - 1)) * PIXEL]) for l in lines if len(l) >= 4]
    return CrossSection(polys, FillRule.EvenOdd) if polys else CrossSection()


def badge_layers():
    from PIL import Image
    from scipy import ndimage as ndi
    src = os.path.join(ROOT, "inputs", ART)
    im = Image.open(src)
    nx = int(BADGE_W / PIXEL)
    ny = int(nx * im.height / im.width)
    alpha = np.asarray(im.getchannel("A").resize((nx, ny), Image.LANCZOS)) > 128
    alpha = ndi.binary_fill_holes(ndi.binary_opening(alpha, iterations=2))
    rgb = np.asarray(im.convert("RGB").resize((nx, ny), Image.LANCZOS))
    names = list(PALETTE)
    pal = to_lab(np.array([PALETTE[n] for n in names]))
    d = ((to_lab(rgb)[..., None, :] - pal[None, None]) ** 2).sum(-1)
    idx = d.argmin(-1)
    # majority filter, then merge specks too small to print into their neighbors
    votes = np.stack([ndi.uniform_filter((idx == k).astype(float), 3) for k in range(len(names))], -1)
    idx = votes.argmax(-1)
    min_px = MIN_SPECK / PIXEL ** 2
    for _ in range(3):
        bad = np.zeros_like(alpha)
        for k in range(len(names)):
            lab, n = ndi.label((idx == k) & alpha)
            if n:
                sizes = ndi.sum(np.ones_like(lab), lab, range(1, n + 1))
                bad |= np.isin(lab, 1 + np.flatnonzero(sizes < min_px))
        if not bad.any():
            break
        _, (iy, ix) = ndi.distance_transform_edt(bad, return_indices=True)
        idx = idx[iy, ix]
    idx[~alpha] = -1
    return alpha, idx, names


badge = {}
outline = None
if os.path.isfile(os.path.join(ROOT, "inputs", ART)):
    alpha, idx, names = badge_layers()
    outline = mask_to_cs(alpha)
    base_name = names[0]
    for k, nm in enumerate(names):
        top = Manifold.extrude(mask_to_cs(idx == k), BADGE_COLOR).translate([0, 0, BADGE_BASE])
        if nm == base_name:
            badge[nm] = Manifold.extrude(outline, BADGE_BASE) + top
        elif not top.is_empty():
            badge[nm] = top
    bb = outline.bounds()
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    z0 = (CASE_H - bh) / 2
    pocket_cs = outline.offset(CLEAR, JoinType.Round)
    front = Manifold.extrude(pocket_cs, POCKET + 1).rotate([90, 0, 0]) \
        .translate([-bw / 2 - bb[0], -CASE_D / 2 + POCKET, z0 - bb[1]])
    back = front.rotate([0, 0, 180])
    case = case - front - back


if __name__ == "__main__":
    out = os.path.join(ROOT, "out")
    parts = {"case": case}
    if badge:
        parts["badge_front"] = badge
        parts["badge_back"] = {k: v for k, v in badge.items()}
    export(parts, "gta6_lighter_color", out_dir=out)
    lighter = Manifold.extrude(ellipse(LIGHTER_W / 2, LIGHTER_D / 2), 82).translate([0, 0, FLOOR])
    print(f"lighter vs case collision: {(lighter ^ case).volume():.2f} mm3")
    if badge:
        print(f"badge: {bw:.1f} x {bh:.1f} mm, colors: " +
              ", ".join(f"{k} {v.volume() / 1000 * 1.24:.1f} g" for k, v in badge.items()))
        thin = (CASE_D / 2 - B_in) - POCKET
        print(f"case wall behind the pockets: {thin:.2f} mm")
