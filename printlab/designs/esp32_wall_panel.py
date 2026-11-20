"""Touchscreen wall panel

Wall panel for the 2.8" ESP32-S3 touch board (about 50 x 86 mm) with the 4000 mAh battery
behind it. Mounts on two screws 83.3 mm apart (a standard US switch box, or wall anchors).
Print the front face-down and the back flat, PLA or PETG, no supports. Print the fit test
first: set the board on it and check the screen window and the four pins line up.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from printlab import *

# ---- board (measured from photos; check with the fit test) ----
BOARD_W = 50        # board width
BOARD_H = 86        # board height
HOLE_IN = 3.5       # screw holes: distance from each board edge to the hole center
SCREEN_W = 43.2     # visible screen width (2.8" panel)
SCREEN_H = 57.6     # visible screen height
SCREEN_Y = 0.6      # screen center above the board center
DISPLAY_T = 4.5     # screen module thickness (glass front to board front)
BACK_PARTS = 6      # tallest parts on the back of the board (connectors)
USE_BATTERY = 1     # 1 = room for the 4000 mAh battery behind the board, 0 = USB powered (thinner)

# ---- panel ----
PLATE_W = 72        # front plate width
PLATE_H = 112       # front plate height
PLATE_T = 3         # front plate thickness
CORNER_R = 6        # plate corner radius
WALL = 2            # body wall thickness
BOX_SCREWS = 83.3   # distance between the two mounting screws (US switch box)
SD_FROM_TOP = 32    # microSD slot: distance from the board's top edge (left side, seen from the front)
USB_X = -3.2        # USB-C position across the bottom, from center (seen from the front)

bat = (41, 70, 8.5) if USE_BATTERY else (0, 0, 0)
FIT = 1.0                                        # gap around the board
in_w, in_h = BOARD_W + 2 * FIT, BOARD_H + 2 * FIT
out_w, out_h = in_w + 2 * WALL, in_h + 2 * WALL
z_glass = -PLATE_T                               # glass front
z_board_f = z_glass - DISPLAY_T                  # board front
z_board_b = z_board_f - 1.6                      # board back
z_body_end = z_board_b - BACK_PARTS - (bat[2] + 1.0 if USE_BATTERY else 0) - 0.5
BACK_T = 2.4
holes = [(sx * (BOARD_W / 2 - HOLE_IN), sy * (BOARD_H / 2 - HOLE_IN)) for sx in (-1, 1) for sy in (-1, 1)]


def cbox(w, h, d, r=0.0):
    """Box centered in x/y, from z=-d to 0 (r rounds the vertical edges)."""
    b = rounded_box(w, h, d, r) if r else box(w, h, d)
    return b.translate([-w / 2, -h / 2, -d])


# ------------------------------------------------------------------ front shell (use position: front face at z=0)
plate = hull(cbox(PLATE_W - 2, PLATE_H - 2, 0.01, CORNER_R - 1),
             cbox(PLATE_W, PLATE_H, PLATE_T - 1, CORNER_R).translate([0, 0, -1]),
             cbox(PLATE_W, PLATE_H, 0.01, CORNER_R).translate([0, 0, -PLATE_T + 0.01]))
body = cbox(out_w, out_h, -z_body_end, 3) - cbox(in_w, in_h, -z_body_end + 1, 2).translate([0, 0, -PLATE_T])
front = plate + body.translate([0, 0, 0])
# screen window, bevelled 45 degrees toward the viewer
win = hull(cbox(SCREEN_W + 0.6, SCREEN_H + 0.6, PLATE_T + 1).translate([0, 0, -0.01 + 0]),
           cbox(SCREEN_W + 0.6 + 4, SCREEN_H + 0.6 + 4, 0.01).translate([0, 0, 1.0])).translate([0, SCREEN_Y, 0])
front -= win
# standoffs for the board (M2.5 self-tapping screws from behind)
for x, y in holes:
    s = cylinder(6, DISPLAY_T).translate([x, y, z_board_f]) - cylinder(2.2, DISPLAY_T + 1).translate([x, y, z_board_f - 0.5])
    front += s
# microphone holes (top strip, right side seen from the front)
for dx in (-1.6, 0, 1.6):
    front -= cylinder(1.0, PLATE_T + 2).translate([6.8 + dx, BOARD_H / 2 - 4, -PLATE_T - 1])
# side and bottom openings: microSD (left), USB-C (bottom), vents (top and bottom, behind the board)
sd_y = BOARD_H / 2 - SD_FROM_TOP
front -= box(WALL * 4, 15, 4).translate([-out_w / 2 - WALL, sd_y - 7.5, z_board_b - 3])
front -= rounded_box(13, WALL * 4, 7.5, 3).translate([USB_X - 6.5, -out_h / 2 - WALL, z_board_b - 5])
for i in (-1, 0, 1):
    for yy in (out_h / 2, -out_h / 2):
        if yy < 0 and abs(i * 11 - USB_X) < 10:
            continue
        front -= box(8, WALL * 4, 1.8).translate([i * 11 + 12 * (yy < 0) - 4, yy - WALL * 2, z_body_end + 3])
# bosses for the two back-plate screws (behind the board, top and bottom center)
boss_pts = [(-15, in_h / 2 - 3), (15, -in_h / 2 + 3)]
boss_len = (z_board_b - BACK_PARTS - 0.3) - z_body_end      # stays behind the board's back parts, beside the battery
for x, y in boss_pts:
    b = cylinder(6, boss_len).translate([x, y, z_body_end]) + box(6, 4, boss_len).translate([x - 3, y if y > 0 else y - 4, z_body_end])
    front += b - cylinder(2.2, boss_len + 1).translate([x, y, z_body_end - 0.5])

# ------------------------------------------------------------------ back plate (use position)
lip = cbox(in_w - 0.4, in_h - 0.4, 2, 1.8) - cbox(in_w - 3.2, in_h - 3.2, 3, 1).translate([0, 0, 0.5])
back = cbox(out_w, out_h, BACK_T, 3).translate([0, 0, z_body_end]) + lip.translate([0, 0, z_body_end + 2])
for x, y in boss_pts:   # screw holes into the bosses, countersunk on the outside
    back -= cylinder(2.8, BACK_T + 3).translate([x, y, z_body_end - BACK_T - 1])
    back -= cylinder(5.6, 1.4, 2.8).translate([x, y, z_body_end - BACK_T - 0.01])
    back -= cylinder(7, 3).translate([x, y, z_body_end])            # clear the boss through the lip ring
for y in (BOX_SCREWS / 2, -BOX_SCREWS / 2):   # mounting screws, countersunk on the inside
    back -= cylinder(4.0, BACK_T + 4).translate([0, y, z_body_end - BACK_T - 1])
    back -= cylinder(4.0, 2.0, 8.0).translate([0, y, z_body_end - 2.0 + 0.01])
if USE_BATTERY:   # low cradle that keeps the battery centered
    cradle = cbox(bat[0] + 2.4 + 0.6, bat[1] + 2.4 + 0.6, 3) - cbox(bat[0] + 0.6, bat[1] + 0.6, 4).translate([0, 0, 0.5])
    cradle -= cbox(12, bat[1] + 10, 4).translate([0, 0, 0.5])            # gaps for the wire and fingers
    back += cradle.translate([0, 0, z_body_end + 3])
for x in (7.5, -17.5):   # pinholes to reach RESET and BOOT on the back of the board
    back -= cylinder(2.0, BACK_T + 3).translate([x, -BOARD_H / 2 + 4, z_body_end - BACK_T - 1])

# ------------------------------------------------------------------ fit test: thin plate with the window and four pins
fit = cbox(BOARD_W + 8, BOARD_H + 8, 1.6, 4) - cbox(SCREEN_W + 0.6, SCREEN_H + 0.6, 3).translate([0, SCREEN_Y, 0.5])
for x, y in holes:
    fit += cylinder(2.6, 4).translate([x, y, 0])                    # pins should drop into the board's holes
fit += cbox(BOARD_W, 0.8, 0.6).translate([0, BOARD_H / 2, 0.6]) + cbox(BOARD_W, 0.8, 0.6).translate([0, -BOARD_H / 2, 0.6])

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "out")
    export({"panel_front": front.rotate([0, 180, 0]), "panel_back": back, "fit_test": fit},
           "esp32_wall_panel", out_dir=out)
    # collision check against stand-ins for the real parts
    glass = cbox(50.4, 69.6, DISPLAY_T).translate([0, SCREEN_Y, z_glass])
    board = cbox(BOARD_W, BOARD_H, 1.6).translate([0, 0, z_board_f])
    parts = cbox(BOARD_W - 2, BOARD_H - 2, BACK_PARTS).translate([0, 0, z_board_b])
    hits = {n: round((p ^ front).volume() + (p ^ back).volume(), 2) for n, p in
            (("screen", glass), ("board", board), ("board back parts", parts))}
    if USE_BATTERY:
        battery = cbox(*bat).translate([0, 0, z_board_b - BACK_PARTS - 0.5])
        hits["battery"] = round((battery ^ front).volume() + (battery ^ back).volume(), 2)
    print("collisions (mm3):", hits)
    print(f"panel: {PLATE_W} x {PLATE_H} mm, sticks out {-(z_body_end - BACK_T):.1f} mm from the wall")
