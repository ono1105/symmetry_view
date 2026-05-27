# Exports

Generated viewer data and local animation outputs are separated here.

```text
exports/
  json/              JSON payloads regenerated from examples/cif and examples/molecules
  gifs/              local GIF outputs, grouped by structure name
    <structure>/
      <structure>_opNNN_<scope>_<timestamp>.gif
```

The browser viewer saves GIFs automatically under `exports/gifs/<structure>/`.
GIF and PNG outputs are local check artifacts and are ignored by Git.

Regenerate tracked JSON exports and `examples/example_catalog.json` with:

```bash
.venv/bin/python tools/regenerate_example_assets.py --clean
```
