# Project Specification

This is the current working specification for the Crystal Symmetry Viewer project.

## Purpose

The goal is to build a structure viewer that helps users understand crystal and molecular symmetry in 3D, and later use that viewer as the base for a symmetry puzzle.

The project must keep these priorities in order:

1. Reliable structure and symmetry analysis.
2. Renderer-friendly shared data.
3. Clear 3D visualization of structures, symmetry elements, and symmetry operations.
4. Educational animation of symmetry operations.
5. GUI and puzzle interactions after the data and viewer behavior are stable.

The project should not jump directly to puzzle UI before the viewer and animation model are dependable.

## Current Scope

The active implementation is a staged rebuild:

```text
analysis
  -> RenderData
  -> AtomMapping
  -> JSON export
  -> PyVista viewer
  -> browser control panel
  -> operation animation
  -> future renderer-independent game logic
```

The previous GUI/VTK attempt is archived in `archive/old_gui_attempt/` and should not be used as the base for new work unless explicitly requested.

## Active Code

```text
crystal_viewer/analysis_models.py
crystal_viewer/structure_analysis.py
crystal_viewer/molecule_analysis.py
crystal_viewer/render_data.py
crystal_viewer/atom_mapping.py
crystal_viewer/json_export.py
tools/analyze_structure.py
tools/analyze_molecule.py
tools/inspect_render_data.py
tools/inspect_atom_mapping.py
tools/export_analysis_json.py
tools/view_json_pyvista.py
tools/view_json_server.py
```

## Data Model

The viewer should consume `RenderData` and `AtomMapping`, not raw CIF parser objects.

- Crystal analysis uses fractional coordinates internally, then converts to Cartesian coordinates for rendering.
- Molecular analysis uses Cartesian coordinates directly.
- `RenderData` carries atoms, unit cell geometry, symmetry operations, axes, planes, centers, and asymmetric-unit source information.
- `AtomMapping` records source-to-target atom correspondences for each symmetry operation.
- JSON export is the boundary between analysis and display prototypes.

JSON details, viewer usage, and animation rules are documented in `docs/VIEWER_GUIDE.md`.

## Symmetry Operation Animation

Animations should show the chosen symmetry operation, not merely move atoms in straight lines to mapped targets.

Primitive animation rules:

```text
rotation:       arc around the selected axis
inversion:      interpolation through the selected center
mirror:         interpolation through the selected plane
translation:    linear movement
screw:          rotation phase, then shared translation phase
glide:          mirror phase, then shared translation phase
rotoinversion:  rotation phase, then inversion phase
rotoreflection: rotation phase, then mirror phase
```

Important constraints:

- When one operation has multiple equivalent axes or planes, the animation and displayed symmetry element must use one compatible selected element.
- Periodic display clones must be evaluated from their own displayed start positions so they follow the same selected axis, plane, or center.
- Atom mapping is used for correspondence and validation, but the visual path should be generated from the symmetry operation primitives.
- Compound operations should not be represented as a single straight-line move unless a geometric fallback is unavoidable.

Animation details are documented in `docs/VIEWER_GUIDE.md`.

## Current Viewer

`tools/view_json_pyvista.py` is the small CLI/debug viewer. It reads exported JSON only and can:

- show atoms and unit cells,
- show symmetry axes, planes, and centers,
- list operations,
- print atom mappings,
- draw source-to-target displacement lines,
- animate selected operations,
- write GIFs and screenshots.

`tools/view_json_gui.py` is the first minimal native PyVista GUI. It also reads exported JSON only and can:

- open one exported JSON file from the command line,
- switch displayed symmetry elements by operation,
- play non-blocking operation animations,
- change playback speed,
- animate all atoms, one representative atom, or typed selected atom indices.

The first GUI intentionally avoids Qt/PyVistaQt. WSL/X11 showed `BadWindow` failures when VTK was embedded in Qt, so the stable prototype uses PyVista's native slider and keyboard widgets.
For responsiveness, it defaults to source atoms only and offers `--expanded` for the half-cell periodic clone display used in visual checks.
The expanded GUI display uses a quarter-cell margin rather than the wider half-cell margin used by earlier checks.

`tools/view_json_server.py` is the preferred interactive viewer. It can start from JSON, CIF, XYZ, or an empty state. CIF/XYZ inputs are analyzed and exported to JSON before the existing viewer path is loaded. The default is Web-only; `--with-pyvista` explicitly opens the retained comparison renderer and enables legacy GIF output.

It is now a thin entry point plus stdlib HTTP API. Shared viewer responsibilities live under `crystal_viewer/viewer/`:

```text
browser_ui.py          compatibility wrapper for older imports
custom_operation.py    custom operation construction and symmetry checking
operation_labels.py    symbols, directions, fractional labels, and view targets
pyvista_controller.py  PyVista state, camera control, animation, and GIF saving
```

Browser-facing UI assets live under `crystal_viewer/web/`:

```text
browser_ui.py          compatibility loader and structure-kind config injection
browser_ui.html        browser control panel DOM
browser_ui.css         browser control panel styles
browser_ui.js          browser controls and API interaction
three_loader.js        Three.js dependency bootstrap
three_view.js          Three.js scene, camera, picking, and animation
animation_path.js      Cartesian animation-path evaluation
```

This split is intentionally coarse: it keeps the current JSON viewer stable while making future CIF loading and molecule-specific controls easier to add without turning the server entry point into the single core file. The browser UI supports structure import, operation filtering/selection, operation sorting, direction filtering, atom visibility controls, color controls, Play, Stop, Reset, GIF saving, and custom operation checks. Operation rows stay compact: operation symbol plus representative axis `[uvw]`, plane normal `(hkl)`, and center/point fractional coordinates.

Viewer usage is documented in `docs/VIEWER_GUIDE.md`.

## Intentional Differences From The Original Final Spec

The archived final spec expected a PyVistaQt GUI. The current implementation restarted GUI work from a small JSON-only viewer because the first GUI attempt was unstable.

Known intentional differences:

```text
The first GUI is native PyVista and JSON-only for now.
The browser-controlled viewer can accept CIF, XYZ, JSON, or local paths on the CLI or through browser controls, then auto-export JSON before opening it.
Mouse-based selected atom interaction is not implemented yet.
Puzzle UI is not implemented yet.
Molecular analysis is already implemented, although early crystal-only specs deferred it.
```

These differences do not change the project goal. They are staging choices to keep the data and animation behavior reliable before building UI.

## Known Non-Blocking Issues

```text
crystal analysis uses the vendored legacy core at crystal_viewer/legacy/symmetry_core.py
and can be overridden with SYMMETRY_VIEW_LEGACY_CORE when needed
mixed-occupancy crystal sites are represented by their highest-occupancy element for now
docs/archive files and old review notes mention earlier file names and should be treated as history
```

## Validation Samples

Representative input data:

```text
examples/cif/
examples/molecules/
```

Generated JSON samples:

```text
exports/json/halite.json
exports/json/sio2.json
exports/json/water.json
```

Regenerate the tracked JSON samples and browser catalog from the canonical inputs:

```bash
.venv/bin/python tools/regenerate_example_assets.py --clean
```

Local GIF/PNG checks live under `exports/gifs/<structure>/` and are intentionally not tracked.

## Archive

Original design discussions and older specs are kept in `docs/archive/`. They are historical context, not the current implementation target. When there is a conflict, this `PROJECT_SPEC.md` and the active code take precedence.
