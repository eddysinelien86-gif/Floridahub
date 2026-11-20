"""iPhone 17 Pro Max case

Print in TPU (95A), back down on the bed, no supports, 3 walls, 15% infill. The camera
plateau, button and port cutouts are deliberately roomy; check the fit and adjust the
CUT numbers if needed. Also writes a photo sticker sized to the back (out/*_sticker.png).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from printlab import *

# ---- phone (Apple spec: 163.4 x 78.0 x 8.75 mm) ----
PHONE_H = 163.4     # phone height
PHONE_W = 78.0      # phone width
PHONE_D = 8.75      # phone thickness (body, without camera plateau)
PHONE_R = 12        # phone corner radius, seen from the front
FIT = 0.15          # gap around the phone (TPU stretches, so keep it small)

# ---- case ----
WALL = 1.6          # side wall thickness
BACK = 1.6          # back thickness
LIP = 1.2           # how far the lip wraps over the screen edge
LIP_T = 1.0         # lip thickness
CHAMFER = 0.8       # softened outer edges

# ---- cutouts (measured from the TOP edge of the phone) ----
CAMERA_CUT = 46     # open back for the camera plateau, from the top edge down
LEFT_CUT_FROM = 20  # left side: action button + volume, slot starts
LEFT_CUT_TO = 82    # left side slot ends
POWER_CUT_FROM = 34 # right side: power button, slot starts
POWER_CUT_TO = 66   # right side power slot ends
CAM_CTRL_FROM = 96  # right side: Camera Control, slot starts
CAM_CTRL_TO = 124   # right side Camera Control slot ends
PORT_CUT = 52       # bottom opening for USB-C, speaker and mics (width)

# ---- photo sticker for the back ----
PHOTO = "case_photo.jpg"   # file in printlab/inputs/
PHOTO_CENTER = 58          # where to center the crop, % across the photo
STICKER_MARGIN = 4         # gap from the case edge to the sticker

in_w, in_h = PHONE_W + 2 * FIT, PHONE_H + 2 * FIT     # cavity
cav_d = PHONE_D + 2 * FIT
out_w, out_h = in_w + 2 * WALL, in_h + 2 * WALL
total_h = BACK + cav_d + LIP_T
out_r = PHONE_R + FIT + WALL


def centered(part_w, part_h, z, r):
    return rounded_box(part_w, part_h, z, r).translate([-part_w / 2, -part_h / 2, 0])


# Outer shell with softened top and bottom edges (45 degree chamfers print cleanly).
c = CHAMFER
shell = hull(
    centered(out_w - 2 * c, out_h - 2 * c, 0.01, out_r - c),
    centered(out_w, out_h, total_h - 2 * c, out_r).translate([0, 0, c]),
    centered(out_w - 2 * c, out_h - 2 * c, 0.01, out_r - c).translate([0, 0, total_h - 0.01]),
)
cavity = centered(in_w, in_h, cav_d, PHONE_R + FIT).translate([0, 0, BACK])
opening = centered(in_w - 2 * LIP, in_h - 2 * LIP, total_h, PHONE_R + FIT - LIP).translate([0, 0, BACK])
case = shell - cavity - opening

top_y = in_h / 2                       # inside top edge
mid_z = BACK + cav_d / 2               # middle of the phone's side
side_h = PHONE_D - 2.0                 # button slot height

# Camera plateau: open the whole back across the width, from the top down.
case -= rounded_box(in_w - 2, CAMERA_CUT + 10, BACK + 2, 6).translate(
    [-(in_w - 2) / 2, top_y - CAMERA_CUT, -1])


def side_slot(x_sign, y_from, y_to):
    length = y_to - y_from
    slot = box(WALL * 4, length, side_h)
    x = (in_w / 2 - WALL) if x_sign > 0 else (-in_w / 2 - 3 * WALL)
    return slot.translate([x, top_y - y_to, mid_z - side_h / 2])


case -= side_slot(-1, LEFT_CUT_FROM, LEFT_CUT_TO)
case -= side_slot(+1, POWER_CUT_FROM, POWER_CUT_TO)
case -= side_slot(+1, CAM_CTRL_FROM, CAM_CTRL_TO)
# Bottom: USB-C, speaker and mics, open to the screen side so the cable plugs in easily.
case -= box(PORT_CUT, WALL * 4, cav_d + LIP_T).translate([-PORT_CUT / 2, -in_h / 2 - 3 * WALL, BACK + 1.0])


def make_sticker(out_dir):
    """Crop the photo to the flat area of the back and save a 300 dpi PNG with a cut line."""
    from PIL import Image, ImageDraw, ImageOps
    src = os.path.join(os.path.dirname(__file__), "..", "inputs", PHOTO)
    if not os.path.isfile(src):
        print(f"(no sticker: put your photo at printlab/inputs/{PHOTO})")
        return
    w_mm = out_w - 2 * STICKER_MARGIN
    h_mm = (top_y - CAMERA_CUT - STICKER_MARGIN) + (out_h / 2 - STICKER_MARGIN)
    dpi = 300
    px_w, px_h = round(w_mm / 25.4 * dpi), round(h_mm / 25.4 * dpi)
    img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    # crop to the sticker's shape, centered where the subject is
    target = w_mm / h_mm
    iw, ih = img.size
    if iw / ih > target:
        cw = round(ih * target)
        cx = round(iw * PHOTO_CENTER / 100 - cw / 2)
        img = img.crop((max(0, min(iw - cw, cx)), 0, max(0, min(iw - cw, cx)) + cw, ih))
    else:
        ch = round(iw / target)
        img = img.crop((0, (ih - ch) // 2, iw, (ih - ch) // 2 + ch))
    img = img.resize((px_w, px_h), Image.LANCZOS)
    r_px = round((out_r - STICKER_MARGIN) / 25.4 * dpi)
    mask = Image.new("L", (px_w, px_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, px_w - 1, px_h - 1), r_px, fill=255)
    pad = round(5 / 25.4 * dpi)     # 5 mm white border around the cut line
    sheet = Image.new("RGB", (px_w + 2 * pad, px_h + 2 * pad), "white")
    sheet.paste(img, (pad, pad), mask)
    ImageDraw.Draw(sheet).rounded_rectangle((pad, pad, pad + px_w - 1, pad + px_h - 1), r_px,
                                            outline=(150, 150, 150), width=2)
    path = os.path.join(out_dir, "iphone17_pro_max_case_sticker.png")
    sheet.save(path, dpi=(dpi, dpi))
    print(f"sticker: {path}  ({w_mm:.1f} x {h_mm:.1f} mm inside the grey cut line; "
          "print at 100% / actual size)")


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "out")
    export({"iphone17_pro_max_case": case}, "iphone17_pro_max_case", out_dir=out)
    make_sticker(out)
