"""Printable ruler

150 mm ruler with millimetre marks and centimetre numbers, plus a 90 degree corner for
measuring hole positions from an edge. Two colors on an AMS: body in black, marks in white
(marks are the top 2 layers). Print flat at 0.2 mm layers, no supports.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from printlab import *

LENGTH = 150        # measuring length (mm)
WIDTH = 22          # ruler width
THICK = 2.0         # body thickness
MARK_T = 0.4        # mark thickness (2 layers at 0.2 mm)
MARK_W = 0.4        # mark line width (one nozzle width)
CORNER = 40         # length of the square leg for measuring from a corner
MARGIN = 3          # plain space before 0 and after the last mark

body = box(LENGTH + 2 * MARGIN, WIDTH, THICK) + box(WIDTH, CORNER + WIDTH, THICK).translate([0, -CORNER, 0])

marks = []
for mm in range(0, LENGTH + 1):
    tall = 7 if mm % 10 == 0 else 5 if mm % 5 == 0 else 3
    x = MARGIN + mm - MARK_W / 2
    marks.append(box(MARK_W, tall, MARK_T).translate([x, WIDTH - tall, THICK - MARK_T]))
    if mm % 10 == 0 and mm > 0:
        n = text(str(mm // 10), 4.2, MARK_T + 0.01, halign="center")
        marks.append(n.translate([MARGIN + mm, WIDTH - 13, THICK - MARK_T]))
# the corner leg: marks down the left edge every mm, numbered every cm
for mm in range(0, CORNER - 4):
    tall = 7 if mm % 10 == 0 else 5 if mm % 5 == 0 else 3
    y = -mm - MARK_W / 2
    marks.append(box(tall, MARK_W, MARK_T).translate([0, y, THICK - MARK_T]))
    if mm % 10 == 0 and mm > 0:
        marks.append(text(str(mm // 10), 4.2, MARK_T + 0.01).translate([9, -mm - 2.1, THICK - MARK_T]))
marks.append(text("mm", 3.5, MARK_T + 0.01).translate([MARGIN + 2, 2.5, THICK - MARK_T]))
white = union(*marks)
black = body - white

if __name__ == "__main__":
    export({"ruler": {"black": black, "white": white}}, "printable_ruler",
           out_dir=os.path.join(os.path.dirname(__file__), "..", "out"))
