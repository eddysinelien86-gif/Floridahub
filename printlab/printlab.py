"""printlab — tiny CAD toolkit for designing parts to print on a Bambu Lab printer.

Solids are manifold3d.Manifold objects (always watertight, so Bambu Studio never
needs to "repair" them). Units are millimetres. Z is up; parts should sit on Z=0.

Typical design file:

    from printlab import *
    part = box(60, 40, 20) - box(56, 36, 20).translate([2, 2, 2])
    export(part, "my_box")          # writes out/my_box.stl, .3mf, .png and a report
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass

import numpy as np
import trimesh
from manifold3d import CrossSection, JoinType, Manifold, OpType

# --------------------------------------------------------------------------
# Printer profiles (build volume in mm)
# --------------------------------------------------------------------------
PRINTERS = {
    "X1C": (256, 256, 256), "X1E": (256, 256, 256),
    "P1S": (256, 256, 256), "P1P": (256, 256, 256),
    "P2S": (256, 256, 256),
    "A1": (256, 256, 256), "A1mini": (180, 180, 180),
    "H2D": (325, 320, 325),
}
DEFAULT_PRINTER = os.environ.get("BAMBU_PRINTER", "P1S")

# Rules of thumb for a 0.4 mm nozzle
NOZZLE = 0.4
MIN_WALL = 0.8          # 2 perimeters
GOOD_WALL = 1.6         # 4 perimeters — sturdy
FIT_CLEARANCE = 0.2     # per side, for parts that slide together
PRESS_CLEARANCE = 0.1   # per side, tight press fit
SEGMENTS = 96           # circle smoothness

# --------------------------------------------------------------------------
# Primitives (all placed with their min corner / base at the origin unless noted)
# --------------------------------------------------------------------------

def box(x: float, y: float, z: float, center: bool = False) -> Manifold:
    return Manifold.cube([x, y, z], center)


def rounded_box(x: float, y: float, z: float, r: float = 3.0) -> Manifold:
    """Box with rounded vertical edges (flat top & bottom — prints cleanly)."""
    r = min(r, x / 2 - 0.01, y / 2 - 0.01)
    if r <= 0:
        return box(x, y, z)
    cs = CrossSection.square([x - 2 * r, y - 2 * r]).translate([r, r]).offset(
        r, JoinType.Round, circular_segments=SEGMENTS)
    return Manifold.extrude(cs, z)


def cylinder(d: float, h: float, d2: float | None = None, center: bool = False) -> Manifold:
    """Cylinder (or cone if d2 given) standing on Z=0, centred on X/Y."""
    r2 = (d2 if d2 is not None else d) / 2
    return Manifold.cylinder(h, d / 2, r2, SEGMENTS, center)


def sphere(d: float) -> Manifold:
    return Manifold.sphere(d / 2, SEGMENTS)


def polygon_extrude(points, h: float) -> Manifold:
    """Extrude a 2D outline [(x, y), ...] up by h."""
    return Manifold.extrude(CrossSection([points]), h)


def tube(od: float, id: float, h: float) -> Manifold:
    return cylinder(od, h) - cylinder(id, h + 2).translate([0, 0, -1])


def hole(d: float, depth: float, clearance: float = FIT_CLEARANCE) -> Manifold:
    """A cutter for a round hole that will actually fit a d-mm pin/screw."""
    return cylinder(d + 2 * clearance, depth + 2).translate([0, 0, -1])


def countersunk_hole(d: float, head_d: float, depth: float) -> Manifold:
    """Cutter for a countersunk screw entering from the top surface at Z=depth."""
    shaft = hole(d, depth)
    head_h = (head_d - d) / 2
    head = cylinder(d, head_h + 0.01, head_d + 0.4).translate([0, 0, depth - head_h])
    return shaft + head + cylinder(head_d + 0.4, 5).translate([0, 0, depth])


def hex_nut_trap(across_flats: float, h: float) -> Manifold:
    d = (across_flats + 2 * PRESS_CLEARANCE) / math.cos(math.pi / 6)
    return Manifold.cylinder(h, d / 2, d / 2, 6)


def text_plate_not_supported(*_a, **_k):  # pragma: no cover
    raise NotImplementedError("Text: design in Blender or add the label in Bambu Studio.")


def union(*parts: Manifold) -> Manifold:
    return Manifold.batch_boolean(list(parts), OpType.Add)


def on_bed(part: Manifold) -> Manifold:
    """Drop the part so its lowest point rests on Z=0 and centre it on X/Y."""
    lo, hi = _bounds(part)
    return part.translate([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def _bounds(part: Manifold):
    b = part.bounding_box()
    return np.array(b[:3]), np.array(b[3:])


def to_trimesh(part: Manifold) -> trimesh.Trimesh:
    m = part.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(m.vert_properties)[:, :3],
                           faces=np.asarray(m.tri_verts), process=False)


@dataclass
class Report:
    name: str
    size: tuple
    volume_cm3: float
    grams_pla: float
    watertight: bool
    fits: bool
    printer: str
    warnings: list

    def __str__(self) -> str:
        lines = [
            f"== {self.name} ==",
            f"  size        : {self.size[0]:.1f} x {self.size[1]:.1f} x {self.size[2]:.1f} mm",
            f"  volume      : {self.volume_cm3:.1f} cm3  (~{self.grams_pla:.0f} g PLA at 100% infill, "
            f"~{self.grams_pla * 0.45:.0f} g at typical 15% infill)",
            f"  watertight  : {self.watertight}",
            f"  fits {self.printer:<7}: {self.fits}",
        ]
        lines += [f"  WARNING: {w}" for w in self.warnings] or ["  no warnings"]
        return "\n".join(lines)


def check(part: Manifold, name: str = "part", printer: str = DEFAULT_PRINTER) -> Report:
    lo, hi = _bounds(part)
    size = hi - lo
    mesh = to_trimesh(part)
    warnings = []
    bed = PRINTERS[printer]
    fits = bool(np.all(size <= np.array(bed)))
    if not fits:
        warnings.append(f"too big for {printer} {bed} — split the part or scale it")
    if part.is_empty():
        warnings.append("part is empty — a boolean probably removed everything")
    if abs(lo[2]) > 0.01:
        warnings.append(f"lowest point is at Z={lo[2]:.2f}, not on the bed — use on_bed()")
    n_bodies = len(part.decompose())
    if n_bodies > 1:
        warnings.append(f"{n_bodies} separate bodies — intended? (fine for a multi-part plate)")
    # first-layer contact area
    z0 = part.slice(lo[2] + 0.1)
    contact = z0.area()
    if contact < 50 and not part.is_empty():
        warnings.append(f"only {contact:.0f} mm2 touching the bed — add a brim or flip the part")
    # overhangs: faces pointing down steeper than 45 deg that are not on the bed
    if len(mesh.faces):
        n = mesh.face_normals
        centroids = mesh.triangles_center
        down = (n[:, 2] < -math.cos(math.radians(45))) & (centroids[:, 2] > lo[2] + 0.2)
        over = mesh.area_faces[down].sum()
        if over > 100:
            warnings.append(f"~{over:.0f} mm2 of overhang >45 deg — enable supports or reorient")
    vol = part.volume() / 1000.0
    return Report(name, tuple(size), vol, vol * 1.24, mesh.is_watertight, fits, printer, warnings)


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def render_png(parts: dict, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(10, 5), dpi=120)
    views = [(25, -60, "3/4 view"), (90, -90, "top")]
    colors = ["#2f9e44", "#1971c2", "#e8590c", "#9c36b5", "#f08c00"]
    allpts = np.vstack([to_trimesh(p).vertices for p in parts.values()])
    lo, hi = allpts.min(0), allpts.max(0)
    span = (hi - lo).max() / 2
    mid = (hi + lo) / 2
    light = np.array([0.3, -0.5, 0.8]); light /= np.linalg.norm(light)
    for i, (elev, azim, title) in enumerate(views):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        for j, (pname, p) in enumerate(parts.items()):
            m = to_trimesh(p)
            base = np.array(matplotlib.colors.to_rgb(colors[j % len(colors)]))
            shade = 0.45 + 0.55 * np.clip(m.face_normals @ light, 0, 1)
            fc = np.clip(base[None, :] * shade[:, None], 0, 1)
            ax.add_collection3d(Poly3DCollection(m.triangles, facecolors=fc, linewidths=0))
        for setlim, k in ((ax.set_xlim, 0), (ax.set_ylim, 1), (ax.set_zlim, 2)):
            setlim(mid[k] - span, mid[k] + span)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(title)
        ax.set_xlabel("X mm"); ax.set_ylabel("Y mm"); ax.set_zlabel("Z mm")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def export(parts, name: str, out_dir: str = "out", printer: str = DEFAULT_PRINTER,
           spacing: float = 10.0) -> list[Report]:
    """Write STL (one per part), a single 3MF plate with every part, a PNG preview
    and a text report. `parts` is a Manifold or a dict {"name": Manifold}."""
    if isinstance(parts, Manifold):
        parts = {name: parts}
    os.makedirs(out_dir, exist_ok=True)
    reports = []
    scene = trimesh.Scene()
    x_cursor = 0.0
    laid_out = {}
    for pname, p in parts.items():
        p = on_bed(p)
        reports.append(check(p, pname, printer))
        to_trimesh(p).export(os.path.join(out_dir, f"{pname}.stl"))
        lo, hi = _bounds(p)
        placed = p.translate([x_cursor - lo[0], 0, 0])
        x_cursor += (hi[0] - lo[0]) + spacing
        laid_out[pname] = placed
        scene.add_geometry(to_trimesh(placed), node_name=pname, geom_name=pname)
    plate = on_bed(union(*laid_out.values())) if len(laid_out) > 1 else None
    if plate is not None:
        lo, hi = _bounds(plate)
        bed = PRINTERS[printer]
        if (hi - lo)[0] > bed[0] or (hi - lo)[1] > bed[1]:
            print(f"note: parts don't all fit on one {printer} plate together — "
                  "Bambu Studio will let you split them across plates.")
    scene.export(os.path.join(out_dir, f"{name}.3mf"))
    render_png(laid_out, os.path.join(out_dir, f"{name}.png"))
    text = "\n\n".join(str(r) for r in reports)
    with open(os.path.join(out_dir, f"{name}_report.txt"), "w") as f:
        f.write(text + "\n")
    print(text)
    print(f"\nwrote {out_dir}/{name}.3mf (open this in Bambu Studio), STLs, and {name}.png")
    return reports
