# Exports

This directory is split into two kinds of output.

## Tracked JSON Samples

These files are renderer-facing sample exports and are safe to share:

```text
f2_pd.json
jacobsite.json
mg2v2o7.json
water.json
```

They are generated with `tools/export_analysis_json.py` from files under `examples/`.

## Local Visual Checks

`exports/checks/` contains generated GIFs, screenshots, and temporary JSON used for visual inspection.

```text
exports/checks/current/          current Jacobsite/Mg2V2O7 checks
exports/checks/lattice_systems/  lattice-system sample GIFs
exports/checks/old/              older visual checks kept for comparison
```

`exports/checks/` is intentionally ignored by Git.
