# Exports

Generated viewer data and local animation outputs are separated here.

```text
exports/
  json/              JSON payloads for the viewers
  gifs/              local GIF outputs, grouped by structure name
    <structure>/
      <structure>_opNNN_<scope>_<timestamp>.gif
```

The browser viewer saves GIFs automatically under `exports/gifs/<structure>/`.
GIF and PNG outputs are local check artifacts and are ignored by Git.
