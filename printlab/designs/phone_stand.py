"""Phone stand

Angled for watching video. Prints on its side with no supports.

Set SLOT to your phone's thickness including the case, plus about 1 mm.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from printlab import *

# ---- parameters (mm) — change these ----
WIDTH = 70        # how wide the stand is (along the phone's bottom edge)
BASE_DEPTH = 85   # front-to-back footprint
BACK_HEIGHT = 75  # height of the back support
LIP_HEIGHT = 14   # front lip that holds the phone's bottom edge
SLOT = 12         # gap for the phone + case
THICK = 5         # wall thickness of the profile

# Side profile in the X/Y plane (X = front-to-back, Y = up), extruded by WIDTH,
# so every edge is vertical while printing: no overhangs, no supports.
lean = BACK_HEIGHT * 0.45            # back leans ~65 degrees from horizontal
x0 = THICK + SLOT                    # where the back support starts
top = (x0 + lean, BACK_HEIGHT)
base = [(0, 0), (BASE_DEPTH, 0), (BASE_DEPTH, THICK), (0, THICK)]
lip = [(0, 0), (THICK, 0), (THICK, LIP_HEIGHT), (0, LIP_HEIGHT)]
back = [(x0, 0), (x0 + THICK * 1.1, 0), (top[0] + THICK * 1.1, top[1]), top]
brace = [(BASE_DEPTH - THICK * 1.4, 0), (BASE_DEPTH, 0),
         (x0 + lean * 0.7 + THICK, BACK_HEIGHT * 0.7), (x0 + lean * 0.7, BACK_HEIGHT * 0.7)]
stand = union(*[polygon_extrude(p, WIDTH) for p in (base, lip, back, brace)])

if __name__ == "__main__":
    export({"phone_stand": stand}, "phone_stand",
           out_dir=os.path.join(os.path.dirname(__file__), "..", "out"))
