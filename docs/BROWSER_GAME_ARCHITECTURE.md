# Browser/Game Architecture

This project keeps symmetry analysis separate from rendering and game logic.

## Package Roles

- `crystal_viewer/`
  - Core Python package.
  - Owns analysis, JSON export, render data, shared geometry, viewer helpers, web UI, and game logic.

- `crystal_viewer/web/`
  - Browser-facing UI assets and future browser-integrated rendering code.
  - `browser_ui.py` currently provides the control panel HTML.
  - Future three.js or browser-native 3D code should live here, not in `tools/`.

- `crystal_viewer/game/`
  - Renderer-independent game logic.
  - Challenges, scoring, hints, progression, and answer checking should use `render_data` and operation summaries.
  - This code must not depend on PyVista, browser DOM APIs, or a specific rendering engine.

- `crystal_viewer/viewer/`
  - Visualization implementations and shared viewer helpers.
  - PyVista-specific controllers stay here.
  - `viewer/browser_ui.py` is only a compatibility wrapper for older imports.

- `tools/`
  - Thin command-line entry points.
  - Scripts should delegate to `crystal_viewer` modules instead of owning core logic.

## Migration Direction

1. Keep PyVista working as the current renderer.
2. Add game rules in `crystal_viewer/game/`.
3. Add browser-integrated display code in `crystal_viewer/web/`.
4. Keep renderer calls thin: game code should emit "select/highlight/animate operation" style commands that PyVista or browser 3D can implement separately.
