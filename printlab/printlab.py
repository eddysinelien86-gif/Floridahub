"""printlab — tiny CAD toolkit for designing parts to print on a Bambu Lab printer.

Solids are manifold3d.Manifold objects (always watertight, so Bambu Studio never
needs to "repair" them). Units are millimetres. Z is up; parts should sit on Z=0.

Typical design file:

    from printlab import *
    part = box(60, 40, 20) - box(56, 36, 20).translate([2, 2, 2])
    export(part, "my_box")          # writes out/my_box.stl, .3mf, .png and a report
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import asdict
from dataclasses import dataclass

import numpy as np
import trimesh
from manifold3d import CrossSection, FillRule, JoinType, Manifold, Mesh, OpType

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


def union(*parts: Manifold) -> Manifold:
    return Manifold.batch_boolean(list(parts), OpType.Add)


def on_bed(part: Manifold) -> Manifold:
    """Drop the part so its lowest point rests on Z=0 and centre it on X/Y."""
    lo, hi = _bounds(part)
    return part.translate([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])


# --------------------------------------------------------------------------
# Beyond boxes: text, turned shapes, organic shapes, images, existing meshes
# --------------------------------------------------------------------------

def text2d(s: str, size: float = 10, font: str = "DejaVu Sans", bold: bool = True,
           halign: str = "left") -> CrossSection:
    """Outline of text as a 2D CrossSection (size = cap height-ish, mm)."""
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    tp = TextPath((0, 0), s, size=size,
                  prop=FontProperties(family=font, weight="bold" if bold else "normal"))
    polys = []
    for p in tp.to_polygons():
        p = np.asarray(p, dtype=float)
        if len(p) > 1 and np.allclose(p[0], p[-1]):
            p = p[:-1]
        if len(p) >= 3:
            polys.append(p)
    cs = CrossSection(polys, FillRule.EvenOdd)
    if halign in ("center", "right") and not cs.is_empty():
        b = cs.bounds()
        w = b[2] - b[0]
        cs = cs.translate([-(b[0] + (w / 2 if halign == "center" else w)), 0])
    return cs


def text(s: str, size: float = 10, height: float = 2, **kw) -> Manifold:
    """Raised 3D text standing on Z=0. Add it on top of a part to emboss it, or
    subtract it to engrave. Keep letters >= 5 mm tall and strokes >= 0.8 mm."""
    return Manifold.extrude(text2d(s, size, **kw), height)


def revolve(profile, degrees: float = 360) -> Manifold:
    """Spin a 2D profile [(radius, z), ...] around the Z axis: vases, cups, knobs,
    bottles, chess pieces, wheels. Radius values must be >= 0."""
    return Manifold.revolve(CrossSection([np.asarray(profile, float)]), SEGMENTS, degrees)


def hull(*parts: Manifold) -> Manifold:
    """Convex hull, the shrink-wrap around all parts. Great for smooth organic blends."""
    return Manifold.batch_hull(list(parts))


def smooth(part: Manifold, subdivisions: int = 3, sharp_angle: float = 60) -> Manifold:
    """Round off a blocky shape into a soft, organic one (edges sharper than
    `sharp_angle` degrees are kept)."""
    return part.smooth_out(sharp_angle).refine(subdivisions)


def sdf(f, bounds, resolution: float = 0.5) -> Manifold:
    """Organic/mathematical shape from a signed distance function f(x, y, z) that is
    POSITIVE INSIDE the shape. bounds = (xmin, ymin, zmin, xmax, ymax, zmax).
    Example sphere: sdf(lambda x, y, z: 10 - (x*x + y*y + z*z) ** 0.5, (-11,)*3 + (11,)*3)."""
    return Manifold.level_set(f, list(bounds), resolution)


def smooth_union(a: float, b: float, k: float = 4.0) -> float:
    """For sdf(): blend two positive-inside distances with a fillet of about k mm."""
    h = max(k - abs(a - b), 0.0) / k
    return max(a, b) + h * h * k * 0.25


def scale_to(part: Manifold, x: float | None = None, y: float | None = None,
             z: float | None = None) -> Manifold:
    """Uniformly scale so the part is exactly x (or y, or z) mm in that direction."""
    lo, hi = _bounds(part)
    size = hi - lo
    for target, k in ((x, 0), (y, 1), (z, 2)):
        if target:
            return part.scale([target / size[k]] * 3)
    return part


def from_trimesh(mesh: trimesh.Trimesh) -> Manifold:
    mesh = mesh.copy()
    mesh.merge_vertices()
    m = Manifold(Mesh(np.ascontiguousarray(mesh.vertices, dtype=np.float32),
                      np.ascontiguousarray(mesh.faces, dtype=np.uint32)))
    if m.is_empty():
        trimesh.repair.fill_holes(mesh)
        trimesh.repair.fix_normals(mesh)
        m = Manifold(Mesh(np.ascontiguousarray(mesh.vertices, dtype=np.float32),
                          np.ascontiguousarray(mesh.faces, dtype=np.uint32)))
    if m.is_empty():
        raise ValueError(f"mesh is not watertight ({m.status()}); repair it in Blender first")
    return m


def load_mesh(path: str) -> Manifold:
    """Import an existing STL/3MF/OBJ/PLY (a download, a Blender export, a scan) so it
    can be cut, combined, resized, hollowed or given mounting holes."""
    return from_trimesh(trimesh.load(path, force="mesh"))


def _load_gray(path: str, max_px: int) -> np.ndarray:
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(Image.open(path)).convert("L")
    img.thumbnail((max_px, max_px))
    return np.asarray(img, dtype=float) / 255.0


def image_outline(path: str, width: float, threshold: float = 0.5,
                  invert: bool = False) -> CrossSection:
    """Trace the dark parts of a logo/drawing/silhouette (PNG/JPG) into a 2D shape
    `width` mm wide. invert=True traces the light parts instead."""
    import contourpy
    g = _load_gray(path, 800)
    ink = (g > threshold) if invert else (g < threshold)
    ink = np.pad(ink.astype(float), 1)
    lines = contourpy.contour_generator(z=ink).lines(0.5)
    h_px, w_px = ink.shape
    k = width / w_px
    polys = [np.column_stack([l[:, 0] * k, (h_px - l[:, 1]) * k]) for l in lines if len(l) >= 4]
    return CrossSection(polys, FillRule.EvenOdd).simplify(k * 0.3)


def image_extrude(path: str, width: float, height: float, **kw) -> Manifold:
    """Logo/drawing to a 3D badge, stamp, cookie-cutter blank, wall art layer."""
    return Manifold.extrude(image_outline(path, width, **kw), height)


def heightmap(z: np.ndarray, width: float, base: float = 0.0) -> Manifold:
    """Watertight solid from a 2D array of heights in mm (row 0 = back edge)."""
    z = np.asarray(z, float) + base
    ny, nx = z.shape
    k = width / (nx - 1)
    xs, ys = np.meshgrid(np.arange(nx) * k, (ny - 1 - np.arange(ny)) * k)
    top = np.column_stack([xs.ravel(), ys.ravel(), z.ravel()])
    bot = top.copy(); bot[:, 2] = 0
    verts = np.vstack([top, bot])
    n = nx * ny
    idx = np.arange(n).reshape(ny, nx)
    a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    faces = [np.column_stack([a, c, b]), np.column_stack([b, c, d]),              # top (normals up)
             np.column_stack([a + n, b + n, c + n]), np.column_stack([b + n, d + n, c + n])]  # bottom
    for edge, flip in ((idx[0, :], True), (idx[-1, :], False), (idx[:, 0], False), (idx[:, -1], True)):
        e0, e1 = edge[:-1], edge[1:]
        q = [np.column_stack([e0, e1, e0 + n]), np.column_stack([e1, e1 + n, e0 + n])]
        faces += [f[:, ::-1] for f in q] if flip else q
    mesh = trimesh.Trimesh(verts, np.vstack(faces), process=False)
    if mesh.volume < 0:
        mesh.invert()
    return from_trimesh(mesh)


def lithophane(path: str, width: float = 100, min_t: float = 0.8, max_t: float = 3.2,
               px_mm: float = 0.25) -> Manifold:
    """Photo lithophane: dark pixels thick, light pixels thin. Lies flat as built; print it
    standing upright (rotate([90, 0, 0])) in white PLA at 0.12 mm layers, 100% infill,
    and hold it up to a light."""
    from PIL import Image
    g = _load_gray(path, 2000)
    nx = max(2, int(width / px_mm))
    ny = max(2, int(nx * g.shape[0] / g.shape[1]))
    g = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((nx, ny)), float) / 255
    return heightmap(min_t + (1 - g) * (max_t - min_t), width)


def find_blender() -> str | None:
    import glob
    import shutil
    hit = shutil.which("blender")
    if hit:
        return hit
    pats = [r"C:\Program Files\Blender Foundation\Blender*\blender.exe",
            "/Applications/Blender.app/Contents/MacOS/Blender",
            "/snap/bin/blender", os.path.expanduser("~/blender*/blender")]
    for p in pats:
        found = sorted(glob.glob(p))
        if found:
            return found[-1]
    return None


def blender_model(bpy_code: str, workdir: str = "out") -> Manifold:
    """Run bpy code in Blender (headless) to build sculpted/organic geometry with
    modifiers, then bring every mesh object back as one Manifold.
    The code starts from an EMPTY scene, units are mm, and `bpy` is imported."""
    import subprocess
    import tempfile
    exe = find_blender()
    if not exe:
        raise RuntimeError("Blender not found; install it or add it to PATH")
    os.makedirs(workdir, exist_ok=True)
    out = os.path.abspath(os.path.join(workdir, "_blender_export.stl"))
    script = ("import bpy\nbpy.ops.wm.read_factory_settings(use_empty=True)\n"
              + bpy_code +
              "\nbpy.ops.object.select_all(action='DESELECT')\n"
              "for o in bpy.data.objects:\n"
              "    if o.type == 'MESH': o.select_set(True)\n"
              f"bpy.ops.wm.stl_export(filepath={out!r}, export_selected_objects=True, "
              "apply_modifiers=True, global_scale=1.0)\n")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(script)
    try:
        r = subprocess.run([exe, "-b", "--factory-startup", "--python", f.name],
                           capture_output=True, text=True, timeout=600)
    finally:
        os.unlink(f.name)
    if not os.path.isfile(out):
        raise RuntimeError("Blender export failed:\n" + (r.stdout + r.stderr)[-3000:])
    return load_mesh(out)


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
        if elev == 90:
            ax.set_proj_type("ortho")
            ax.set_zticks([])
            ax.set_zlabel("")
        ax.set_title(title)
        ax.set_xlabel("X mm"); ax.set_ylabel("Y mm"); ax.set_zlabel("Z mm")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def export(parts, name: str, out_dir: str = "out", printer: str = DEFAULT_PRINTER,
           spacing: float = 10.0) -> list[Report]:
    """Write STL (one per part), a single 3MF plate with every part, a PNG preview
    and a text report. `parts` is a Manifold or a dict {"name": Manifold}.

    A value may itself be a dict {"color": Manifold} (an assembly, e.g. one multi-color
    badge): its members keep their positions relative to each other and are written as
    <part>_<color>.stl in a shared frame, so importing them together in Bambu Studio
    ("load as one object with multiple parts") lines the colors up."""
    if isinstance(parts, Manifold):
        parts = {name: parts}
    os.makedirs(out_dir, exist_ok=True)
    reports = []
    scene = trimesh.Scene()
    x_cursor = 0.0
    laid_out = {}
    for pname, p in parts.items():
        members = p if isinstance(p, dict) else None
        whole = union(*members.values()) if members else p
        lo, hi = _bounds(whole)
        shift = [-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]]   # same as on_bed()
        whole = whole.translate(shift)
        reports.append(check(whole, pname, printer))
        to_trimesh(whole).export(os.path.join(out_dir, f"{pname}.stl"))
        lo, hi = _bounds(whole)
        dx = x_cursor - lo[0]
        x_cursor += (hi[0] - lo[0]) + spacing
        laid_out[pname] = whole.translate([dx, 0, 0])
        if members:
            for mname, m in members.items():
                m = m.translate(shift)
                to_trimesh(m).export(os.path.join(out_dir, f"{pname}_{mname}.stl"))
                node = f"{pname}_{mname}"
                scene.add_geometry(to_trimesh(m.translate([dx, 0, 0])), node_name=node, geom_name=node)
        else:
            scene.add_geometry(to_trimesh(laid_out[pname]), node_name=pname, geom_name=pname)
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
    with open(os.path.join(out_dir, f"{name}_report.json"), "w") as f:
        json.dump({"name": name, "printer": printer, "built_at": time.time(),
                   "bed": PRINTERS[printer],
                   "parts": [dict(asdict(r), size=[round(float(v), 2) for v in r.size],
                                  volume_cm3=round(float(r.volume_cm3), 2),
                                  grams_pla=round(float(r.grams_pla), 1),
                                  watertight=bool(r.watertight), stl=f"{r.name}.stl")
                             for r in reports]}, f, indent=2)
    print(text)
    print(f"\nwrote {out_dir}/{name}.3mf (open this in Bambu Studio), STLs, and {name}.png")
    return reports
