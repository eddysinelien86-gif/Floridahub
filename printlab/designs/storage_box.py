"""Parametric storage box with a slip-on lid.

Run:  python designs/storage_box.py
Then open out/storage_box.3mf in Bambu Studio. Print both parts open-side up, no supports.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from printlab import *

# ---- parameters (mm) — change these ----
INNER_X, INNER_Y, INNER_Z = 80, 50, 35
WALL = GOOD_WALL          # 1.6 mm = 4 perimeters
FLOOR = 1.6
CORNER_R = 4
LID_H = 8                 # how far the lid skirt overlaps the box
LID_TOP = 1.6

outer_x, outer_y = INNER_X + 2 * WALL, INNER_Y + 2 * WALL
body = rounded_box(outer_x, outer_y, INNER_Z + FLOOR, CORNER_R) - \
    rounded_box(INNER_X, INNER_Y, INNER_Z + 1, CORNER_R - WALL).translate([WALL, WALL, FLOOR])

# Lid fits *over* the box: its inner size = box outer + clearance on each side.
lid_in_x, lid_in_y = outer_x + 2 * FIT_CLEARANCE, outer_y + 2 * FIT_CLEARANCE
lid = rounded_box(lid_in_x + 2 * WALL, lid_in_y + 2 * WALL, LID_H + LID_TOP, CORNER_R + WALL) - \
    rounded_box(lid_in_x, lid_in_y, LID_H + 1, CORNER_R + FIT_CLEARANCE).translate([WALL, WALL, LID_TOP])

if __name__ == "__main__":
    export({"box": body, "lid": lid}, "storage_box",
           out_dir=os.path.join(os.path.dirname(__file__), "..", "out"))
