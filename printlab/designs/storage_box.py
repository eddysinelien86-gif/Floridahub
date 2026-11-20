"""Storage box with a slip-on lid

Print both parts open side up, no supports. The lid slides over the box with 0.2 mm clearance.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from printlab import *

# ---- parameters (mm) — change these ----
INNER_X = 80       # inside length
INNER_Y = 50      # inside width
INNER_Z = 35      # inside depth
WALL = 1.6        # side wall thickness (1.6 = 4 perimeters)
FLOOR = 1.6       # floor thickness
CORNER_R = 4      # outside corner radius
LID_H = 8         # how far the lid skirt overlaps the box
LID_TOP = 1.6     # lid top thickness

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
