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
.venv/bin/python tools/export_analysis_json.py 'F2 Pd.cif' --mode crystal -o exports/f2_pd.json
```

Molecule:

```bash
.venv/bin/python tools/export_analysis_json.py examples/water.xyz --mode molecule -o exports/water.json
```

Stdout export is also supported:

```bash
.venv/bin/python tools/export_analysis_json.py examples/water.xyz --mode molecule
```

## Top-Level Shape

```json
{
  "schema_version": 1,
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
operations
axes
planes
centers
unit_cell
bounds_min
bounds_max
```

All geometry in `render_data` is Cartesian. For crystals, fractional geometry is converted before export.

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
.venv/bin/python -m json.tool exports/f2_pd.json /tmp/f2_pd_checked.json
.venv/bin/python -m json.tool exports/water.json /tmp/water_checked.json
```

