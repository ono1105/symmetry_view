# Current Status

## Active Code

Active implementation is intentionally limited to analysis, render-data conversion, JSON export, and a small JSON-only PyVista viewer.

- `crystal_viewer/analysis_models.py`
- `crystal_viewer/structure_analysis.py`
- `crystal_viewer/molecule_analysis.py`
- `crystal_viewer/render_data.py`
- `crystal_viewer/atom_mapping.py`
- `crystal_viewer/json_export.py`
- `tools/*.py`

## Archived Code

The previous GUI/VTK attempt is archived in:

```text
archive/old_gui_attempt/
```

Do not use it as the basis for new work unless explicitly requested. It was kept only as reference for ideas and failures.

## Current Animation Prototype

The first animation prototype is implemented in the JSON viewer.

`AtomMapping`, JSON export, and a minimal JSON PyVista viewer are now implemented. The viewer can list operations, filter symmetry elements by operation, print atom mappings, draw source-to-target displacement lines, and animate a selected operation.

The animation uses operation primitives:

```text
rotation:
  arc around an axis
inversion:
  through the inversion center
mirror:
  through the mirror plane
translation:
  linear movement
screw:
  rotation phase, then translation phase
glide:
  mirror phase, then translation phase
```

Compound operations should not be represented as a single straight-line move unless the required symmetry element is missing and the viewer must fall back.

Example:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/water.json --operation 0 --animate --animation-fps 6 --animation-output exports/water_op0_animation.gif
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --list-elements
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --element-index 0 --animate --animation-fps 6 --animation-output exports/f2_pd_op1_axis0.gif
```

Detailed design:

```text
docs/ANIMATION_DESIGN.md
```

Specification alignment before animation:

```text
docs/SPEC_ALIGNMENT.md
```

For external review, start with:

```text
docs/CLAUDE_HANDOFF.md
```
