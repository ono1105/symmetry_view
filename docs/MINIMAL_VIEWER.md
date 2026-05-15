# Minimal JSON PyVista Viewer

`tools/view_json_pyvista.py` is a small display prototype.

It reads exported JSON only. It does not run crystal or molecule analysis.

## Commands

Show all render elements:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json
.venv/bin/python tools/view_json_pyvista.py exports/water.json
```

List operations:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --list-operations
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json --list-operations
```

List symmetry elements for one operation:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --list-elements
```

Show elements related to one operation:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --element-index 2
```

Show atom mapping and source-to-target displacement lines for one operation:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/water.json --operation 0 --show-mapping --show-displacements
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --show-mapping --show-displacements
```

Animate one operation:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/water.json --operation 0 --animate
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --element-index 0 --animate --animation-scope representative --animation-fps 6 --animation-output exports/checks/f2_pd_op1_rep.gif
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --element-index 0 --animate --animation-scope all --representative-atom 0 --animation-fps 6 --animation-output exports/checks/f2_pd_op1_all.gif
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json --operation 1 --element-index 0 --animate --animation-fps 6 --animation-output exports/checks/jacobsite_op1_screw4.gif
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json --operation 26 --element-index 0 --animate --animation-fps 6 --animation-output exports/checks/jacobsite_op26_glide.gif
```

Render a screenshot and exit:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/water.json --screenshot exports/checks/water_view.png
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --screenshot exports/checks/f2_pd_op1_view.png
```

`exports/` 直下は共有用のJSON本体、`exports/checks/` はローカル確認用のGIF/PNG置き場です。

`--animation-scope representative` animates one representative atom only. `--animation-scope all` animates every atom, but the crystal periodic image is chosen once from the representative atom and then applied to all atoms as the same integer lattice shift. Use `--representative-atom N` when a specific atom should define that shared movement.

For crystal JSON, the viewer shows periodic display images in a half-cell expanded fractional window `[-0.5, 1.5]`. These images are display clones only; animation paths are still computed once per source atom and copied with a constant lattice shift.

## Jacobsite Check Notes

`Jacobsite.cif` is a broader crystal symmetry sample:

```text
space group: 227 Fd-3m
operations: 192
representative operations checked:
  op 1  screw_4
  op 4  rotation_2
  op 24 inversion
  op 25 rotoinversion_or_improper_4
  op 26 glide
  op 31 mirror
```

For `op 25`, current RenderData exposes centers but no rotation axis, so the viewer falls back to an inversion-style phase instead of a full rotation-plus-inversion animation. Full rotoinversion animation will need axis extraction from the operation matrix or richer element export.

## Scope

Implemented:

```text
atoms
unit cell
axes
planes
centers
operation-based element filtering
operation list
operation element list
atom mapping printout
source-to-target displacement lines
operation animation
screenshots
```

Not implemented yet:

```text
GUI controls
atom selection
puzzle interactions
```

This viewer is intentionally separate from analysis code. It should consume only exported JSON.
