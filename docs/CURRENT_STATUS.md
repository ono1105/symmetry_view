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

Add the first simple animation prototype on top of the JSON viewer.

`AtomMapping`, JSON export, and a minimal JSON PyVista viewer are now implemented. The viewer can list operations, filter symmetry elements by operation, print atom mappings, and draw source-to-target displacement lines.

The next useful step is a conservative animation prototype:

```text
selected operation + AtomMappingEntry.transformed_cart
  -> interpolate atom positions
  -> save a short GIF/MP4 or play in the PyVista window
```

Start with linear interpolation for debugging. After that works, add operation-aware motion such as rotation around an axis or reflection through a plane.

For external review, start with:

```text
docs/CLAUDE_HANDOFF.md
```
