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

The previous GUI/VTK attempt was deleted once the rebuild it was kept for finished; recover it from git history (`git show e625e0f:archive/old_gui_attempt/viewer.py`) if it is ever wanted again.

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
colors.js              shared colour constants for three_view.js and puzzle.js
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

## Bundled Examples

The bundled structures are chosen as teaching material: familiar substances with
small cells, whose symmetry is worth watching move. `examples/cif/` holds 15
crystals and `examples/molecules/` 21 molecules, listed in the README of each
directory. Everything but `Halite.cif` and `BaTiO3.cif` is generated from
published space groups, lattice constants and Wyckoff positions by
`tools/generate_example_structures.py`, so the data and its sources live in code.

The original example set — one real structure per crystal class, including
128-atom cells and unfamiliar minerals — was retired to `tests/fixtures/cif/`.
It is no longer offered to users but is still analysed by
`tests/test_fixture_cif_coverage.py`, which is what keeps all 32 crystal classes
covered.

Two of the molecules are icosahedral clusters — the building block of an
icosahedral quasicrystal, not a quasicrystal. A quasicrystal has no translational
periodicity, so it has neither a unit cell nor a space group and cannot go down
the crystal path at all: `structure_to_spglib_cell` requires a lattice, and
spglib answers with *some* space group whatever it is given (an icosahedron in a
cubic box reports `Pm-3`; tilted, `P-1`). A finite cluster has no such problem,
and the molecule path reads its 5-fold axes correctly, so that is where they go.

Which structures a quiz offers is data, not code. `regenerate_example_assets.py`
runs the four question generators over each export and records the counts in
`examples/example_catalog.json`; the picker offers a structure only where its
count is non-zero. This is why the mapping quiz shows only molecules and the
hard operation quiz only crystals — molecules have no screws or glides, crystals
no atom-mapping questions — and why water never appears under the composition
quiz to announce that it has no questions.

The same catalog carries `beyond_quiz_vocabulary` for the other half of that
question. The answer vocabulary is closed at folds 2/3/4/6 (plus ∞ for linear
molecules), so a structure with a 5-fold axis is withdrawn from every quiz even
though it still has plenty of C2/C3 questions — asking only those would teach
that its 5-fold axes are not there. Both fields are computed by
`crystal_viewer/game/catalog.py` from the quizzes' own logic, so adding or
removing a structure never means editing the client.

```text
examples/cif/           15 teaching crystals
examples/molecules/     19 teaching molecules
examples/example_catalog.json   generated: formula, symmetry, question counts
exports/json/           generated: one export per bundled example
tests/fixtures/cif/     30 retired crystal-class CIFs (not user-visible)
tests/fixtures/json/    exports of the five fixtures tests read
```

Regenerate the tracked JSON samples and browser catalog from the canonical inputs:

```bash
.venv/bin/python tools/generate_example_structures.py   # rewrite the generated inputs
.venv/bin/python tools/regenerate_example_assets.py --clean
```

Local GIF/PNG checks live under `exports/gifs/<structure>/` and are intentionally not tracked.

## Archive

Original design discussions and older specs are kept in `docs/archive/`. They are historical context, not the current implementation target. When there is a conflict, this `PROJECT_SPEC.md` and the active code take precedence.
