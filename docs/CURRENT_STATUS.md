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

## Next Recommended Step

Add the first animation prototype on top of the JSON viewer.

`AtomMapping`, JSON export, and a minimal JSON PyVista viewer are now implemented. The viewer can list operations, filter symmetry elements by operation, print atom mappings, and draw source-to-target displacement lines.

The next useful step is an operation-aware animation prototype:

```text
selected operation
  + RenderOperationData.angle_deg
  + matching RenderAxisData when needed
  + AtomMappingEntry.transformed_cart
  -> interpolate atom positions
  -> play in the PyVista window or save a short GIF
```

Use an operation-aware dispatcher from the start. Linear interpolation is acceptable only as a short debugging fallback; rotation and screw operations should move along arcs to match the specification.

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
