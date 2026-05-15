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
matrix_frac
translation_frac
matrix_cart
translation_cart
```

`angle_deg` is required for operation-aware rotation and screw animation. `matrix_cart` and `translation_cart` are required once animation needs to follow the actual operation exactly, especially for rotoinversion and other improper operations. JSON exports that contain operation matrices use `schema_version = 3`.

## CLI Scope

Add these options to `tools/view_json_pyvista.py`:

```bash
--animate
--animation-frames N
--animation-fps FPS
--animation-output PATH
--animation-scope all|representative
--representative-atom INDEX
--list-elements
--element-index N
```

Required usage:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/water.json --operation 0 --animate
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --list-elements
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --element-index 0 --animate --animation-scope representative --animation-fps 6 --animation-output exports/checks/f2_pd_op1_rep.gif
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --element-index 0 --animate --animation-scope all --representative-atom 0 --animation-fps 6 --animation-output exports/checks/f2_pd_op1_all.gif
```

`--animate` requires `--operation`, because atom targets are operation-specific.
`--element-index` selects one matching axis/plane/center for the operation. During animation, only that selected element is displayed and used for the motion path. This matters when one operation has multiple equivalent screw axes.
`--animation-scope representative` animates only the representative source atom. `--animation-scope all` animates all atoms, using the representative atom to choose one periodic image shift for the whole operation.

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

The periodic image must be chosen per operation, not independently per atom. The viewer first chooses a representative atom target that is consistent with the selected axis/plane/center, converts that choice to one integer lattice shift, and applies the same shift to every atom:

```text
representative target = W*x_ref + t + shared_integer_shift
all atom targets      = W*x_i   + t + shared_integer_shift
```

This keeps the all-atom animation visually tied to one symmetry operation instead of mixing equivalent periodic images atom by atom.

When `matrix_cart` is present, final animation targets are computed from the operation affine transform plus the shared crystal lattice shift. Atom mappings are still used to choose the representative atom and validate correspondence, but they are no longer the only source of motion geometry.

## Periodic Display Images

Crystal data distinguishes three concepts:

```text
AsymmetricUnitAtom: atom sites written directly in the CIF
ExpandedAtom: atoms generated from the asymmetric unit by space-group operations
DisplayClone: lattice-translation copies used only for viewing across boundaries
```

Animation paths are computed for `ExpandedAtom` entries. This is deliberately more conservative than computing only for asymmetric-unit atoms, because non-translation space-group operations do not generally commute with the animated operation.

Only `DisplayClone` entries reuse the exact same path as their source atom.

For crystal viewing, the atom display should include periodic images in the fractional window:

```text
[-0.5, 1.5] along a, b, and c
```

This is a display-only expansion. It prevents atoms on cell boundaries from looking isolated or uniquely fixed when their equivalent periodic images are just outside the drawn unit cell.

Animation paths are still computed once per source atom. Each periodic display image reuses the source atom path plus a constant lattice shift:

```text
display_pos_i(s) = source_path_i(s) + lattice_shift
```

Do not duplicate AtomMapping or operation-path calculations for these display images.

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
.venv/bin/python tools/export_analysis_json.py examples/structures/f2_pd.cif --mode crystal -o exports/f2_pd.json
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
wrapping final crystal positions back into the unit cell
high-quality operation labels for screw axes
puzzle interactions
```
