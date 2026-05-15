# Minimal JSON PyVista Viewer

`tools/view_json_pyvista.py` is a small display prototype.

It reads exported JSON only. It does not run crystal or molecule analysis.

## Commands

Show all render elements:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json
.venv/bin/python tools/view_json_pyvista.py exports/water.json
```

List operations:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --list-operations
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
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --element-index 0 --animate --animation-fps 6 --animation-output exports/f2_pd_op1_axis0_slow.gif
```

Render a screenshot and exit:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/water.json --screenshot exports/water_view.png
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --screenshot exports/f2_pd_op1_view.png
```

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
