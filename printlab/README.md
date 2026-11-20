# printlab — design parts for the Bambu Lab printer

A small code-CAD toolkit plus a Claude Code agent (`.claude/agents/print-designer.md`)
that designs printable parts from a plain-English description.

## Use the agent

In Claude Code, in this repo, just ask, e.g.:

> Use the print-designer agent to make a wall hook for a 20 mm broom handle.

The agent writes `printlab/designs/<name>.py`, runs it, checks the preview and the
printability report, and tells you which file to open and the slicer settings to use.

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
