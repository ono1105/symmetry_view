# Animation Design

This document defines the next implementation step after JSON export and the minimal JSON PyVista viewer.

## Goal

Add a small animation prototype on top of `tools/view_json_pyvista.py`.

The prototype should still consume exported JSON only. It should not call CIF or molecule analysis code directly.

## Inputs

Animation uses:

```text
render_data.atoms[].cart
render_data.operations[]
render_data.axes / planes / centers
atom_mappings.mappings[].entries[].transformed_cart
```

For crystals, `transformed_cart` is the nearest periodic animation image, computed from `animation_frac @ lattice`.
For molecules, `transformed_cart` is the raw transformed Cartesian coordinate.

For crystal animation, the viewer may choose a different periodic image from `transformed_frac + integer shifts` when a selected symmetry element requires it. This is important for screw/rotation/glide-style paths: the nearest periodic image can make each atom appear to use a different equivalent axis. Animation should prefer the periodic image that is consistent with the selected axis or plane.

## Operation Data

`RenderOperationData` includes:

```text
index
label
kind
order
angle_deg
symbol
```

`angle_deg` is required for operation-aware rotation and screw animation. It is already computed during analysis, then copied into RenderData and JSON. JSON exports that contain this field use `schema_version = 2`.

## CLI Scope

Add these options to `tools/view_json_pyvista.py`:

```bash
--animate
--animation-frames N
--animation-fps FPS
--animation-output PATH
--list-elements
--element-index N
```

Required usage:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/water.json --operation 0 --animate
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --list-elements
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --element-index 0 --animate --animation-fps 6 --animation-output exports/f2_pd_op1_axis0.gif
```

`--animate` requires `--operation`, because atom targets are operation-specific.
`--element-index` selects one matching axis/plane/center for the operation. During animation, only that selected element is displayed and used for the motion path. This matters when one operation has multiple equivalent screw axes.

## Interpolation Policy

Use an operation-aware dispatcher from the beginning:

```text
operation kind starts with rotation_ or screw_:
  arc interpolation around the selected operation axis

mirror, glide, inversion, translation, identity, fallback:
  linear interpolation from start_cart to the operation target image
```

Animation should be built from primitive motions rather than collapsing every operation into a single straight-line movement:

```text
rotation:
  rotate around the selected axis

inversion:
  move through the inversion center

mirror:
  move toward the reflected position through the mirror plane

translation:
  linear translation

screw:
  rotation phase, then translation phase

glide:
  mirror phase, then translation phase

rotoinversion:
  rotation phase, then inversion phase

rotoreflection / improper:
  rotation phase, then mirror phase
```

Compound operations should not be represented as a single straight-line move unless the required symmetry element is missing from the exported JSON and the viewer must fall back.

## Axis Lookup

For rotation and screw operations:

```text
operation index
  -> first RenderAxisData whose operation_indices contains the index
```

Use:

```text
axis.point_cart
axis.direction_cart
operation.angle_deg
```

There can be multiple equivalent axes for one operation in a periodic crystal. The first matching axis is acceptable for the first prototype, but crystal target images must be chosen to match that axis.

## Rotation Direction

`angle_deg` is an unsigned magnitude. The viewer should determine the sign per atom by comparing candidate rotations:

```text
candidate +angle
candidate -angle
choose the candidate closer to the operation target image
```

For screw operations, first implement:

```text
rotation phase + translation phase
```

That keeps the motion readable as a composition of basic operations and keeps the end frame exactly equal to the selected operation target image.

For crystals, the final animation target may be an equivalent periodic image rather than `transformed_cart` if that image better matches the selected screw axis. The atom mapping remains the same; only the displayed path image changes.

## Frame Calculation

For each frame parameter `s` in `[0, 1]`:

```text
start = atom.cart
target = selected operation target image

if operation uses arc and axis exists:
  pos = arc_path(start, target, axis, angle_deg, s)
else:
  pos = (1 - s) * start + s * target
```

Static atoms may be left in place.

## Verification

Minimum checks:

```bash
.venv/bin/python -m py_compile tools/view_json_pyvista.py crystal_viewer/render_data.py
.venv/bin/python tools/export_analysis_json.py examples/water.xyz --mode molecule -o exports/water.json
.venv/bin/python tools/export_analysis_json.py 'F2 Pd.cif' --mode crystal -o exports/f2_pd.json
.venv/bin/python tools/view_json_pyvista.py exports/water.json --list-operations
```

Visual checks:

```text
water operation 0:
  H atoms exchange positions via C2 motion

F2 Pd operation 1:
  atoms move toward nearest periodic screw-equivalent positions
```

## Deferred

```text
GUI controls
selected-atom-only animation
wrapping final crystal positions back into the unit cell
high-quality operation labels for screw axes
puzzle interactions
```
