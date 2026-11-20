"""Name keychain

Raised letters on a rounded tag. For two colours, add a filament change at the
layer where the letters start (Bambu Studio: right-click the layer slider).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from printlab import *

NAME = "FLORIDA"   # text on the tag
LETTER_SIZE = 9    # letter height
LETTER_RAISE = 1.2 # how far the letters stick up
TAG_THICK = 2.4    # thickness of the tag
MARGIN = 3         # border around the text
RING_HOLE = 5      # hole for the key ring

letters = text(NAME, LETTER_SIZE, LETTER_RAISE)
lo, hi = letters.bounding_box()[:3], letters.bounding_box()[3:]
ring_od = RING_HOLE + 2 * 2.4
tag_w = (hi[0] - lo[0]) + 2 * MARGIN + ring_od
tag_h = (hi[1] - lo[1]) + 2 * MARGIN
tag = rounded_box(tag_w, tag_h, TAG_THICK, min(tag_h / 2, 6)) - \
    hole(RING_HOLE, TAG_THICK).translate([ring_od / 2 + 0.5, tag_h / 2, 0])
keychain = tag + letters.translate([ring_od + MARGIN - lo[0], MARGIN - lo[1], TAG_THICK])

if __name__ == "__main__":
    export({"name_keychain": keychain}, "name_keychain",
           out_dir=os.path.join(os.path.dirname(__file__), "..", "out"))
