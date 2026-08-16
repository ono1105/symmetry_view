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

`--clean` deletes every top-level JSON here first, so exports of anything that is
no longer a bundled example disappear with it. The retired crystal-class CIFs
keep their exports under `tests/fixtures/json/` instead; see
`tests/fixtures/README.md` for the command that refreshes those.
