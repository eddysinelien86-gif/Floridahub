"""Haiti flag mug

Upright, no supports, 3 walls. The picture is a raised relief wrapped around the side;
lighter parts of the photo stand out more. PLA isn't safe for hot drinks or the
dishwasher: use it as a pen or brush cup, or see the notes for a drinking mug.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from printlab import *

# ---- mug ----
MUG_D = 84          # outside diameter
MUG_H = 95          # height
WALL = 3            # wall thickness
BASE = 4            # floor thickness
FOOT_CHAMFER = 1.5  # bevel at the bottom edge
HANDLE_T = 12       # handle thickness
HANDLE_REACH = 30   # how far the handle sticks out

# ---- picture relief ----
PICTURE_H = 80      # picture height on the mug
RAISE = 0.9         # how far the whole figure stands out
DETAIL = 0.9        # extra height for light parts (face, flag, highlights)
PICTURE_AT = 270    # degrees around the mug, handle at 0 (270 = facing you, handle on the right)

R = MUG_D / 2
ROOT = os.path.join(os.path.dirname(__file__), "..")

# Body: revolved profile with a beveled foot and a rounded-over rim.
c = FOOT_CHAMFER
profile = [(0, 0), (R - c, 0), (R, c), (R, MUG_H - 1), (R - 1, MUG_H), (R - WALL + 1, MUG_H),
           (R - WALL, MUG_H - 1), (R - WALL, BASE + 3), (R - WALL - 3, BASE), (0, BASE)]
body = revolve(profile)

# Handle: a D shape in the X/Z plane. 45 degree underside and a pointed-arch finger hole,
# so it prints upright with no supports.
x0 = R - 2.5
outer = [(x0, 6), (R + HANDLE_REACH, 6 + HANDLE_REACH + 2.5), (R + HANDLE_REACH, MUG_H - 16),
         (R + HANDLE_REACH - 6, MUG_H - 8), (x0, MUG_H - 8)]
hw = HANDLE_REACH - 9
hole = [(R + 0.5, 20), (R + 0.5 + hw, 20 + hw), (R + 0.5 + hw, MUG_H - 32),
        (R + 0.5 + hw / 2, MUG_H - 32 + hw / 2), (R + 0.5, MUG_H - 32)]
handle_2d = CrossSection([np.array(outer)]) - CrossSection([np.array(hole)])
handle = Manifold.extrude(handle_2d, HANDLE_T).rotate([90, 0, 0]).translate([0, HANDLE_T / 2, 0])
handle -= cylinder(MUG_D - 2 * WALL + 0.01, MUG_H + 2).translate([0, 0, BASE])   # keep the inside clear

mug = body + handle


def picture_relief():
    """Raised figure from printlab/inputs/mug_mask.png + mug_cutout.png, wrapped on the mug."""
    from PIL import Image, ImageFilter
    mask_p = os.path.join(ROOT, "inputs", "mug_mask.png")
    col_p = os.path.join(ROOT, "inputs", "mug_cutout.png")
    if not (os.path.isfile(mask_p) and os.path.isfile(col_p)):
        print("(no picture: put mug_mask.png and mug_cutout.png in printlab/inputs/)")
        return None
    m = Image.open(mask_p).convert("L")
    pic_w = PICTURE_H * m.width / m.height
    step = 0.25                                          # mm per heightmap cell
    nx, ny = int(pic_w / step), int(PICTURE_H / step)
    mask = np.asarray(m.resize((nx, ny), Image.LANCZOS), float) / 255 > 0.5
    gray = Image.open(col_p).convert("L").resize((nx, ny), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1))
    g = np.asarray(gray, float) / 255
    g = (g - g[mask].min()) / max(1e-6, np.ptp(g[mask]))  # stretch contrast inside the figure
    embed = 0.6                                          # sink the plate into the wall
    z = np.where(mask, embed + RAISE + DETAIL * g, 0.3)
    plate = heightmap(z, pic_w)                          # x across, y up, z out of the surface
    theta0 = np.radians(PICTURE_AT)
    z_base = (MUG_H - PICTURE_H) / 2

    def wrap(p):
        x, y, h = p
        t = theta0 + (x - pic_w / 2) / R
        rr = R - embed + h
        return (rr * np.cos(t), rr * np.sin(t), z_base + y)

    return plate.warp(wrap)


relief = picture_relief()
if relief is not None:
    mug = mug + relief


def make_decal(out_dir):
    """Full-color cutout at true size (300 dpi) for a waterslide decal or sticker."""
    from PIL import Image
    src = os.path.join(ROOT, "inputs", "mug_cutout.png")
    if not os.path.isfile(src):
        return
    im = Image.open(src)
    dpi = 300
    h_px = round(PICTURE_H / 25.4 * dpi)
    im = im.resize((round(im.width * h_px / im.height), h_px), Image.LANCZOS)
    path = os.path.join(out_dir, "haiti_flag_mug_decal.png")
    im.save(path, dpi=(dpi, dpi))
    print(f"decal: {path}  ({PICTURE_H * im.width / im.height:.0f} x {PICTURE_H} mm, print at 100%)")


if __name__ == "__main__":
    out = os.path.join(ROOT, "out")
    export({"haiti_flag_mug": mug}, "haiti_flag_mug", out_dir=out)
    make_decal(out)
