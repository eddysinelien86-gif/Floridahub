"""GTA VI push-and-turn jar

Child-resistant style: the ribbed lid only unscrews while you push it down; it clicks
and spins freely otherwise. Print the jar and inner cap in PETG or PLA, the outer cap
in PETG (its springs and pawls need to flex). All parts print as laid out, no supports.
Glue the medallion into the lid. A printed lid is not certified child-resistant.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from printlab import *

# ---- jar ----
BODY_D = 62         # jar outside diameter
BODY_H = 36         # height up to the shoulder
WALL = 2.4          # jar wall
BASE = 2.4          # jar floor
NECK_D = 52         # neck outside diameter (thread root)
NECK_H = 15         # neck height

# ---- threads and lid ----
PITCH = 4           # thread pitch
THREAD_DEPTH = 1.2  # thread depth
FIT = 0.35          # thread clearance
LID_WALL = 2.4      # outer cap wall
TOP_T = 2.4         # outer cap top thickness
PUSH = 1.8          # how far you push the lid down to open
RATCHET = 0.6       # depth of the click teeth
CLICKS = 24         # click teeth around the cap
RIB_PITCH = 2.4     # spacing of the grip rings on the lid

# ---- art ----
ART_H = 28          # picture height on the jar
ART_RAISE = 0.6     # picture stands out by this much
ART_DETAIL = 0.8    # extra height for light parts of the picture
TEXTURE = 0.35      # height of the swirl lines around the jar
TEXT_SIZE = 3.6     # letter height of PUSH DOWN & TURN on the lid
ART = "gta6_cutout.png"   # in printlab/inputs/

ROOT = os.path.join(os.path.dirname(__file__), "..")
SEG = 180
R = BODY_D / 2
rn = NECK_D / 2
top_z = BODY_H + NECK_H                       # neck rim


# ------------------------------------------------------------------ helpers
def ring(r_out, r_in, h):
    return Manifold.cylinder(h, r_out, r_out, SEG) - Manifold.cylinder(h + 2, r_in, r_in, SEG).translate([0, 0, -1])


def thread(r_base, z0, turns, inward=False):
    """Trapezoid thread (45 degree flanks) wound on radius r_base, starting at height z0."""
    crest = PITCH - 2 * THREAD_DEPTH - 0.8
    b = crest + 2 * THREAD_DEPTH
    prof = [(-0.6, -b / 2 - 0.6), (0, -b / 2), (THREAD_DEPTH, -crest / 2),
            (THREAD_DEPTH, crest / 2), (0, b / 2), (-0.6, b / 2 + 0.6)]
    length = turns * 2 * math.pi * r_base
    bar = Manifold.extrude(CrossSection([np.array(prof)]), length).refine_to_length(1.0)
    s = -1 if inward else 1

    def wrap(p):
        u, v, w = p
        t = w / r_base
        r = r_base + s * u
        # winding inward mirrors the shape; flipping v (the profile is symmetric) undoes it
        return (r * math.cos(t), r * math.sin(t), z0 + s * v + PITCH * t / (2 * math.pi))
    return bar.warp(wrap)


def toothed(r_root, depth, n, lock_ccw, extra=0.0, samples=6, floor=0.0):
    """Outline of a click-tooth ring. lock_ccw=False: a pawl moving clockwise catches
    (tightening); lock_ccw=True: a pawl moving counter-clockwise catches (opening)."""
    pts = []
    d = 2 * math.pi / n
    for k in range(n):
        for j in range(samples + 1):
            f = j / samples * 0.9999
            b = depth * ((1 - f) if lock_ccw else f)
            t = k * d + f * d
            r = max(floor, r_root + b) + extra
            pts.append((r * math.cos(t), r * math.sin(t)))
    return np.array(pts)


def circle_pts(r, n=SEG):
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.column_stack([r * np.cos(t), r * np.sin(t)])


def sector(r, a0, a1):
    t = np.linspace(a0, a1, 24)
    return CrossSection([np.vstack([[0, 0], np.column_stack([r * np.cos(t), r * np.sin(t)])])])


# ------------------------------------------------------------------ jar body
ri = rn - WALL
c = 1.0
body_prof = [(0, 0), (R - c, 0), (R, c), (R, BODY_H - 1.5), (R - 1.5, BODY_H), (rn, BODY_H),
             (rn, top_z - 0.5), (rn - 0.5, top_z), (ri + 0.5, top_z), (ri, top_z - 0.5),
             (ri, BODY_H + 2), (R - WALL, BODY_H + 2 - (R - WALL - ri)),
             (R - WALL, BASE + 2), (R - WALL - 2, BASE), (0, BASE)]
jar = revolve(body_prof)
thread_z0 = top_z - 8.5
jar += thread(rn, thread_z0, 1.5) - Manifold.cylinder(top_z, ri + 0.1, ri + 0.1, SEG)


# ------------------------------------------------------------------ inner cap (use position)
skirt = NECK_H - 5                      # inner cap skirt height
ic_top = top_z + 2.0                    # top surface of inner cap
ic_bot = top_z - skirt
r_iw = rn + THREAD_DEPTH + FIT          # inside wall
r_ic = r_iw + 2.0                       # outside wall
OPEN_BAND = 2.0
inner = ring(r_ic, r_iw, skirt).translate([0, 0, ic_bot]) + \
    Manifold.cylinder(2.0, r_ic, r_ic, SEG).translate([0, 0, top_z])
inner += thread(r_iw, thread_z0 + PITCH / 2, 1.25, inward=True)
inner -= Manifold.cylinder(skirt, rn - 0.2, rn - 0.2, SEG).translate([0, 0, ic_bot - 0.01])
teeth_ring = lambda lock: CrossSection([toothed(r_ic - 0.3, RATCHET + 0.3, CLICKS, lock)]) - CrossSection([circle_pts(r_ic - 1.0)])
close_teeth = Manifold.extrude(teeth_ring(False),
                               ic_top - OPEN_BAND - 0.5 - (ic_bot + 1.0)).translate([0, 0, ic_bot + 1.0])
open_teeth = Manifold.extrude(teeth_ring(True),
                              OPEN_BAND).translate([0, 0, ic_top - OPEN_BAND])
bead = ring(r_ic + RATCHET, r_ic - 0.3, 1.0).translate([0, 0, ic_bot])     # the lid's lip snaps under this
inner = inner + close_teeth + open_teeth + bead


# ------------------------------------------------------------------ outer cap (own frame: z=0 at underside of top)
r_os = r_ic + RATCHET + 0.4              # skirt inside
r_oo = r_os + LID_WALL                   # lid outside
G = 1.6 + 0.6                            # inner-cap top sits this far below the underside at rest
inner_top_local = -G
lug_lo, lug_hi = inner_top_local - OPEN_BAND - 6.0, inner_top_local - OPEN_BAND - 1.0
bead_local = (ic_bot - ic_top) + inner_top_local          # bottom of inner cap, in lid frame
lip_apex = bead_local - 1.0 - 0.95                         # stays under the bead even when lifted
skirt_end = lip_apex - 1.0
lid_h = TOP_T - skirt_end

outer = ring(r_oo, r_os, lid_h).translate([0, 0, skirt_end]) + \
    Manifold.cylinder(TOP_T, r_oo, r_oo, SEG)
# soften the top edge and add grip rings
outer -= (Manifold.cylinder(1.2, r_oo + 5, r_oo + 5, SEG) - Manifold.cylinder(1.2, r_oo - 0.8, r_oo + 0.4, SEG)).translate([0, 0, TOP_T - 1.2])
z = TOP_T - 2.6
while z > skirt_end + 1.6:
    groove = revolve([(r_oo - 0.7, z), (r_oo + 1, z - 1.7), (r_oo + 1, z + 1.7)])
    outer -= groove
    z -= RIB_PITCH
# snap lip: 45 degree retaining face, sloped lead-in
lip_in = r_ic + 0.15
outer += revolve([(r_os + 0.3, lip_apex + (r_os - lip_in) + 0.3), (lip_in, lip_apex),
                  (r_os + 0.3, skirt_end), (r_os + 0.3, skirt_end)])
# pawls: three on the lower skirt (tighten), three keys just under the top (open when pushed)
annulus = lambda lock: CrossSection([circle_pts(r_os + 0.3), toothed(r_ic - 0.3, RATCHET + 0.3, CLICKS, lock, 0.15, floor=r_ic)[::-1]], FillRule.EvenOdd)
d = 2 * math.pi / CLICKS
for i in range(3):
    a = i * 2 * math.pi / 3
    lug = annulus(False) ^ sector(r_oo, a, a + d * 0.999)
    outer += Manifold.extrude(lug, lug_hi - lug_lo).translate([0, 0, lug_lo])
    key = annulus(True) ^ sector(r_oo, a + d * 4, a + d * 6 * 0.999)
    outer += Manifold.extrude(key, 1.6 + 0.01).translate([0, 0, -1.6])

# three arc springs cut into the top, each with a post that rests on the inner cap
text_out = r_oo - 1.2                                    # lettering stays inside the edge bevel
text_in = text_out - TEXT_SIZE - 0.3
w_sp = 3.0 if r_oo < 30 else 4.0
r_sp = text_in - 0.5 - 1.0 - w_sp / 2                      # springs just inside the lettering
assert r_sp + 1.5 < r_ic, "springs must rest on the inner cap"
for i in range(3):
    a0 = math.radians(i * 120 + 20)
    a1 = a0 + math.radians(70)
    slot_o = CrossSection([np.vstack([circle_pts(r_sp + w_sp / 2 + 1.0, 72)])]) - CrossSection([circle_pts(r_sp - w_sp / 2 - 1.0, 72)])
    tongue = CrossSection([circle_pts(r_sp + w_sp / 2, 72)]) - CrossSection([circle_pts(r_sp - w_sp / 2, 72)])
    slot = (slot_o - tongue) ^ sector(40, a0 - 0.02, a1 + 0.12)          # U-shaped slot
    outer -= Manifold.extrude(slot, TOP_T + 2).translate([0, 0, -1])
    thin = tongue ^ sector(40, a0, a1)
    outer -= Manifold.extrude(thin, 1.2).translate([0, 0, -0.01])         # tongue is 1.2 mm thick
    pa = a1 - math.radians(5)
    post = box(3, 3, 1.2 + G + 0.3).translate([-1.5, -1.5, inner_top_local - 0.3])
    outer += post.translate([r_sp * math.cos(pa), r_sp * math.sin(pa), 0])

# engraved lettering + arrows on the top, medallion pocket in the middle
MED_R = r_sp - w_sp / 2 - 2.0
outer -= Manifold.cylinder(1.0 + 0.01, MED_R, MED_R, SEG).translate([0, 0, TOP_T - 1.0])


def arc_text(s, r, size, center_deg, top=True, depth=0.6):
    glyphs, widths = [], []
    for ch in s:
        if ch == " ":
            glyphs.append(None); widths.append(size * 0.45); continue
        g = text2d(ch, size, font="DejaVu Sans", bold=True)
        b = g.bounds()
        glyphs.append(g.translate([-(b[0] + b[2]) / 2, 0])); widths.append(b[2] - b[0] + size * 0.18)
    total = sum(widths)
    out = None
    pos = -total / 2
    for g, w in zip(glyphs, widths):
        mid = pos + w / 2
        pos += w
        if g is None:
            continue
        if top:   # reads clockwise along the top, letters point outward
            ang = math.radians(center_deg) - mid / r
            g2 = g.translate([0, -size * 0.36]).rotate(math.degrees(ang) - 90).translate([r * math.cos(ang), r * math.sin(ang)])
        else:     # reads left to right along the bottom, letters point to the center
            ang = math.radians(center_deg) + mid / r
            g2 = g.translate([0, -size * 0.36]).rotate(math.degrees(ang) + 90).translate([r * math.cos(ang), r * math.sin(ang)])
        cut = Manifold.extrude(g2, depth + 0.01).translate([0, 0, TOP_T - depth])
        out = cut if out is None else out + cut
    return out


def arc_arrow(r, a_from, a_to, depth=0.6, w=1.2):
    t = np.linspace(math.radians(a_from), math.radians(a_to), 30)
    band = np.vstack([np.column_stack([(r + w / 2) * np.cos(t), (r + w / 2) * np.sin(t)]),
                      np.column_stack([(r - w / 2) * np.cos(t[::-1]), (r - w / 2) * np.sin(t[::-1])])])
    te = math.radians(a_to)
    sgn = 1 if a_to > a_from else -1
    tip = ((r) * math.cos(te + sgn * 0.12), (r) * math.sin(te + sgn * 0.12))
    hw = min(2.2, TEXT_SIZE * 0.6)
    head = [((r + hw) * math.cos(te), (r + hw) * math.sin(te)), tip, ((r - hw) * math.cos(te), (r - hw) * math.sin(te))]
    cs = CrossSection([band]) + CrossSection([np.array(head)])
    return Manifold.extrude(cs, depth + 0.01).translate([0, 0, TOP_T - depth])


outer -= arc_text("PUSH DOWN & TURN", text_out - 0.64 * TEXT_SIZE, TEXT_SIZE, 90, top=True)
outer -= arc_text("TO OPEN", text_out - 0.36 * TEXT_SIZE, TEXT_SIZE, 270, top=False)
mid = text_out - TEXT_SIZE / 2
outer -= arc_arrow(mid, 160, 205, w=min(1.2, TEXT_SIZE * 0.35))      # left side: points down (counter-clockwise)
outer -= arc_arrow(mid, -25, 20, w=min(1.2, TEXT_SIZE * 0.35))       # right side: points up (counter-clockwise)


# ------------------------------------------------------------------ art: wrap + medallion
def art_arrays(h_mm, w_mm, step=0.25):
    from PIL import Image, ImageFilter
    p = os.path.join(ROOT, "inputs", ART)
    if not os.path.isfile(p):
        return None
    im = Image.open(p)
    nx, ny = int(w_mm / step), int(h_mm / step)
    a = np.asarray(im.getchannel("A").resize((nx, ny), Image.LANCZOS), float) / 255 > 0.5
    g = np.asarray(im.convert("L").resize((nx, ny), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.8)), float) / 255
    g = (g - g[a].min()) / max(1e-6, np.ptp(g[a]))
    return a, g


def swirl(xs, ys):
    f = np.sin(0.55 * xs + 2.2 * np.sin(0.09 * ys + 0.05 * xs) + 1.5 * np.sin(0.04 * xs - 0.07 * ys))
    return (f > 0.72).astype(float)


step = 0.25
art_w = None
src = os.path.join(ROOT, "inputs", ART)
if os.path.isfile(src):
    from PIL import Image
    with Image.open(src) as im:
        aspect = im.width / im.height
    art_w = ART_H * aspect
    band_h = BODY_H - 4.0
    circ = 2 * math.pi * R - 1.0                # leave a hairline gap at the back seam
    nx, ny = int(circ / step), int(band_h / step)
    xs, ys = np.meshgrid(np.arange(nx) * step, np.arange(ny)[::-1] * step)
    hz = 0.4 + TEXTURE * swirl(xs, ys)
    a, g = art_arrays(ART_H, art_w, step)
    ax0 = (nx - a.shape[1]) // 2
    ay0 = (ny - a.shape[0]) // 2
    region = hz[ay0:ay0 + a.shape[0], ax0:ax0 + a.shape[1]]
    region[a] = 0.4 + ART_RAISE + ART_DETAIL * g[a]
    halo = np.zeros_like(a)
    from scipy import ndimage as ndi
    halo = ndi.binary_dilation(a, iterations=int(1.0 / step)) & ~a
    region[halo] = 0.4                          # clean border around the picture
    plate = heightmap(hz, circ)
    z_band = 2.0

    def wrap(p):
        x, y, hh = p
        t = math.radians(270) + (x - circ / 2) / R
        rr = R - 0.4 + hh
        return (rr * math.cos(t), rr * math.sin(t), z_band + y)
    jar = jar + plate.warp(wrap)

medallion = None
if art_w:
    md = 2 * MED_R - 0.4
    mh = MED_R * 1.43
    mw = mh * aspect
    n = int(md / step)
    xs, ys = np.meshgrid(np.arange(n) * step, np.arange(n)[::-1] * step)
    hz = 1.0 + 0.3 * swirl(xs * 1.6, ys * 1.6)
    a, g = art_arrays(mh, mw, step)
    ox, oy = (n - a.shape[1]) // 2, (n - a.shape[0]) // 2
    reg = hz[oy:oy + a.shape[0], ox:ox + a.shape[1]]
    reg[a] = 1.0 + ART_RAISE + ART_DETAIL * g[a]
    medallion = heightmap(hz, md - step).translate([-(md - step) / 2, -(md - step) / 2, 0]) ^ \
        Manifold.cylinder(5, md / 2, md / 2, SEG)
    medallion = medallion + Manifold.cylinder(1.0, md / 2, md / 2, SEG)


def make_labels(out_dir):
    """Full-color wrap label for the jar and a round sticker for the lid (300 dpi)."""
    from PIL import Image, ImageDraw
    if not art_w:
        return
    dpi = 300
    mm = lambda v: round(v / 25.4 * dpi)
    W, H = mm(2 * math.pi * R), mm(BODY_H - 4)
    yy, xx = np.mgrid[0:H, 0:W]
    lines = swirl(xx / dpi * 25.4, (H - yy) / dpi * 25.4)
    base = np.dstack([18 + 30 * yy / H, 10 + 4 * yy / H, 40 + 40 * yy / H])
    hi = np.array([150, 60, 200])
    img = (base * (1 - lines[..., None] * 0.6) + hi * lines[..., None] * 0.6).clip(0, 255).astype(np.uint8)
    label = Image.fromarray(img)
    art = Image.open(src)
    ah = mm(ART_H)
    art = art.resize((round(art.width * ah / art.height), ah), Image.LANCZOS)
    label.paste(art, ((W - art.width) // 2, (H - ah) // 2), art)
    ImageDraw.Draw(label).rectangle((0, 0, W - 1, H - 1), outline=(160, 160, 160), width=2)
    label.save(os.path.join(out_dir, "gta6_cr_jar_wrap_label.png"), dpi=(dpi, dpi))
    d = mm(2 * MED_R - 0.4)
    disc = Image.new("RGB", (d, d), (20, 12, 45))
    ah = mm(MED_R * 1.43)
    art2 = Image.open(src).resize((round(ah * aspect), ah), Image.LANCZOS)
    disc.paste(art2, ((d - art2.width) // 2, (d - ah) // 2), art2)
    m = Image.new("L", (d, d), 0)
    ImageDraw.Draw(m).ellipse((0, 0, d - 1, d - 1), fill=255)
    sheet = Image.new("RGB", (d + 40, d + 40), "white")
    sheet.paste(disc, (20, 20), m)
    ImageDraw.Draw(sheet).ellipse((20, 20, 20 + d - 1, 20 + d - 1), outline=(160, 160, 160), width=2)
    sheet.save(os.path.join(out_dir, "gta6_cr_jar_lid_sticker.png"), dpi=(dpi, dpi))
    print(f"labels: wrap {2 * math.pi * R:.1f} x {BODY_H - 4:.0f} mm, lid sticker {2 * MED_R - 0.4:.1f} mm (print at 100%)")


def assembled():
    """Everything in place on the jar, lid at rest: for previews and fit checks."""
    lid_z = ic_top - inner_top_local
    parts = [jar, inner, outer.translate([0, 0, lid_z])]
    if medallion:
        parts.append(medallion.translate([0, 0, lid_z + TOP_T - 1.0]))
    return parts


if __name__ == "__main__":
    out = os.path.join(ROOT, "out")
    # print orientation: jar upright, both caps top-down, medallion face up
    flip = lambda m: m.rotate([180, 0, 0])
    parts = {"jar_body": jar, "inner_cap": flip(inner), "outer_cap": flip(outer)}
    if medallion:
        parts["medallion"] = medallion
    export(parts, "gta6_cr_jar", out_dir=out)
    make_labels(out)
    # interference check of the assembled lid at rest and pushed
    lid_z = ic_top - inner_top_local
    # the spring posts are meant to press on the inner cap (the springs flex), so leave them out
    rigid = outer - ring(r_sp + 2.5, r_sp - 2.5, 20).translate([0, 0, -20])
    for name, dz in (("at rest", 0), ("pushed", -PUSH)):
        o = rigid.translate([0, 0, lid_z + dz])
        print(f"lid {name}: collision with inner cap {(o ^ inner).volume():.2f} mm3, with jar {(o ^ jar).volume():.2f} mm3")
    print(f"inner cap vs jar threads overlap: {(inner ^ jar).volume():.2f} mm3")
    print(f"jar holds about {math.pi * (R - WALL) ** 2 * (BODY_H - BASE) / 1000 + math.pi * ri ** 2 * NECK_H / 1000:.0f} ml")
