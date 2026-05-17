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
  -> minimal JSON-only PyVista viewer
  -> operation animation prototype
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
```

## Data Model

The viewer should consume `RenderData` and `AtomMapping`, not raw CIF parser objects.

- Crystal analysis uses fractional coordinates internally, then converts to Cartesian coordinates for rendering.
- Molecular analysis uses Cartesian coordinates directly.
- `RenderData` carries atoms, unit cell geometry, symmetry operations, axes, planes, centers, and asymmetric-unit source information.
- `AtomMapping` records source-to-target atom correspondences for each symmetry operation.
- JSON export is the boundary between analysis and display prototypes.

JSON details are documented in `docs/JSON_EXPORT.md`.

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

Animation details are documented in `docs/ANIMATION_DESIGN.md`.

## Current Viewer

`tools/view_json_pyvista.py` is the current viewer prototype. It reads exported JSON only and can:

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

`tools/view_json_server.py` is the preferred prototype for list-based controls. It starts a local stdlib HTTP server for browser operation/atom lists and uses the main Python thread for PyVista rendering. The browser UI supports operation filtering/selection, operation sorting, direction filtering, atom checkbox selection, Play, Stop, and Reset. Operation rows stay compact: operation symbol plus representative axis `[uvw]`, plane normal `(hkl)`, and center/point fractional coordinates.

Viewer usage is documented in `docs/MINIMAL_VIEWER.md`.

## Intentional Differences From The Original Final Spec

The archived final spec expected a PyVistaQt GUI. The current implementation restarted GUI work from a small JSON-only viewer because the first GUI attempt was unstable.

Known intentional differences:

```text
The first GUI is native PyVista and JSON-only for now.
Open CIF / Analyze Symmetry buttons are not implemented yet.
Mouse-based selected atom interaction is not implemented yet.
Puzzle UI is not implemented yet.
Molecular analysis is already implemented, although early crystal-only specs deferred it.
```

These differences do not change the project goal. They are staging choices to keep the data and animation behavior reliable before building UI.

## Known Non-Blocking Issues

```text
screw operation labels can still appear as 2_?
crystal analysis still depends on /home/ken/work/kouzoukaiseki/symmetry_core.py
mixed-occupancy crystal sites are represented by their highest-occupancy element for now
```

## Validation Samples

Representative input data:

```text
examples/structures/
examples/cif/
examples/water.xyz
examples/methane.xyz
```

Generated JSON samples:

```text
exports/json/f2_pd.json
exports/json/jacobsite.json
exports/json/mg2v2o7.json
exports/json/water.json
```

Local GIF/PNG checks live under `exports/gifs/<structure>/` and are intentionally not tracked.

## Archive

Original design discussions and older specs are kept in `docs/archive/`. They are historical context, not the current implementation target. When there is a conflict, this `PROJECT_SPEC.md` and the active code take precedence.
