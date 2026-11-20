"""Twisted vase

A turned vase with a gentle twist. Print in vase mode (Bambu Studio: Others > Spiral vase)
for a fast, single-wall print, or normally with 2 walls to make it watertight.
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from printlab import *

HEIGHT = 140       # total height
BASE_D = 70        # diameter at the base
BELLY_D = 95       # widest diameter
NECK_D = 50        # diameter at the top
WALL = 2           # wall thickness (ignored in vase mode)
TWIST = 60         # degrees of twist from bottom to top
LOBES = 6          # number of soft ridges around the vase
LOBE_DEPTH = 4     # how deep the ridges are

def radius(z):
    t = z / HEIGHT
    return (BASE_D / 2) * (1 - t) ** 2 + (BELLY_D / 2) * 2 * t * (1 - t) * 1.25 + (NECK_D / 2) * t * t

n = 40
outer = [(0, 0)] + [(radius(HEIGHT * i / n), HEIGHT * i / n) for i in range(n + 1)]
inner = [(radius(HEIGHT * i / n) - WALL, HEIGHT * i / n) for i in range(n, 0, -1)]
profile = outer + inner + [(0, WALL)]
plain = revolve(profile)

def ridges(p):
    x, y, z = p
    a = math.atan2(y, x) + math.radians(TWIST) * z / HEIGHT
    k = 1 + (LOBE_DEPTH / max(radius(z), 1)) * math.cos(LOBES * a)
    return (x * k, y * k, z)

vase = plain.refine(2).warp(ridges)

if __name__ == "__main__":
    export({"twist_vase": vase}, "twist_vase",
           out_dir=os.path.join(os.path.dirname(__file__), "..", "out"))
