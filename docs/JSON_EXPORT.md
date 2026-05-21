# JSON Export

`tools/export_analysis_json.py` exports the current analysis state in a renderer-friendly format.

The JSON contains:

```text
schema_version
source_kind
render_data
atom_mappings
```

## Commands

Crystal:

```bash
.venv/bin/python tools/export_analysis_json.py examples/structures/f2_pd.cif --mode crystal -o exports/json/f2_pd.json
```

Molecule:

```bash
.venv/bin/python tools/export_analysis_json.py examples/molecules/water.xyz --mode molecule -o exports/json/water.json
```

Stdout export is also supported:

```bash
.venv/bin/python tools/export_analysis_json.py examples/molecules/water.xyz --mode molecule
```

## Top-Level Shape

```json
{
  "schema_version": 4,
  "source_kind": "crystal",
  "render_data": {},
  "atom_mappings": {}
}
```

## `render_data`

`render_data` is the common representation for future display layers.

It contains:

```text
metadata
atoms
asymmetric_atoms
operations
axes
planes
centers
unit_cell
bounds_min
bounds_max
```

All geometry in `render_data` is Cartesian. For crystals, fractional geometry is converted before export.

For crystal exports, `asymmetric_atoms` stores the atom sites written directly in the CIF asymmetric unit. `atoms` stores the expanded structure used for display, mapping, and animation. Each expanded atom has:

```text
asymmetric_index
generation_operation_index
```

This records which CIF atom site and which space-group operation generated the expanded atom.

Each render operation contains:

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

`angle_deg` is included for operation-aware animation. `matrix_cart` and `translation_cart` let the viewer animate the actual symmetry operation instead of reconstructing it only from atom mappings. For crystal exports, `matrix_frac` and `translation_frac` store the original fractional operation.

## `atom_mappings`

`atom_mappings` stores how each symmetry operation maps atoms.

Each operation mapping contains:

```text
operation_index
operation_kind
complete
atom_to_atom
entries
```

For crystal mappings, each entry may also contain:

```text
transformed_frac
wrapped_frac
animation_frac
```

`animation_frac` is the nearest periodic image selected for smooth animation.
`transformed_cart` is computed from that animation image for crystals.

For molecule mappings, `transformed_cart` is the raw transformed Cartesian coordinate.

## Validation

```bash
.venv/bin/python -m json.tool exports/json/f2_pd.json /tmp/f2_pd_checked.json
.venv/bin/python -m json.tool exports/json/water.json /tmp/water_checked.json
.venv/bin/python -m json.tool exports/json/jacobsite.json /tmp/jacobsite_checked.json
```
