# Specification Alignment Check

This document records the current alignment with `docs/specs/codex_final_spec_crystal_symmetry_viewer.md` before implementing animation.

## Current Scope

The active project intentionally uses a staged rebuild:

```text
analysis
  -> RenderData
  -> AtomMapping
  -> JSON export
  -> minimal JSON-only PyVista viewer
```

The final specification expects a PyVistaQt GUI, but the current prototype keeps GUI work deferred because the previous GUI attempt was unstable.

## Aligned

The current implementation matches the specification in the data areas that matter before animation:

```text
CIF loading through pymatgen
spglib W, t extraction
operation classification
axis / plane / center data with operation indices
crystal fractional analysis converted to Cartesian RenderData
plane normals computed from Cartesian basis vectors
unit cell vertices and edges from lattice rows
atom mapping per operation
nearest periodic image selection for crystal animation
JSON schema carrying RenderData + AtomMapping
operation angle exposed as angle_deg for future arc interpolation
```

The optimized `choose_nearest_periodic_image` still checks exactly the 27 shifts in `[-1, 0, 1]^3`, matching the specification.

## Intentional Differences

These are known and intentional at this stage:

```text
PyVistaQt GUI is not active yet.
Open CIF / Analyze Symmetry buttons are not implemented yet.
Selected atoms mode is not implemented yet.
Animation playback exists in the JSON viewer, but not yet in a PyVistaQt GUI.
Puzzle UI is not implemented yet.
Molecular analysis is implemented even though the original final spec listed it as deferred.
```

The molecular analysis addition does not conflict with the spec because the shared RenderData/AtomMapping design keeps molecule and crystal rendering paths unified.

## Known Non-Blocking Issues

```text
screw operation labels can still appear as 2_?
crystal analysis still depends on /home/ken/work/kouzoukaiseki/symmetry_core.py
```

Both are already documented in `docs/REVIEW_NOTES.md` and do not block animation logic, because animation uses `kind`, `order`, `angle_deg`, `operation_indices`, and `AtomMapping`.

## Animation Status

The JSON viewer animation follows `docs/ANIMATION_DESIGN.md`:

```text
--animate requires --operation
rotation/screw operations use arc interpolation
mirror/inversion/glide/translation/fallback use linear interpolation
crystal targets use transformed_cart from the nearest periodic animation image
```

Compound operations are represented as compositions of primitive motions where possible:

```text
screw = rotation then translation
glide = mirror then translation
rotoinversion = rotation then inversion
rotoreflection/improper = rotation then mirror
```

This keeps the prototype aligned with Section 16 of the final specification while preserving the current JSON-only, non-GUI architecture.
