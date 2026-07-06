# Viewer Guide

This document is the current reference for JSON export, viewer usage, browser controls, and symmetry-operation animation.

## Current Flow

The project keeps analysis, renderer data, viewer state, and future game logic separated:

```text
CIF / XYZ
  -> crystal or molecule analysis
  -> RenderData
  -> AtomMapping
  -> JSON export
  -> PyVista viewer + browser control panel
  -> future renderer-independent game logic
```

The viewer should consume exported JSON and `RenderData`-shaped state. It should not depend on raw CIF parser or pymatgen objects.

## JSON Export

`tools/export_analysis_json.py` exports renderer-friendly JSON.

```bash
.venv/bin/python tools/export_analysis_json.py examples/cif/Halite.cif --mode crystal -o exports/json/halite.json
.venv/bin/python tools/export_analysis_json.py examples/molecules/water.xyz --mode molecule -o exports/json/water.json
```

Current top-level shape:

```json
{
  "schema_version": 6,
  "source_kind": "crystal",
  "render_data": {},
  "atom_mappings": {}
}
```

`render_data.metadata` currently includes:

```text
mode
source_file
formula
symmetry_label
operation_count
point_group_label
lattice_parameters
space_group_generators
point_group_generators
warnings
```

Each operation contains:

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

For crystals, `asymmetric_atoms` stores CIF atom sites and expanded atoms carry:

```text
asymmetric_index
generation_operation_index
```

`atom_mappings` records source-to-target atom correspondences. It is used for correspondence and validation; animation paths should be generated from operation matrices plus selected axes, planes, or centers.

## Browser-Controlled Viewer

The preferred interactive prototype is:

```bash
.venv/bin/python tools/view_json_server.py exports/json/halite.json
```

Start empty and open structures from the browser:

```bash
.venv/bin/python tools/view_json_server.py --no-browser
```

Open a CIF or XYZ directly:

```bash
.venv/bin/python tools/view_json_server.py examples/cif/Halite.cif --no-browser
.venv/bin/python tools/view_json_server.py examples/molecules/water.xyz --no-browser
```

The browser panel talks to a local stdlib HTTP server. Three.js renders the 3D scene.
The server selects a free local port automatically. Use `--port 5173` only when
a fixed port is required.

Atom display defaults live in:

```text
crystal_viewer/viewer/atom_defaults.json
```

This JSON can override default atom colors, mesh style, and highlight radius scale. Invalid or missing values fall back to built-in defaults in `atom_style.py`.

Current browser controls include:

```text
open CIF / XYZ / JSON / local path
operation list and operation details
operation filtering and sorting
display range controls
atom visibility and element visibility
atom color controls
selected atom animation scope
play / stop / reset
camera controls and view center controls
PNG screenshots and animated GIF export
custom operation check and animation
```

The default server path is Web-only. Use `--with-pyvista` only for final
comparison of the retained renderer. `--web-only` remains accepted for command
compatibility. Standard, custom, and custom-sequence animations run in Three.js.
The Web viewer can save the current canvas as PNG or export the current animation
as an animated GIF.

`tools/view_json_server.py` should stay a thin entry point and HTTP API. Shared viewer code belongs under `crystal_viewer/viewer/`; browser-facing UI assets belong under `crystal_viewer/web/`.

### Browser rendering API

The browser renderer consumes these read-only endpoints:

```text
GET /api/render_data
GET /api/animation_path?operation_index=<index>
```

Animation path responses use their own `schema_version`, independently of the
analysis export schema. Version 1 declares `source_kind`,
`coordinate_space: "cartesian"`, and uses `angle_deg` for all public angles.
Python also supplies `animation_duration_seconds`. It normalizes the maximum
Cartesian path length by the displayed structure span, then clamps the normal
speed duration to 1.0–5.33 seconds. Three.js and PyVista apply the shared
Slow/Normal/Fast multiplier to that same base duration.
For crystals, `periodic_image_policy` is `"transform_with_source"`: a periodic
display image is evaluated from its displayed start position with the same
operation, rather than being held fixed or retaining a constant Cartesian
offset during a rotation. For molecules it is `"not_applicable"`.

Crystal and molecule responses share one schema. Consumers must branch on
`source_kind: "crystal" | "molecule"`, not infer the source from optional
fields. Crystal-only data such as `unit_cell`, fractional coordinates, and
periodic-image controls must be treated as nullable or unavailable for a
molecule. Atom Cartesian coordinates, symmetry operations, atom mappings, and
animation path types remain common to both modes.

The renderer-independent JavaScript reference interpolator is served from
`/static/animation_path.js`. Its path and boundary-wrap parity tests use the
same golden JSON as the Python reference implementation:

```bash
node --test tests/js/animation_path.test.mjs
```

The current browser page also contains a Three.js comparison view. It
renders Cartesian atom positions with `InstancedMesh`, renders a unit-cell line
frame only for crystal input, and supports orbit, zoom, pan, and projection
switching. Left-drag uses unrestricted trackball rotation, including roll,
rather than a camera orbit constrained to a fixed up-axis. Standard
operation animation uses `/api/animation_path` and the JavaScript reference
interpolator. The selected operation's Python-resolved axis, plane, and center
come from `/api/symmetry_elements` and are rendered alongside the animation.
For glide operations, the same response includes the Python-resolved Cartesian
glide translation used by the animation; a yellow arrow on the plane shows its
direction.
When playback starts, translucent yellow markers remain at each animated
display instance's starting position. `Displayed all` includes periodic images;
`Unit cell only` shows markers only for primary images. They persist after Stop
or completion and are removed by Reset, operation changes, or structure
changes.
Cell Range uses the same Python-generated display instances as PyVista.
`Displayed all` evaluates every periodic image from its displayed Cartesian
start position; `Unit cell only` moves primary images and leaves periodic
copies fixed. `Continuous` leaves evaluated Cartesian positions unchanged.
For `Wrap`, Python supplies the Cartesian-to-cell and cell-to-Cartesian
matrices and the origin convention, and JavaScript only applies that versioned
boundary contract. Molecules always use continuous behavior because they have
no unit cell. Left-click picking in Three.js selects the source atom and updates
the shared browser/PyVista state; Shift/Ctrl-click toggles multi-selection.
PyVista remains the reference renderer; custom-operation animation has not yet
moved to Three.js.

Install the pinned browser dependency after cloning or changing the lockfile:

```bash
cd crystal_viewer/web
npm ci
```

Restart `tools/view_json_server.py` after changing browser HTML or static asset
routes. The page HTML is loaded when Python imports `browser_ui.py`. CSS and
JavaScript files are read per request, so reloading the page picks up changes to
those files without restarting the server.

## CLI Viewers

The older JSON-only viewers remain useful for debugging.

```bash
.venv/bin/python tools/view_json_pyvista.py exports/json/halite.json --list-operations
.venv/bin/python tools/view_json_pyvista.py exports/json/halite.json --operation 1 --list-elements
.venv/bin/python tools/view_json_pyvista.py exports/json/halite.json --operation 1 --animate
.venv/bin/python tools/view_json_gui.py exports/json/halite.json
```

The native PyVista GUI avoids Qt/PyVistaQt because WSL/X11 had `BadWindow` failures when VTK was embedded in Qt.

## Animation Rules

Animations should show the selected symmetry operation, not just move atoms in straight lines to mapped targets.

Primitive rules:

```text
rotation:       arc around selected axis
inversion:      interpolation through selected center
mirror:         interpolation through selected plane
translation:    linear movement
screw:          rotation phase, then shared translation phase
glide:          mirror phase, then shared translation phase
rotoinversion:  rotation phase, then inversion phase
rotoreflection: rotation phase, then mirror phase
```

Important constraints:

- When one operation has multiple equivalent axes, planes, or centers, the displayed element and animation path must use one compatible selected element.
- Periodic display clones are display-only. They reuse source atom paths with appropriate shifts or evaluate the same operation from their displayed start positions, depending on the current animation path implementation.
- Crystal animation should choose one shared periodic image shift per operation, usually from a representative atom, rather than letting every atom pick a different equivalent image.
- `AtomMapping` is still used for correspondence and validation.

## Display And Performance Notes

The current PyVista viewer uses glyph-style atom meshes for large displayed ranges. This avoids creating one actor per atom and keeps range expansion and animation more responsive.

Key concepts:

```text
ExpandedAtom: atom generated by crystallographic symmetry operation
DisplayClone: lattice-translation copy used only for viewing
element batch: same-element displayed atom instances grouped for glyph rendering
```

Range-related behavior should be checked with `tools/inspect_atom_instances.py` before changing rendering internals.

## Future Game Architecture

Future puzzle logic should live in `crystal_viewer/game/` and consume renderer-independent data. It should not call PyVista, browser DOM APIs, or raw parser objects.

Recommended direction:

```text
1. Keep PyVista working as current renderer.
2. Add game rules in crystal_viewer/game/.
3. Add browser-integrated 3D code in crystal_viewer/web/.
4. Let game code emit renderer-neutral commands such as select/highlight/animate operation.
```

## Validation Commands

Focused checks:

```bash
.venv/bin/python -m py_compile crystal_viewer/render_data.py crystal_viewer/web/browser_ui.py tools/view_json_server.py
.venv/bin/python -m unittest tests/test_render_metadata.py tests/test_rhombohedral_cif_fallback.py
.venv/bin/python tools/inspect_atom_instances.py exports/json/halite.json --display-mode expanded_1_0 --glyph-preview
```

JSON validity:

```bash
.venv/bin/python -m json.tool exports/json/halite.json /tmp/halite_checked.json
```

Visual checks should still be done in the browser-controlled viewer for glyph rendering, animation, display range changes, and operation labels.
