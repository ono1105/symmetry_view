# Minimal JSON PyVista Viewer

`tools/view_json_pyvista.py` is a small command-line display prototype.
`tools/view_json_gui.py` is the first minimal native PyVista GUI around the same JSON data and animation functions.

Both read exported JSON only. They do not run crystal or molecule analysis.

## Commands

Show all render elements:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/json/f2_pd.json
.venv/bin/python tools/view_json_pyvista.py exports/json/jacobsite.json
.venv/bin/python tools/view_json_pyvista.py exports/json/water.json
```

List operations:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/json/f2_pd.json --list-operations
.venv/bin/python tools/view_json_pyvista.py exports/json/jacobsite.json --list-operations
```

List symmetry elements for one operation:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/json/f2_pd.json --operation 1 --list-elements
```

Show elements related to one operation:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/json/f2_pd.json --operation 1
.venv/bin/python tools/view_json_pyvista.py exports/json/f2_pd.json --operation 1 --element-index 2
```

Show atom mapping and source-to-target displacement lines for one operation:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/json/water.json --operation 0 --show-mapping --show-displacements
.venv/bin/python tools/view_json_pyvista.py exports/json/f2_pd.json --operation 1 --show-mapping --show-displacements
```

Animate one operation:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/json/water.json --operation 0 --animate
.venv/bin/python tools/view_json_pyvista.py exports/json/f2_pd.json --operation 1 --element-index 0 --animate --animation-scope representative --animation-fps 6 --animation-output exports/gifs/f2_pd/f2_pd_op1_rep.gif
.venv/bin/python tools/view_json_pyvista.py exports/json/f2_pd.json --operation 1 --element-index 0 --animate --animation-scope all --representative-atom 0 --animation-fps 6 --animation-output exports/gifs/f2_pd/f2_pd_op1_all.gif
.venv/bin/python tools/view_json_pyvista.py exports/json/jacobsite.json --operation 1 --element-index 0 --animate --animation-fps 6 --animation-output exports/gifs/jacobsite/jacobsite_op1_screw4.gif
.venv/bin/python tools/view_json_pyvista.py exports/json/jacobsite.json --operation 26 --element-index 0 --animate --animation-fps 6 --animation-output exports/gifs/jacobsite/jacobsite_op26_glide.gif
```

Use `--animation-speed` to change playback speed without changing the path:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/json/jacobsite.json --operation 31 --animate --animation-speed 0.5 --animation-output exports/gifs/jacobsite/jacobsite_op31_slow.gif
```

Use `--selected-atom` or `--selected-atoms` to animate only chosen source atoms while the rest of the structure remains visible:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/json/jacobsite.json --operation 25 --animate --selected-atom 0 --animation-output exports/gifs/jacobsite/jacobsite_op25_atom0.gif
.venv/bin/python tools/view_json_pyvista.py exports/json/jacobsite.json --operation 25 --animate --selected-atoms 0 3 8 --animation-output exports/gifs/jacobsite/jacobsite_op25_atoms.gif
```

Render a screenshot and exit:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/json/water.json --screenshot exports/gifs/water/water_view.png
.venv/bin/python tools/view_json_pyvista.py exports/json/f2_pd.json --operation 1 --screenshot exports/gifs/f2_pd/f2_pd_op1_view.png
```

Open the minimal GUI:

```bash
.venv/bin/python tools/view_json_gui.py exports/json/f2_pd.json
.venv/bin/python tools/view_json_gui.py exports/json/jacobsite.json
```

Open the browser-controlled viewer:

```bash
.venv/bin/python tools/view_json_server.py exports/json/jacobsite.json
```

If no input path is provided, the viewer starts from `exports/json/halite.json` when available:

```bash
.venv/bin/python tools/view_json_server.py --no-browser
```

This starts a local control panel at `http://127.0.0.1:5173/` and keeps PyVista responsible for the 3D view. The browser UI includes an operation list, operation filter, atom checkbox list, atom filter, Play, Stop, and Reset. Operation rows show the operation symbol plus the selected representative axis `[uvw]`, plane normal `(hkl)`, or center/point fractional coordinate.
The operation list can be sorted by operation number, operation symbol, full axis/plane/center entry, or direction only. It can also be filtered to one selected operation or one selected axis/plane direction.

The browser-controlled viewer can also take a CIF file directly. In that mode it first analyzes the CIF, writes a JSON export under `exports/json/`, then opens the generated JSON with the existing viewer path:

```bash
.venv/bin/python tools/view_json_server.py examples/structures/f2_pd.cif --no-browser
```

Use `--json-output path/to/file.json` to choose the generated JSON path, or `--json-dir exports/json` to choose the output directory.

After the browser-controlled viewer is running, the `Open CIF` control can load another local CIF file without restarting the server. The uploaded CIF is analyzed, exported under `exports/json/imported/` by default, and the PyVista view is rebuilt in place. This browser import directory is ignored by Git so routine viewer use does not dirty the tracked sample JSON files. Use `--import-json-dir` to change that destination.

When running from WSL, `Open path` is usually faster for large Windows-side files because it lets the server read a WSL-accessible path directly instead of uploading the file through the browser. It accepts Linux paths such as `/mnt/c/.../sample.cif`, Windows drive paths such as `C:\...\sample.cif`, and existing JSON paths such as `exports/json/sample.json`.

Molecule files can be opened as XYZ through the browser `Open XYZ` control, through `Open path`, or directly on the command line. They are analyzed as molecular point groups and exported to JSON before loading:

```bash
.venv/bin/python tools/view_json_server.py examples/water.xyz --no-browser
```

For smoother interactive playback, the GUI defaults to source atoms only. Use `--expanded` when you need the half-cell periodic display clones:

```bash
.venv/bin/python tools/view_json_gui.py exports/json/jacobsite.json --expanded
```

`--expanded` uses a smaller quarter-cell margin `[-0.25, 1.25]` to keep the GUI responsive.

List operations or atoms before opening the GUI:

```bash
.venv/bin/python tools/view_json_gui.py exports/json/jacobsite.json --list-operations
.venv/bin/python tools/view_json_gui.py exports/json/jacobsite.json --list-atoms
```

Open at a specific operation or with selected atoms:

```bash
.venv/bin/python tools/view_json_gui.py exports/json/jacobsite.json --operation 25
.venv/bin/python tools/view_json_gui.py exports/json/jacobsite.json --scope selected --selected-atoms 0 1 2
```

The first GUI intentionally avoids Qt/PyVistaQt. It uses PyVista's native slider and keyboard widgets because WSL/X11 can fail with `BadWindow` when VTK is embedded in Qt.

The browser-controlled viewer also avoids Qt. It communicates with Python through a local stdlib HTTP server, so it is the preferred path for list-based controls and future puzzle UI.

Controls:

```text
operation slider: choose operation
speed slider: playback speed
space: play / stop
n / p: next / previous operation
r: reset animation
1 / 2 / 3: all / representative / selected scope
```

If the current directory is `tools/`, use:

```bash
../.venv/bin/python view_json_gui.py ../exports/json/jacobsite.json
```

`exports/json/` は共有用のJSON本体、`exports/gifs/<structure>/` はローカル確認用のGIF/PNG置き場です。

`--animation-scope representative` animates one representative atom only. `--animation-scope all` animates every atom, but the crystal periodic image is chosen once from the representative atom and then applied to all atoms as the same integer lattice shift. Use `--representative-atom N` when a specific atom should define that shared movement.

For crystal JSON, the viewer shows periodic display images in a half-cell expanded fractional window `[-0.5, 1.5]`. These images are display clones only; animation paths are still computed once per source atom and copied with a constant lattice shift.

Crystal JSON also stores `asymmetric_atoms`, the atom sites written directly in the CIF, and records `asymmetric_index` / `generation_operation_index` on each expanded atom. Jacobsite therefore keeps the CIF representatives Mn1/Fe1/O1 separately from the 56 expanded atoms.

## Jacobsite Check Notes

`examples/structures/jacobsite.cif` is a broader crystal symmetry sample:

```text
space group: 227 Fd-3m
operations: 192
representative operations checked:
  op 1  screw_4
  op 4  rotation_2
  op 24 inversion
  op 25 rotoinversion_or_improper_4
  op 26 glide
  op 31 mirror
```

For `op 25`, the viewer derives the effective rotoinversion axis from the operation matrix and animates it as rotation followed by inversion.

## Scope

Implemented:

```text
atoms
unit cell
axes
planes
centers
operation-based element filtering
operation list
operation element list
atom mapping printout
source-to-target displacement lines
operation animation
minimal JSON GUI
screenshots
```

Not implemented yet:

```text
puzzle interactions
CIF/XYZ open and analysis from the GUI
CIF/XYZ open and analysis from the GUI
mouse-based atom picking
```

This viewer is intentionally separate from analysis code. It should consume only exported JSON.
