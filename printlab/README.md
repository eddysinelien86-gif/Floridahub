# printlab: design anything for the Bambu Lab printer

A small code-CAD toolkit plus a Claude Code agent (`.claude/agents/print-designer.md`)
that designs printable parts from a plain-English description.

## Use the agent

In Claude Code, in this repo, just ask, e.g.:

> Use the print-designer agent to make a wall hook for a 20 mm broom handle.
> Make a lithophane of `printlab/inputs/beach.jpg`.
> Design a twisty planter with a drainage hole and a saucer.
> Turn my logo into a cookie cutter.

It can do functional parts, text and signs, vases and other turned shapes, logos traced from images,
lithophanes, organic shapes, edits to existing STL files, and Blender-driven sculpted
models when Blender is installed on the laptop. Put photos/logos/STLs in `printlab/inputs/`.

The agent writes `printlab/designs/<name>.py`, runs it, checks the preview and the
printability report, and tells you which file to open and the slicer settings to use.

## Put it on your desktop

```bash
python3 printlab/install_app.py          # desktop icon + app list (Windows, Mac, Linux)
python3 printlab/install_app.py --remove # take it off again
```

Clicking **Print Lab** starts the dashboard in the background and opens it in its own
window (Chrome, Edge or Brave app window when installed; otherwise your browser).

## In the Claude app

Print Lab is also a page in the Claude app (pinned in the sidebar):
https://claude.ai/artifact/42a1qV1z2pxKmgcigyMmbM. It shows every design in 3D, with
its checks and sizes, and downloads a .zip (3MF + STLs) for Bambu Studio. It's a
snapshot and can't rebuild. To add new designs to it, run
`python3 printlab/export_gallery.py`, then ask Claude to republish `printlab/gallery.html`
with the files in `printlab/out/gallery/` to that link.

## Dashboard (laptop + TV)

```bash
pip install -r printlab/requirements.txt
python3 printlab/dashboard.py
```

This opens **http://localhost:8765** in your browser. Drag the window to the TV and press **F11**
for full screen. You get:

- every design, with a 3D view you can spin, shown as it will sit on the print bed;
- size boxes for each parameter. **Save & rebuild** writes the new numbers into the design file and regenerates it;
- the printer picker (P1S, X1C, A1, A1 mini, H2D…), which re-checks the fit against that bed;
- printability checks, filament estimate, downloads, and **Open in Bambu Studio**;
- auto-refresh: when the agent adds or changes a design, it appears within 5 seconds.

`--lan` lets a phone or a smart-TV browser on your Wi-Fi view it. Building and opening
files only works from the laptop itself. The 3D view loads three.js from the jsDelivr
CDN; offline it shows the preview image instead.

## Run a design yourself

```bash
pip install -r printlab/requirements.txt
cd printlab
python3 designs/storage_box.py
```

Outputs in `printlab/out/`:

| file | what it's for |
|---|---|
| `<name>.3mf` | open in **Bambu Studio**: every part already laid out on one plate |
| `<part>.stl` | one per part, also importable in Blender (File → Import → STL) |
| `<name>.png` | quick preview |
| `<name>_report.txt` | size, filament estimate, fits-the-bed, overhang and bed-contact warnings |

Change the UPPERCASE parameters at the top of a design file and run it again to resize.
Set `BAMBU_PRINTER=A1mini` (or X1C, P1S, A1, H2D…) to check against a different bed.
