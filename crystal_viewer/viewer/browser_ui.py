from __future__ import annotations

from ..source_kinds import source_kind_ui_config_json


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Symmetry Controls</title>
  <style>
    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #111418;
      color: #edf2f7;
    }
    main {
      max-width: 1100px;
      margin: 0 auto;
      padding: 20px;
    }
    h1 {
      font-size: 21px;
      margin: 0;
    }
    label {
      display: block;
      font-size: 13px;
      color: #aeb8c5;
      margin-bottom: 8px;
    }
    select, button, input {
      font: inherit;
    }
    input {
      box-sizing: border-box;
      background: #151a20;
      color: #edf2f7;
      border: 1px solid #3a4350;
      border-radius: 6px;
      padding: 8px;
    }
    select {
      width: 100%;
      box-sizing: border-box;
      background: #151a20;
      color: #edf2f7;
      border: 1px solid #3a4350;
      border-radius: 6px;
      padding: 8px;
    }
    .direction-filter-list {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 0;
      max-height: 116px;
      overflow: auto;
      padding: 6px;
      border: 1px solid #3a4350;
      border-radius: 6px;
      background: #1b2027;
    }
    .direction-chip {
      margin: 0;
      padding: 6px 9px;
      border: 1px solid #3a4350;
      border-radius: 5px;
      background: #151a20;
      color: #edf2f7;
    }
    .direction-chip.selected {
      background: #7dd3fc;
      color: #081017;
      border-color: #7dd3fc;
    }
    .speed-button.selected {
      background: #7dd3fc;
      color: #081017;
    }
    .display-button.selected {
      background: #7dd3fc;
      color: #081017;
    }
    .projection-button.selected {
      background: #7dd3fc;
      color: #081017;
    }
    .mode-button.selected {
      background: #7dd3fc;
      color: #081017;
    }
    .atom-mode-button.selected {
      background: #7dd3fc;
      color: #081017;
    }
    .structure-kind-button.selected {
      background: #7dd3fc;
      color: #081017;
    }
    .overbar {
      text-decoration: overline;
      text-decoration-thickness: 1.5px;
    }
    .operation-list {
      width: 100%;
      min-height: 280px;
      max-height: 380px;
      overflow: auto;
      background: #1b2027;
      color: #edf2f7;
      border: 1px solid #3a4350;
      border-radius: 6px;
      padding: 8px;
    }
    .operation-row {
      display: block;
      width: 100%;
      margin: 0 0 4px;
      padding: 7px 8px;
      color: #edf2f7;
      text-align: left;
      background: transparent;
      border: 0;
      border-radius: 5px;
      cursor: pointer;
    }
    .operation-row:hover {
      background: #26303b;
    }
    .operation-row.selected {
      background: #7dd3fc;
      color: #081017;
    }
    button {
      border: 0;
      border-radius: 6px;
      padding: 10px 14px;
      color: #101216;
      background: #7dd3fc;
      cursor: pointer;
    }
    button.secondary {
      background: #cbd5e1;
    }
    button:disabled {
      cursor: wait;
      opacity: 0.48;
    }
    .saving-gif button:not(#save-gif):not(#save-gif-3view),
    .saving-gif input,
    .saving-gif select {
      pointer-events: none;
      opacity: 0.55;
    }
    .saving-gif #save-gif,
    .saving-gif #save-gif-3view {
      background: #f8fafc;
      color: #111418;
      cursor: wait;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
      gap: 16px;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }
    .topbar-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 10px;
      flex-wrap: wrap;
    }
    .file-input {
      max-width: 220px;
      padding: 7px;
    }
    .structure-summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 10px;
    }
    .summary-item {
      display: grid;
      gap: 3px;
    }
    .summary-label {
      color: #91a0b3;
      font-size: 12px;
    }
    .summary-value {
      color: #f8fafc;
      font-weight: 600;
      overflow-wrap: anywhere;
    }
    .panel {
      background: #151a20;
      border: 1px solid #29313c;
      border-radius: 8px;
      padding: 14px;
    }
    .side-stack {
      display: grid;
      gap: 16px;
      align-content: start;
    }
    .left-stack {
      display: grid;
      gap: 16px;
      align-content: start;
    }
    .section-title {
      margin: 0 0 12px;
      font-size: 15px;
      color: #f8fafc;
    }
    .subsection-title {
      margin: 14px 0 8px;
      font-size: 13px;
      color: #d7dee9;
    }
    .control-stack {
      display: grid;
      gap: 12px;
      margin-bottom: 12px;
    }
    .button-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 12px 0 0;
    }
    .button-row.flush {
      margin-top: 0;
    }
    .camera-block {
      display: grid;
      gap: 10px;
      margin-bottom: 14px;
    }
    .camera-block:last-of-type {
      margin-bottom: 0;
    }
    .camera-grid {
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      gap: 8px;
      align-items: center;
      justify-items: center;
    }
    .camera-grid button {
      min-width: 48px;
      padding: 8px 12px;
    }
    .angle-control {
      width: 88px;
      text-align: center;
    }
    .view-center-row {
      display: grid;
      grid-template-columns: repeat(3, minmax(62px, 1fr));
      gap: 6px;
      margin-top: 8px;
    }
    .view-center-row input {
      width: 100%;
      text-align: right;
    }
    .atom-list {
      max-height: 280px;
      overflow: auto;
      background: #1b2027;
      border: 1px solid #3a4350;
      border-radius: 6px;
      padding: 8px;
    }
    .atom-row {
      display: flex;
      gap: 8px;
      align-items: baseline;
      padding: 4px 2px;
      font-size: 13px;
    }
    .atom-row input[type="color"] {
      width: 28px;
      height: 24px;
      padding: 0;
      border: 0;
      background: transparent;
      flex: 0 0 auto;
    }
    .element-color-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 12px;
    }
    .element-color-item {
      display: inline-flex;
      gap: 6px;
      align-items: center;
      color: #cbd5e1;
      font-size: 13px;
    }
    .element-color-item input[type="color"] {
      width: 30px;
      height: 24px;
      padding: 0;
      border: 0;
      background: transparent;
    }
    .check-row {
      display: flex;
      gap: 8px;
      align-items: center;
      margin: 0 0 10px;
      color: #cbd5e1;
    }
    .check-row input {
      width: auto;
      margin: 0;
    }
    .atom-row span {
      color: #cbd5e1;
    }
    .atom-row.unmapped {
      background: rgba(248, 113, 113, 0.14);
      border-radius: 5px;
      padding-left: 6px;
    }
    .atom-badge {
      color: #fecaca;
      font-size: 11px;
      margin-left: 6px;
    }
    .hint {
      color: #91a0b3;
      font-size: 12px;
      margin-top: 8px;
    }
    .overline {
      text-decoration: overline;
      text-decoration-thickness: 0.08em;
      text-decoration-skip-ink: none;
    }
    .status {
      margin-top: 14px;
      padding: 10px;
      border-radius: 6px;
      background: #1b2027;
      color: #cbd5e1;
      font-size: 13px;
      white-space: pre-wrap;
    }
    .operation-details {
      max-height: 260px;
      overflow: auto;
      font-family: monospace;
      font-size: 12px;
      color: #94a3b8;
      white-space: pre;
      line-height: 1.6;
      min-height: 0;
    }
    .vec3-row {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 6px;
      margin-bottom: 8px;
    }
    .mat3-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 4px;
      margin-bottom: 8px;
    }
    .vec3-row input, .mat3-grid input {
      width: 100%;
      box-sizing: border-box;
      text-align: right;
      padding: 6px;
    }
    .narrow-input {
      width: 96px;
      margin-bottom: 8px;
    }
    .cop-result {
      margin-top: 10px;
      padding: 10px;
      border-radius: 6px;
      background: #1b2027;
      font-size: 13px;
    }
    .cop-result.ok { border-left: 3px solid #6ee7b7; color: #a7f3d0; }
    .cop-result.fail { border-left: 3px solid #fca5a5; color: #fecaca; }
    .cop-result .unmapped-list {
      font-family: monospace;
      font-size: 12px;
      max-height: 130px;
      overflow: auto;
      margin-top: 6px;
      color: #e2e8f0;
    }
    @media (max-width: 820px) {
      main {
        padding: 14px;
      }
      .grid, .topbar {
        display: block;
      }
      .panel {
        margin-bottom: 14px;
      }
    }
  </style>
</head>
<body>
<main>
  <div class="topbar">
    <h1>Symmetry Controls</h1>
    <div class="topbar-actions">
      <div class="button-row flush" id="structure-kind-controls">
        <button class="secondary structure-kind-button selected" data-kind="crystal">Crystal</button>
        <button class="secondary structure-kind-button" data-kind="molecule">Molecule</button>
      </div>
      <input id="cif-file" class="file-input" type="file" accept=".cif,.txt">
      <button id="import-cif" class="secondary">Open CIF</button>
      <input id="molecule-file" class="file-input" type="file" accept=".xyz,.txt">
      <button id="import-molecule" class="secondary">Open XYZ</button>
      <div class="button-row flush" id="mode-controls">
        <button class="secondary mode-button selected" data-mode="standard">Symmetry operation</button>
        <button class="secondary mode-button" data-mode="custom">Custom operation</button>
      </div>
    </div>
  </div>
  <section class="panel" id="start-panel" hidden>
    <h2 class="section-title">Open Structure</h2>
    <p class="hint">Open a CIF for crystal symmetry or an XYZ for molecular point-group symmetry.</p>
  </section>
  <section class="panel" id="structure-info-panel" hidden>
    <h2 class="section-title">Structure Info</h2>
    <div class="structure-summary" id="structure-info"></div>
  </section>
  <div class="grid" id="workspace">
    <div class="left-stack">
    <section class="panel" id="standard-panel">
      <h2 class="section-title">Operations</h2>
      <div class="control-stack">
        <div>
          <label for="operation-sort">Sort</label>
          <select id="operation-sort">
            <option value="index">Operation number</option>
            <option value="symbol">Operation symbol</option>
            <option value="element">Axis / plane / center</option>
            <option value="direction">Direction only</option>
          </select>
        </div>
        <div>
          <label id="operation-filter-label">Direction</label>
          <div class="direction-filter-list" id="direction-filter"></div>
        </div>
      </div>
      <label for="operations">Operation list</label>
      <div class="operation-list" id="operations" role="listbox"></div>
      <p class="hint">The selected operation controls the axis/plane/center shown in PyVista.</p>
    </section>
    <section class="panel" id="custom-panel" hidden>
      <h2 class="section-title">Custom Operation</h2>
      <p class="hint">Enter any (W|t) operation and check it against the unit-cell atoms. After checking, the shared animation and atom controls apply to this operation.</p>
      <div class="control-stack">
        <div>
          <label for="cop-type">Operation type</label>
          <select id="cop-type">
            <option value="rotation">Rotation</option>
            <option value="mirror">Mirror</option>
            <option value="inversion">Inversion</option>
            <option value="screw">Screw axis</option>
            <option value="glide">Glide reflection</option>
            <option value="rotoinversion">Rotoinversion (Sₙ)</option>
            <option value="translation">Translation</option>
            <option value="identity">Identity</option>
            <option value="matrix">Matrix (W|t) direct input</option>
          </select>
        </div>
        <div id="cop-rotation" class="cop-fields">
          <label>Axis [u v w] — fractional lattice direction</label>
          <div class="vec3-row">
            <input type="number" id="cop-rot-u" value="0" step="any" placeholder="u">
            <input type="number" id="cop-rot-v" value="0" step="any" placeholder="v">
            <input type="number" id="cop-rot-w" value="1" step="any" placeholder="w">
          </div>
          <label>Angle (degrees)</label>
          <input type="number" id="cop-rot-angle" value="90" step="any" class="narrow-input">
          <label>Point on axis [x y z] — fractional</label>
          <div class="vec3-row">
            <input type="number" id="cop-rot-px" value="0" step="any" placeholder="x">
            <input type="number" id="cop-rot-py" value="0" step="any" placeholder="y">
            <input type="number" id="cop-rot-pz" value="0" step="any" placeholder="z">
          </div>
        </div>
        <div id="cop-mirror" class="cop-fields" hidden>
          <label>Plane normal (h k l) — Miller indices</label>
          <div class="vec3-row">
            <input type="number" id="cop-mir-h" value="0" step="any" placeholder="h">
            <input type="number" id="cop-mir-k" value="0" step="any" placeholder="k">
            <input type="number" id="cop-mir-l" value="1" step="any" placeholder="l">
          </div>
          <label>Point on plane [x y z] — fractional</label>
          <div class="vec3-row">
            <input type="number" id="cop-mir-px" value="0" step="any" placeholder="x">
            <input type="number" id="cop-mir-py" value="0" step="any" placeholder="y">
            <input type="number" id="cop-mir-pz" value="0" step="any" placeholder="z">
          </div>
        </div>
        <div id="cop-inversion" class="cop-fields" hidden>
          <label>Inversion center [x y z] — fractional</label>
          <div class="vec3-row">
            <input type="number" id="cop-inv-cx" value="0" step="any" placeholder="x">
            <input type="number" id="cop-inv-cy" value="0" step="any" placeholder="y">
            <input type="number" id="cop-inv-cz" value="0" step="any" placeholder="z">
          </div>
        </div>
        <div id="cop-screw" class="cop-fields" hidden>
          <label>Axis [u v w] — fractional</label>
          <div class="vec3-row">
            <input type="number" id="cop-scr-u" value="0" step="any" placeholder="u">
            <input type="number" id="cop-scr-v" value="0" step="any" placeholder="v">
            <input type="number" id="cop-scr-w" value="1" step="any" placeholder="w">
          </div>
          <label>Rotation angle (degrees)</label>
          <input type="number" id="cop-scr-angle" value="180" step="any" class="narrow-input">
          <label>Screw translation [tx ty tz] — fractional</label>
          <div class="vec3-row">
            <input type="number" id="cop-scr-tx" value="0" step="any" placeholder="tx">
            <input type="number" id="cop-scr-ty" value="0" step="any" placeholder="ty">
            <input type="number" id="cop-scr-tz" value="0.5" step="any" placeholder="tz">
          </div>
          <label>Point on axis [x y z] — fractional</label>
          <div class="vec3-row">
            <input type="number" id="cop-scr-px" value="0" step="any" placeholder="x">
            <input type="number" id="cop-scr-py" value="0" step="any" placeholder="y">
            <input type="number" id="cop-scr-pz" value="0" step="any" placeholder="z">
          </div>
        </div>
        <div id="cop-glide" class="cop-fields" hidden>
          <label>Plane normal (h k l) — Miller indices</label>
          <div class="vec3-row">
            <input type="number" id="cop-gli-h" value="0" step="any" placeholder="h">
            <input type="number" id="cop-gli-k" value="0" step="any" placeholder="k">
            <input type="number" id="cop-gli-l" value="1" step="any" placeholder="l">
          </div>
          <label>Point on plane [x y z] — fractional</label>
          <div class="vec3-row">
            <input type="number" id="cop-gli-px" value="0" step="any" placeholder="x">
            <input type="number" id="cop-gli-py" value="0" step="any" placeholder="y">
            <input type="number" id="cop-gli-pz" value="0" step="any" placeholder="z">
          </div>
          <label>Glide translation [tx ty tz] — fractional</label>
          <div class="vec3-row">
            <input type="number" id="cop-gli-tx" value="0.5" step="any" placeholder="tx">
            <input type="number" id="cop-gli-ty" value="0" step="any" placeholder="ty">
            <input type="number" id="cop-gli-tz" value="0" step="any" placeholder="tz">
          </div>
        </div>
        <div id="cop-rotoinversion" class="cop-fields" hidden>
          <label>Axis [u v w] — fractional</label>
          <div class="vec3-row">
            <input type="number" id="cop-riv-u" value="0" step="any" placeholder="u">
            <input type="number" id="cop-riv-v" value="0" step="any" placeholder="v">
            <input type="number" id="cop-riv-w" value="1" step="any" placeholder="w">
          </div>
          <label>Rotation angle before inversion (degrees)</label>
          <input type="number" id="cop-riv-angle" value="90" step="any" class="narrow-input">
          <label>Inversion center [x y z] — fractional</label>
          <div class="vec3-row">
            <input type="number" id="cop-riv-cx" value="0" step="any" placeholder="x">
            <input type="number" id="cop-riv-cy" value="0" step="any" placeholder="y">
            <input type="number" id="cop-riv-cz" value="0" step="any" placeholder="z">
          </div>
        </div>
        <div id="cop-translation" class="cop-fields" hidden>
          <label>Translation [tx ty tz] — fractional</label>
          <div class="vec3-row">
            <input type="number" id="cop-tra-x" value="0.5" step="any" placeholder="tx">
            <input type="number" id="cop-tra-y" value="0.5" step="any" placeholder="ty">
            <input type="number" id="cop-tra-z" value="0" step="any" placeholder="tz">
          </div>
        </div>
        <div id="cop-identity" class="cop-fields" hidden>
          <p class="hint">Identity: W = I, t = 0. All atoms map to themselves.</p>
        </div>
        <div id="cop-matrix" class="cop-fields" hidden>
          <label>Rotation matrix W — 3×3 row-major, fractional basis</label>
          <div class="mat3-grid">
            <input type="number" id="cop-mat-w00" value="1" step="any">
            <input type="number" id="cop-mat-w01" value="0" step="any">
            <input type="number" id="cop-mat-w02" value="0" step="any">
            <input type="number" id="cop-mat-w10" value="0" step="any">
            <input type="number" id="cop-mat-w11" value="1" step="any">
            <input type="number" id="cop-mat-w12" value="0" step="any">
            <input type="number" id="cop-mat-w20" value="0" step="any">
            <input type="number" id="cop-mat-w21" value="0" step="any">
            <input type="number" id="cop-mat-w22" value="1" step="any">
          </div>
          <label>Translation t — fractional</label>
          <div class="vec3-row">
            <input type="number" id="cop-mat-tx" value="0" step="any" placeholder="tx">
            <input type="number" id="cop-mat-ty" value="0" step="any" placeholder="ty">
            <input type="number" id="cop-mat-tz" value="0" step="any" placeholder="tz">
          </div>
        </div>
        <div>
          <label for="cop-tol">Tolerance (Å)</label>
          <input type="number" id="cop-tol" value="0.1" min="0.001" max="2.0" step="0.01" class="narrow-input">
        </div>
      </div>
      <div class="button-row flush">
        <button id="btn-check-op">Check symmetry</button>
        <button id="btn-clear-check" class="secondary">Clear custom</button>
      </div>
      <div id="cop-result" class="cop-result" hidden></div>
    </section>
    <section class="panel">
      <h2 class="section-title">Selected Operation</h2>
      <div id="op-details" class="operation-details"></div>
    </section>
    </div>
    <div class="side-stack">
      <section class="panel">
        <h2 class="section-title">Animation</h2>
        <div class="button-row flush">
          <button id="play-toggle">Start</button>
          <button id="reset" class="secondary">Reset</button>
          <button id="save-gif" class="secondary">Save GIF</button>
          <button id="save-gif-3view" class="secondary">Save 3-view GIFs</button>
        </div>
        <h3 class="subsection-title">Speed</h3>
        <div class="button-row flush" id="speed-controls">
          <button class="secondary speed-button" data-speed="0.5">Slow</button>
          <button class="secondary speed-button selected" data-speed="1.0">Normal</button>
          <button class="secondary speed-button" data-speed="2.0">Fast</button>
        </div>
        <div>
          <label for="improper-mode">Improper operation</label>
          <select id="improper-mode">
            <option value="auto">Auto</option>
            <option value="rotoreflection">Rotoreflection</option>
            <option value="rotoinversion">Rotoinversion</option>
          </select>
        </div>
        <p class="hint">Start or stop the selected operation and save the current view as a GIF.</p>
        <h2 class="section-title">Camera</h2>
        <div class="camera-block">
          <label for="camera-angle">Rotate current view</label>
          <div class="camera-grid">
            <span></span>
            <button id="camera-up" class="secondary">Up</button>
            <span></span>
            <button id="camera-left" class="secondary">Left</button>
            <input id="camera-angle" class="angle-control" type="number" value="90" min="0" max="180" step="1">
            <button id="camera-right" class="secondary">Right</button>
            <span></span>
            <button id="camera-down" class="secondary">Down</button>
            <span></span>
          </div>
        </div>
        <div class="camera-block">
          <label>Projection</label>
          <div class="button-row flush" id="projection-controls">
            <button class="secondary projection-button selected" data-projection-mode="perspective">Perspective</button>
            <button class="secondary projection-button" data-projection-mode="orthographic">Orthographic</button>
          </div>
        </div>
        <div class="camera-block">
          <div class="button-row flush">
            <button id="view-direction" class="secondary">View along direction</button>
            <button id="reset-view" class="secondary">Reset view center</button>
          </div>
          <label id="view-center-label">View center [x y z] — fractional</label>
          <div class="view-center-row">
            <input type="number" id="view-center-x" value="0.5" step="any" placeholder="x">
            <input type="number" id="view-center-y" value="0.5" step="any" placeholder="y">
            <input type="number" id="view-center-z" value="0.5" step="any" placeholder="z">
          </div>
          <div class="button-row flush">
            <button id="apply-view-center" class="secondary">Apply center</button>
          </div>
        </div>
        <div id="display-block">
          <h2 class="section-title">Display</h2>
          <label>Range</label>
          <div class="button-row flush" id="display-controls">
            <button class="secondary display-button selected" data-display-mode="source">Unit cell</button>
            <button class="secondary display-button" data-display-mode="expanded_quarter">±1/4</button>
            <button class="secondary display-button" data-display-mode="expanded_half">±1/2</button>
            <button class="secondary display-button" data-display-mode="expanded_0_75">±3/4</button>
            <button class="secondary display-button" data-display-mode="expanded_1_0">±1</button>
          </div>
        </div>
      </section>
      <section class="panel">
        <h2 class="section-title">Atoms</h2>
        <label>Element colors</label>
        <div class="element-color-list" id="element-colors"></div>
        <label>Element filter</label>
        <div class="direction-filter-list" id="atom-element-filter"></div>
        <label>Animated atoms</label>
        <div class="atom-list" id="atoms"></div>
        <div class="button-row">
          <button id="displayed-atoms" class="secondary atom-mode-button" data-scope="displayed">Displayed all</button>
          <button id="unit-cell-atoms" class="secondary atom-mode-button" data-scope="unit_cell">Unit cell only</button>
          <button id="clear-atoms" class="secondary atom-mode-button" data-scope="representative">Clear</button>
        </div>
        <p class="hint">Check atoms to animate selected atom types. Unit cell only leaves periodic display copies fixed.</p>
      </section>
    </div>
  </div>
  <div class="status" id="status">Loading...</div>
</main>
<script>
let operations = [];
let atoms = [];
let state = {};
let directionFilterValue = "";
let atomElementFilterValue = "";
let summariesReady = false;
let activeMode = "standard";
let customUnmappedAtoms = new Set();
let sourceKind = "crystal";
let selectedStructureKind = "crystal";
let importInProgress = false;
let refreshInProgress = false;
let importRequestId = 0;
const STRUCTURE_KIND_UI = __STRUCTURE_KIND_CONFIG__;

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  if (response.status === 204) return null;
  return await response.json();
}

function optionText(operation) {
  if (sourceKind === "molecule") {
    return `op ${operation.index}: ${formatSymbol(displayOperationSymbol(operation))}`;
  }
  const element = operation.element_summary ? ` | ${operation.element_summary}` : "";
  return `op ${operation.index}: ${formatSymbol(displayOperationSymbol(operation))}${element}`;
}

function renderHtml(text) {
  const template = document.createElement("template");
  template.innerHTML = text;
  return template.content;
}

function formatSymbol(symbol) {
  const subscripts = "₀₁₂₃₄₅₆";
  return String(symbol)
    .replace(/sigma/g, "σ")
    .replace(/_([0-6])/g, (_, digit) => subscripts[Number(digit)]);
}

function resolvedImproperMode() {
  const requested = state.improper_mode || "auto";
  if (requested === "rotoreflection" || requested === "rotoinversion") return requested;
  return sourceKind === "molecule" ? "rotoreflection" : "rotoinversion";
}

function isImproperOperation(operation) {
  const kind = String(operation.kind || "");
  return kind.includes("improper") || kind.includes("rotoinversion") || kind.includes("rotoreflection");
}

function displayOperationSymbol(operation) {
  if (!isImproperOperation(operation)) {
    return operation.display_symbol || operation.symbol || "";
  }
  const match = String(operation.symbol || "").match(/[0-9]+/);
  const order = operation.order || (match ? match[0] : "");
  if (resolvedImproperMode() === "rotoreflection") {
    return order ? `S${order}` : (operation.display_symbol || operation.symbol || "");
  }
  return order ? `<span class="overbar">${order}</span>` : (operation.display_symbol || operation.symbol || "");
}

function atomText(atom) {
  const frac = atom.frac_label ? ` frac=${atom.frac_label}` : "";
  const asym = atom.asymmetric_index === null || atom.asymmetric_index === undefined
    ? ""
    : ` asym=${atom.asymmetric_index}`;
  return `${atom.index}: ${atom.element}${frac}${asym}`;
}

function normalizeColor(value, fallback = "#9aa5b1") {
  const text = String(value || "").trim();
  if (/^#[0-9a-fA-F]{6}$/.test(text)) return text.toLowerCase();
  return fallback;
}

function atomEffectiveColor(atom) {
  const atomColors = state.atom_colors || {};
  const elementColors = state.element_colors || {};
  return normalizeColor(
    atomColors[String(atom.index)] || elementColors[atom.element] || atom.default_color,
  );
}

function renderOperations() {
  const root = document.getElementById("operations");
  root.innerHTML = "";
  for (const operation of sortedOperations()) {
    if (directionFilterValue && operationFilterKey(operation) !== directionFilterValue) continue;
    const text = optionText(operation);
    const row = document.createElement("button");
    row.type = "button";
    row.className = "operation-row";
    row.dataset.index = operation.index;
    row.setAttribute("role", "option");
    row.setAttribute("aria-selected", operation.index === state.operation_index ? "true" : "false");
    if (operation.index === state.operation_index) row.classList.add("selected");
    row.appendChild(renderHtml(text));
    row.addEventListener("click", () => {
      postState({operation_index: operation.index, playing: false, reset: true});
    });
    root.appendChild(row);
  }
}

function renderDirectionFilter() {
  const root = document.getElementById("direction-filter");
  const filterType = operationFilterType();
  document.getElementById("operation-filter-label").textContent =
    filterType === "symbol" ? "Symbol" : "Direction";
  const values = [...new Map(
    operations
      .map(operation => [operationFilterKey(operation), operationFilterLabel(operation)])
      .filter(([value]) => value && value !== "none")
  ).entries()].sort((a, b) => compareText(a[1], b[1]));
  root.innerHTML = "";
  const allButton = document.createElement("button");
  allButton.type = "button";
  allButton.className = `direction-chip${directionFilterValue ? "" : " selected"}`;
  allButton.textContent = "All";
  allButton.addEventListener("click", () => {
    directionFilterValue = "";
    renderDirectionFilter();
    renderOperations();
  });
  root.appendChild(allButton);
  for (const [value, label] of values) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `direction-chip${value === directionFilterValue ? " selected" : ""}`;
    button.appendChild(renderHtml(label));
    button.addEventListener("click", () => {
      directionFilterValue = value;
      renderDirectionFilter();
      renderOperations();
    });
    root.appendChild(button);
  }
  if (directionFilterValue && !values.some(([value]) => value === directionFilterValue)) {
    directionFilterValue = "";
    renderDirectionFilter();
    renderOperations();
  }
}

function sortedOperations() {
  const mode = document.getElementById("operation-sort").value;
  return [...operations].sort((a, b) => {
    if (mode === "symbol") {
      return compareText(sortableSymbol(a), sortableSymbol(b)) || compareNumber(a.index, b.index);
    }
    if (mode === "element") {
      return compareText(a.element_sort_key || "", b.element_sort_key || "") || compareNumber(a.index, b.index);
    }
    if (mode === "direction") {
      return compareText(a.direction_sort_key || "", b.direction_sort_key || "") || compareNumber(a.index, b.index);
    }
    return compareNumber(a.index, b.index);
  });
}

function sortableSymbol(operation) {
  return stripHtml(`${displayOperationSymbol(operation)}`).replace(/_/g, "");
}

function operationFilterType() {
  return document.getElementById("operation-sort").value === "symbol" ? "symbol" : "direction";
}

function operationFilterKey(operation) {
  if (operationFilterType() === "symbol") return sortableSymbol(operation);
  return operation.direction_sort_key || "";
}

function operationFilterLabel(operation) {
  if (operationFilterType() === "symbol") return formatSymbol(displayOperationSymbol(operation));
  return operation.direction_label || operation.direction_filter_label || operation.direction_sort_key || "";
}

function stripHtml(text) {
  const template = document.createElement("template");
  template.innerHTML = text;
  return template.content.textContent || "";
}

function compareText(a, b) {
  return String(a).localeCompare(String(b), undefined, {numeric: true, sensitivity: "base"});
}

function compareNumber(a, b) {
  return Number(a) - Number(b);
}

function basename(path) {
  const text = String(path || "");
  if (!text) return "-";
  const parts = text.split(/[\\\\/]/);
  return parts[parts.length - 1] || text;
}

function structureLoadedForSelectedKind() {
  const loaded = state.structure_loaded !== false && sourceKind !== "empty";
  return loaded && sourceKind === selectedStructureKind;
}

function sourceKindConfig(kind) {
  return STRUCTURE_KIND_UI[kind] || STRUCTURE_KIND_UI.crystal;
}

function setDefaultOperationSortForSourceKind() {
  document.getElementById("operation-sort").value = sourceKind === "molecule" ? "symbol" : "index";
  directionFilterValue = "";
}

function renderStructureInfo() {
  const panel = document.getElementById("structure-info-panel");
  const root = document.getElementById("structure-info");
  if (!structureLoadedForSelectedKind()) {
    panel.hidden = true;
    root.innerHTML = "";
    return;
  }
  const metadata = state.metadata || {};
  const config = sourceKindConfig(sourceKind);
  const items = [
    ["Type", config.label],
    ["Name", basename(metadata.source_file || state.json_path)],
    ["Formula", metadata.formula || "-"],
    [config.symmetryLabel, metadata.symmetry_label || "-"],
    [
      "Operations",
      metadata.operation_count !== undefined && metadata.operation_count !== null
        ? metadata.operation_count
        : operations.length,
    ],
  ];
  root.innerHTML = "";
  for (const [label, value] of items) {
    const item = document.createElement("div");
    item.className = "summary-item";
    const labelEl = document.createElement("div");
    labelEl.className = "summary-label";
    labelEl.textContent = label;
    const valueEl = document.createElement("div");
    valueEl.className = "summary-value";
    valueEl.textContent = String(value);
    item.appendChild(labelEl);
    item.appendChild(valueEl);
    root.appendChild(item);
  }
  panel.hidden = false;
}

function syncStructureKindButtons() {
  for (const button of document.querySelectorAll(".structure-kind-button")) {
    button.classList.toggle("selected", button.dataset.kind === selectedStructureKind);
  }
}

function setStructureKind(kind) {
  if (importInProgress) {
    document.getElementById("status").textContent = "Loading in progress. Wait for it to finish.";
    return;
  }
  selectedStructureKind = kind === "molecule" ? "molecule" : "crystal";
  if (!structureLoadedForSelectedKind() && activeMode === "custom") {
    activeMode = "standard";
    syncActiveModeControls();
  }
  syncSourceKindControls();
  renderStructureInfo();
  renderStatus();
}

function syncImportControls() {
  for (const id of ["import-cif", "cif-file", "import-molecule", "molecule-file"]) {
    document.getElementById(id).disabled = importInProgress;
  }
  for (const button of document.querySelectorAll(".structure-kind-button")) {
    button.disabled = importInProgress;
  }
}

function beginImport(message) {
  importInProgress = true;
  const requestId = ++importRequestId;
  syncImportControls();
  document.getElementById("status").textContent = message;
  return requestId;
}

function finishImport(requestId) {
  if (requestId !== importRequestId) return;
  importInProgress = false;
  syncImportControls();
}

function isCurrentImport(requestId) {
  return requestId === importRequestId;
}

function syncOperationSelection() {
  for (const row of document.querySelectorAll(".operation-row")) {
    const selected = Number(row.dataset.index) === state.operation_index;
    row.classList.toggle("selected", selected);
    row.setAttribute("aria-selected", selected ? "true" : "false");
  }
}

function fmtMatVal(v) {
  if (v === null || v === undefined) return "  ?";
  const r = Math.round(v * 1e9) / 1e9;
  if (Number.isInteger(r) && Math.abs(r) < 10) return String(r).padStart(3);
  return r.toFixed(4).padStart(8);
}

function fmtFrac(v) {
  if (v === null || v === undefined) return "?";
  const r = Math.round(v * 1e9) / 1e9;
  if (Math.abs(r) < 1e-8 || Math.abs(r - 1.0) < 1e-8) return "0";
  // try to express as a simple fraction with denominator ≤ 24
  for (const d of [2, 3, 4, 6, 8, 12, 24]) {
    const n = Math.round(r * d);
    if (Math.abs(n / d - r) < 1e-8) return n === 0 ? "0" : `${n}/${d}`;
  }
  return r.toFixed(4);
}

function renderOperationDetails() {
  const div = document.getElementById("op-details");
  if (activeMode === "custom") {
    renderCustomOperationDetails();
    return;
  }
  const op = operations.find(o => o.index === state.operation_index);
  if (!op) { div.textContent = ""; return; }
  if (sourceKind === "molecule") {
    const Wc = op.matrix_cart;
    const tc = op.translation_cart;
    let lines = [];
    lines.push(`${stripHtml(optionText(op))}`);
    lines.push(`point group: ${(state.metadata && state.metadata.symmetry_label) || ""}`);
    if (isImproperOperation(op)) lines.push(`improper view: ${resolvedImproperMode()}`);
    lines.push("W (cart):");
    if (Wc) {
      for (const row of Wc) lines.push(`  [${row.map(v => v.toFixed(4).padStart(9)).join("  ")}]`);
    }
    if (tc && tc.some(v => Math.abs(v) > 1e-8)) {
      lines.push(`t (cart): ${tc.map(v => v.toFixed(4)).join(",  ")} Å`);
    }
    div.textContent = lines.join("\\n");
    return;
  }
  const W = op.matrix_frac;
  const t = op.translation_frac;
  if (!W || !t) { div.textContent = ""; return; }

  let lines = [];
  lines.push(`${stripHtml(optionText(op))}`);
  if (isImproperOperation(op)) lines.push(`improper view: ${resolvedImproperMode()}`);
  lines.push("W (frac):");
  for (const row of W) lines.push(`  [${row.map(fmtMatVal).join("  ")}]`);
  lines.push(`t (frac): ${t.map(fmtFrac).join(",  ")}`);

  const Wc = op.matrix_cart;
  const tc = op.translation_cart;
  if (Wc && tc) {
    lines.push("W (cart):  (Å scale)");
    for (const row of Wc) lines.push(`  [${row.map(v => v.toFixed(4).padStart(9)).join("  ")}]`);
    lines.push(`t (cart): ${tc.map(v => v.toFixed(4)).join(",  ")} Å`);
  }
  div.textContent = lines.join("\\n");
}

function renderCustomOperationDetails() {
  const div = document.getElementById("op-details");
  if (!copMatrix) {
    div.textContent = "Custom operation is not checked yet. Enter parameters and click Check symmetry.";
    return;
  }
  const result = copMatrix.result || {};
  let lines = [];
  lines.push(`custom ${copMatrix.op_type}`);
  lines.push(result.is_symmetry ? "status: symmetry operation" : "status: not a symmetry operation");
  if (result.total !== undefined) {
    lines.push(`mapped: ${result.mapped_count}/${result.total}  unmapped: ${result.unmapped_count}`);
  }
  lines.push("W (frac):");
  for (const row of copMatrix.W_frac) lines.push(`  [${row.map(fmtMatVal).join("  ")}]`);
  lines.push(`t (frac): ${copMatrix.t_frac.map(fmtFrac).join(",  ")}`);
  div.textContent = lines.join("\\n");
}

function renderAtomElementFilter() {
  const root = document.getElementById("atom-element-filter");
  const elements = [...new Set(atoms.map(atom => atom.element))].sort(compareText);
  root.innerHTML = "";
  const allButton = document.createElement("button");
  allButton.type = "button";
  allButton.className = `direction-chip${atomElementFilterValue ? "" : " selected"}`;
  allButton.textContent = "All";
  allButton.addEventListener("click", () => {
    atomElementFilterValue = "";
    renderAtomElementFilter();
    renderAtoms();
  });
  root.appendChild(allButton);
  for (const element of elements) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `direction-chip${element === atomElementFilterValue ? " selected" : ""}`;
    button.textContent = element;
    button.addEventListener("click", () => {
      atomElementFilterValue = element;
      renderAtomElementFilter();
      renderAtoms();
    });
    root.appendChild(button);
  }
}

function renderElementColorControls() {
  const root = document.getElementById("element-colors");
  const elements = [...new Set(atoms.map(atom => atom.element))].sort(compareText);
  const elementColors = state.element_colors || {};
  root.innerHTML = "";
  for (const element of elements) {
    const sample = atoms.find(atom => atom.element === element);
    const label = document.createElement("div");
    label.className = "element-color-item";
    const input = document.createElement("input");
    input.type = "color";
    input.value = normalizeColor(elementColors[element] || (sample && sample.default_color));
    input.addEventListener("change", () => {
      const next = Object.assign({}, state.element_colors || {});
      next[element] = input.value;
      postState({element_colors: next});
    });
    const span = document.createElement("span");
    span.textContent = element;
    label.appendChild(input);
    label.appendChild(span);
    root.appendChild(label);
  }
}

function renderAtoms() {
  const root = document.getElementById("atoms");
  const selected = new Set(state.selected_atoms || []);
  root.innerHTML = "";
  for (const atom of atoms) {
    if (atomElementFilterValue && atom.element !== atomElementFilterValue) continue;
    const text = atomText(atom);
    const label = document.createElement("label");
    label.className = "atom-row";
    if (customUnmappedAtoms.has(atom.index)) label.classList.add("unmapped");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = atom.index;
    checkbox.checked = selected.has(atom.index);
    checkbox.addEventListener("change", onAtomSelectionChange);
    const colorInput = document.createElement("input");
    colorInput.type = "color";
    colorInput.value = atomEffectiveColor(atom);
    colorInput.title = `Color for atom ${atom.index}`;
    colorInput.addEventListener("change", () => {
      const next = Object.assign({}, state.atom_colors || {});
      next[String(atom.index)] = colorInput.value;
      postState({atom_colors: next});
    });
    const span = document.createElement("span");
    span.appendChild(renderHtml(text));
    if (customUnmappedAtoms.has(atom.index)) {
      const badge = document.createElement("span");
      badge.className = "atom-badge";
      badge.textContent = "do not map";
      span.appendChild(badge);
    }
    label.appendChild(checkbox);
    label.appendChild(colorInput);
    label.appendChild(span);
    root.appendChild(label);
  }
}

function syncSpeedButtons() {
  const speed = Number(state.speed || 1.0);
  for (const button of document.querySelectorAll(".speed-button")) {
    button.classList.toggle("selected", Number(button.dataset.speed) === speed);
  }
}

function syncDisplayButtons() {
  const displayMode = state.display_mode || "source";
  for (const button of document.querySelectorAll(".display-button")) {
    button.classList.toggle("selected", button.dataset.displayMode === displayMode);
  }
}

function syncProjectionButtons() {
  const projectionMode = state.projection_mode || "perspective";
  for (const button of document.querySelectorAll(".projection-button")) {
    button.classList.toggle("selected", button.dataset.projectionMode === projectionMode);
  }
}

function syncImproperModeControl() {
  document.getElementById("improper-mode").value = state.improper_mode || "auto";
}

function syncAtomModeButtons() {
  const scope = state.scope || "representative";
  for (const button of document.querySelectorAll(".atom-mode-button")) {
    button.classList.toggle("selected", button.dataset.scope === scope);
  }
}

function syncPlayToggleButton() {
  const button = document.getElementById("play-toggle");
  button.textContent = state.playing ? "Stop" : "Start";
  button.classList.toggle("secondary", Boolean(state.playing));
}

function isGifSaving() {
  return String(state.gif_status || "").startsWith("writing ");
}

function syncGifSavingControls() {
  const saving = isGifSaving();
  document.body.classList.toggle("saving-gif", saving);
  for (const id of ["save-gif", "save-gif-3view", "play-toggle", "reset"]) {
    const button = document.getElementById(id);
    if (button) button.disabled = saving;
  }
  const saveGif = document.getElementById("save-gif");
  const save3 = document.getElementById("save-gif-3view");
  if (saveGif) saveGif.textContent = saving ? "Saving..." : "Save GIF";
  if (save3) save3.textContent = saving ? "Saving..." : "Save 3-view GIFs";
}

function selectedAtomIndices() {
  return Array.from(document.querySelectorAll("#atoms input[type=checkbox]:checked"))
    .map(input => Number(input.value));
}

function onAtomSelectionChange() {
  const selected = selectedAtomIndices();
  postState({
    selected_atoms: selected,
    scope: selected.length > 0 ? "selected" : "representative",
    playing: false,
    reset: true,
  });
}

function renderStatus() {
  if (!structureLoadedForSelectedKind()) {
    const config = sourceKindConfig(selectedStructureKind);
    document.getElementById("status").textContent =
      `No ${selectedStructureKind} loaded. Open a ${config.inputLabel}, JSON, or path.\\n` +
      `import: ${state.import_status || "-"}`;
    return;
  }
  const operation = operations.find(op => op.index === state.operation_index);
  const selected = state.selected_atoms && state.selected_atoms.length
    ? state.selected_atoms.join(", ")
    : "-";
  const scopeLabel = (state.scope || "representative") === "representative"
    ? "clear"
    : (state.scope || "representative");
  document.getElementById("status").textContent =
    `state: ${state.playing ? "playing" : "stopped"}\\n` +
    `mode: ${activeMode}\\n` +
    `operation: ${activeMode === "custom" ? (copMatrix ? "custom " + copMatrix.op_type : "custom unchecked") : (operation ? stripHtml(optionText(operation)) : state.operation_index)}\\n` +
    `speed: ${state.speed || 1.0}x\\n` +
    `projection: ${state.projection_mode || "perspective"}\\n` +
    `display: ${state.display_mode || "source"}\\n` +
    `scope: ${scopeLabel}\\n` +
    `selected atoms: ${selected}\\n` +
    `source: ${state.json_path || "-"}\\n` +
    `import: ${state.import_status || "-"}\\n` +
    `gif: ${state.gif_status || "-"}`;
}

function viewCenterValue(id, fallback = 0) {
  const value = Number(document.getElementById(id).value);
  return Number.isFinite(value) ? value : fallback;
}

function applyViewCenter() {
  postState({
    view_center_request_id: Date.now(),
    view_center_frac: [
      viewCenterValue("view-center-x"),
      viewCenterValue("view-center-y"),
      viewCenterValue("view-center-z"),
    ],
  });
}

function syncSourceKindControls() {
  sourceKind = state.source_kind || "crystal";
  syncStructureKindButtons();
  const loadedForSelected = structureLoadedForSelectedKind();
  document.getElementById("workspace").hidden = !loadedForSelected;
  document.getElementById("start-panel").hidden = loadedForSelected;
  document.getElementById("import-cif").hidden = selectedStructureKind !== "crystal";
  document.getElementById("cif-file").hidden = selectedStructureKind !== "crystal";
  document.getElementById("import-molecule").hidden = selectedStructureKind !== "molecule";
  document.getElementById("molecule-file").hidden = selectedStructureKind !== "molecule";
  document.getElementById("mode-controls").hidden = !loadedForSelected || sourceKind !== "crystal";
  document.getElementById("display-block").hidden = !loadedForSelected || sourceKind !== "crystal";
  document.getElementById("unit-cell-atoms").hidden = sourceKind !== "crystal";
  const config = sourceKindConfig(sourceKind);
  document.querySelector("#standard-panel .section-title").textContent =
    config.operationPanelTitle;
  if ((!loadedForSelected || sourceKind !== "crystal") && activeMode === "custom") {
    activeMode = "standard";
    syncActiveModeControls();
  }
  const label = document.getElementById("view-center-label");
  if (sourceKind !== "crystal") {
    label.textContent = config.viewCenterLabel;
    for (const id of ["view-center-x", "view-center-y", "view-center-z"]) {
      document.getElementById(id).value = "0";
    }
  } else {
    label.textContent = config.viewCenterLabel;
  }
}

async function postState(update) {
  state = await api("/api/state", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(update),
  });
  syncSpeedButtons();
  syncDisplayButtons();
  syncProjectionButtons();
  syncImproperModeControl();
  syncAtomModeButtons();
  syncPlayToggleButton();
  syncGifSavingControls();
  renderElementColorControls();
  renderDirectionFilter();
  renderOperations();
  renderAtoms();
  renderStructureInfo();
  renderStatus();
  renderOperationDetails();
}

async function importCifFile() {
  if (importInProgress) {
    document.getElementById("status").textContent = "Loading in progress. Wait for it to finish.";
    return;
  }
  const input = document.getElementById("cif-file");
  const file = input.files && input.files[0];
  if (!file) {
    document.getElementById("status").textContent = "Choose a CIF file first.";
    return;
  }
  const requestId = beginImport(`Loading ${file.name}...`);
  try {
    const content = await file.text();
    const result = await api("/api/import_cif", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({filename: file.name, content, request_id: requestId}),
    });
    if (!isCurrentImport(requestId)) return;
    applyLoadedStructure(result, "CIF import failed");
  } finally {
    finishImport(requestId);
  }
}

async function importMoleculeFile() {
  if (importInProgress) {
    document.getElementById("status").textContent = "Loading in progress. Wait for it to finish.";
    return;
  }
  const input = document.getElementById("molecule-file");
  const file = input.files && input.files[0];
  if (!file) {
    document.getElementById("status").textContent = "Choose an XYZ file first.";
    return;
  }
  const requestId = beginImport(`Loading ${file.name}...`);
  try {
    const content = await file.text();
    const result = await api("/api/import_molecule", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({filename: file.name, content, request_id: requestId}),
    });
    if (!isCurrentImport(requestId)) return;
    applyLoadedStructure(result, "Molecule import failed");
  } finally {
    finishImport(requestId);
  }
}

function applyLoadedStructure(result, fallbackError) {
  if (result.stale) {
    state = result.state || state;
    renderStatus();
    return;
  }
  if (!result.ok) {
    state = result.state || state;
    renderStatus();
    throw new Error(result.error || fallbackError);
  }
  operations = result.operations || [];
  atoms = result.atoms || [];
  state = result.state || {};
  if (state.source_kind === "crystal" || state.source_kind === "molecule") {
    selectedStructureKind = state.source_kind;
  }
  sourceKind = state.source_kind || "crystal";
  setDefaultOperationSortForSourceKind();
  directionFilterValue = "";
  atomElementFilterValue = "";
  summariesReady = Boolean(state.summaries_ready);
  customUnmappedAtoms = new Set();
  copMatrix = null;
  document.getElementById("cop-result").hidden = true;
  activeMode = "standard";
  syncActiveModeControls();
  syncSourceKindControls();
  renderDirectionFilter();
  renderAtomElementFilter();
  renderElementColorControls();
  syncOperationSelection();
  syncSpeedButtons();
  syncDisplayButtons();
  syncProjectionButtons();
  syncImproperModeControl();
  syncAtomModeButtons();
  syncPlayToggleButton();
  syncGifSavingControls();
  renderOperations();
  renderAtoms();
  renderStructureInfo();
  renderStatus();
  renderOperationDetails();
}

function syncActiveModeControls() {
  document.getElementById("standard-panel").hidden = activeMode !== "standard";
  document.getElementById("custom-panel").hidden = activeMode !== "custom";
  for (const button of document.querySelectorAll(".mode-button")) {
    button.classList.toggle("selected", button.dataset.mode === activeMode);
  }
}

function setActiveMode(mode) {
  activeMode = mode === "custom" ? "custom" : "standard";
  syncActiveModeControls();
  if (activeMode === "standard") {
    customUnmappedAtoms = new Set();
    copMatrix = null;
    renderAtoms();
    postState({active_mode: "standard", playing: false, reset: true, clear_custom_check: true});
  } else {
    postState({active_mode: "custom", playing: false});
  }
  renderStatus();
  renderOperationDetails();
}

async function refreshState() {
  if (refreshInProgress) return;
  refreshInProgress = true;
  try {
    state = await api("/api/state");
    syncOperationSelection();
    syncSpeedButtons();
    syncDisplayButtons();
    syncProjectionButtons();
    syncImproperModeControl();
    syncAtomModeButtons();
    syncPlayToggleButton();
    renderStructureInfo();
    renderStatus();
    renderOperationDetails();
    if (!summariesReady && state.summaries_ready) {
      summariesReady = true;
      const info = await api("/api/operations");
      operations = info.operations;
      renderDirectionFilter();
      renderOperations();
      renderOperationDetails();
    }
  } finally {
    refreshInProgress = false;
  }
}

document.getElementById("operation-sort").addEventListener("change", () => {
  directionFilterValue = "";
  renderDirectionFilter();
  renderOperations();
});
for (const button of document.querySelectorAll(".structure-kind-button")) {
  button.addEventListener("click", () => setStructureKind(button.dataset.kind));
}
document.getElementById("import-cif").addEventListener("click", () => {
  const input = document.getElementById("cif-file");
  input.value = "";
  input.click();
});
document.getElementById("cif-file").addEventListener("change", () => {
  importCifFile().catch(error => {
    document.getElementById("status").textContent = `Import error: ${error}`;
  });
});
document.getElementById("import-molecule").addEventListener("click", () => {
  const input = document.getElementById("molecule-file");
  input.value = "";
  input.click();
});
document.getElementById("molecule-file").addEventListener("change", () => {
  importMoleculeFile().catch(error => {
    document.getElementById("status").textContent = `Import error: ${error}`;
  });
});
for (const button of document.querySelectorAll(".mode-button")) {
  button.addEventListener("click", () => setActiveMode(button.dataset.mode));
}
function startAnimation() {
  if (activeMode === "custom") {
    sendCurrentCustomAnimation(true);
    return;
  }
  postState({playing: true});
}

document.getElementById("play-toggle").addEventListener("click", () => {
  if (state.playing) {
    postState({playing: false});
  } else {
    startAnimation();
  }
});
document.getElementById("reset").addEventListener("click", () => postState({playing: false, reset: true}));
for (const button of document.querySelectorAll(".speed-button")) {
  button.addEventListener("click", () => postState({speed: Number(button.dataset.speed)}));
}
for (const button of document.querySelectorAll(".display-button")) {
  button.addEventListener("click", () => postState({
    display_mode: button.dataset.displayMode,
    playing: false,
    reset: true,
  }));
}
for (const button of document.querySelectorAll(".projection-button")) {
  button.addEventListener("click", () => postState({
    projection_mode: button.dataset.projectionMode,
    playing: false,
  }));
}
document.getElementById("improper-mode").addEventListener("change", event => {
  postState({
    improper_mode: event.target.value,
    playing: false,
    reset: true,
  });
});
document.getElementById("view-direction").addEventListener("click", () => {
  postState({view_request_id: Date.now()});
});
document.getElementById("reset-view").addEventListener("click", () => {
  postState({reset_view_request_id: Date.now()});
});
document.getElementById("apply-view-center").addEventListener("click", applyViewCenter);
document.getElementById("save-gif").addEventListener("click", () => {
  state.gif_status = "writing GIF...";
  syncGifSavingControls();
  renderStatus();
  if (activeMode === "custom") {
    sendCurrentCustomAnimation(false);
    window.setTimeout(() => postState({gif_request_id: Date.now(), playing: false}), 120);
    return;
  }
  postState({gif_request_id: Date.now(), playing: false});
});
document.getElementById("save-gif-3view").addEventListener("click", () => {
  state.gif_status = "writing 3-view GIFs...";
  syncGifSavingControls();
  renderStatus();
  if (activeMode === "custom") {
    sendCurrentCustomAnimation(false);
    window.setTimeout(() => postState({gif_3view_request_id: Date.now(), playing: false}), 120);
    return;
  }
  postState({gif_3view_request_id: Date.now(), playing: false});
});
function cameraAngle() {
  const value = Number(document.getElementById("camera-angle").value);
  if (!Number.isFinite(value)) return 90;
  return Math.max(0, Math.min(value, 180));
}
function rotateCamera(direction) {
  postState({
    camera_request_id: Date.now(),
    camera_direction: direction,
    camera_angle: cameraAngle(),
  });
}
document.getElementById("camera-left").addEventListener("click", () => rotateCamera("left"));
document.getElementById("camera-right").addEventListener("click", () => rotateCamera("right"));
document.getElementById("camera-up").addEventListener("click", () => rotateCamera("up"));
document.getElementById("camera-down").addEventListener("click", () => rotateCamera("down"));
document.getElementById("displayed-atoms").addEventListener("click", () => {
  postState({selected_atoms: atoms.map(atom => atom.index), scope: "displayed", playing: false, reset: true});
});
document.getElementById("unit-cell-atoms").addEventListener("click", () => {
  postState({selected_atoms: atoms.map(atom => atom.index), scope: "unit_cell", playing: false, reset: true});
});
document.getElementById("clear-atoms").addEventListener("click", () => {
  postState({selected_atoms: [], scope: "representative", playing: false, reset: true});
});

// --- Custom Operation Check ---

document.getElementById("cop-type").addEventListener("change", () => {
  const type = document.getElementById("cop-type").value;
  for (const el of document.querySelectorAll(".cop-fields")) el.hidden = true;
  const target = document.getElementById("cop-" + type);
  if (target) target.hidden = false;
});

function copNum(id, fallback = 0) {
  const v = Number(document.getElementById(id).value);
  return Number.isFinite(v) ? v : fallback;
}

function buildCopPayload() {
  const type = document.getElementById("cop-type").value;
  const tolerance = copNum("cop-tol", 0.1);
  let params = {};
  if (type === "rotation") {
    params = {
      axis: [copNum("cop-rot-u"), copNum("cop-rot-v"), copNum("cop-rot-w", 1)],
      angle: copNum("cop-rot-angle", 90),
      point: [copNum("cop-rot-px"), copNum("cop-rot-py"), copNum("cop-rot-pz")],
    };
  } else if (type === "mirror") {
    params = {
      normal: [copNum("cop-mir-h"), copNum("cop-mir-k"), copNum("cop-mir-l", 1)],
      point: [copNum("cop-mir-px"), copNum("cop-mir-py"), copNum("cop-mir-pz")],
    };
  } else if (type === "inversion") {
    params = {
      center: [copNum("cop-inv-cx"), copNum("cop-inv-cy"), copNum("cop-inv-cz")],
    };
  } else if (type === "screw") {
    params = {
      axis: [copNum("cop-scr-u"), copNum("cop-scr-v"), copNum("cop-scr-w", 1)],
      angle: copNum("cop-scr-angle", 180),
      screw: [copNum("cop-scr-tx"), copNum("cop-scr-ty"), copNum("cop-scr-tz", 0.5)],
      point: [copNum("cop-scr-px"), copNum("cop-scr-py"), copNum("cop-scr-pz")],
    };
  } else if (type === "glide") {
    params = {
      normal: [copNum("cop-gli-h"), copNum("cop-gli-k"), copNum("cop-gli-l", 1)],
      point: [copNum("cop-gli-px"), copNum("cop-gli-py"), copNum("cop-gli-pz")],
      glide: [copNum("cop-gli-tx", 0.5), copNum("cop-gli-ty"), copNum("cop-gli-tz")],
    };
  } else if (type === "rotoinversion") {
    params = {
      axis: [copNum("cop-riv-u"), copNum("cop-riv-v"), copNum("cop-riv-w", 1)],
      angle: copNum("cop-riv-angle", 90),
      center: [copNum("cop-riv-cx"), copNum("cop-riv-cy"), copNum("cop-riv-cz")],
    };
  } else if (type === "translation") {
    params = {
      vector: [copNum("cop-tra-x", 0.5), copNum("cop-tra-y", 0.5), copNum("cop-tra-z")],
    };
  } else if (type === "matrix") {
    params = {
      W: [
        copNum("cop-mat-w00",1), copNum("cop-mat-w01"), copNum("cop-mat-w02"),
        copNum("cop-mat-w10"), copNum("cop-mat-w11",1), copNum("cop-mat-w12"),
        copNum("cop-mat-w20"), copNum("cop-mat-w21"), copNum("cop-mat-w22",1),
      ],
      t: [copNum("cop-mat-tx"), copNum("cop-mat-ty"), copNum("cop-mat-tz")],
    };
  }
  return {type, params, tolerance, request_id: Date.now()};
}

let copMatrix = null;        // {W_frac, t_frac, op_type, op_params}
let copSelectedAtoms = new Set();
let copAllUnmapped = [];

function displayCopResult(result, opType, opParams) {
  const div = document.getElementById("cop-result");
  copMatrix = null;
  copSelectedAtoms = new Set();
  copAllUnmapped = [];
  customUnmappedAtoms = new Set();
  if (!result) { div.hidden = true; return; }
  if (result.error) {
    div.className = "cop-result fail";
    div.innerHTML = `<strong>Error:</strong> ${result.error}`;
    div.hidden = false;
    return;
  }
  const ok = result.is_symmetry;
  div.className = "cop-result " + (ok ? "ok" : "fail");
  let html = ok
    ? `<strong>✓ All ${result.total} atoms map correctly — this IS a symmetry operation</strong>`
    : `<strong>✗ ${result.unmapped_count} / ${result.total} atoms do not map — NOT a symmetry operation</strong>`;

  if (!ok && result.unmapped && result.unmapped.length > 0) {
    copAllUnmapped = result.unmapped.map(u => u.source);
    customUnmappedAtoms = new Set(copAllUnmapped);
    html += `<div style="margin:8px 0 4px;font-size:12px;color:#94a3b8">Unmapped atoms are highlighted in PyVista. Use the shared Atoms and Animation panels to animate this custom operation.</div>`;
    html += `<div class="unmapped-list" id="cop-unmapped-list">`;
    for (const u of result.unmapped) {
      const frac = u.frac ? u.frac.map(v => v.toFixed(3)).join(", ") : "—";
      html += `<div>atom ${u.source}: <b>${u.element}</b>  →  (${frac})  nearest: ${u.distance.toFixed(3)} Å</div>`;
    }
    html += `</div>`;
  }
  if (result.W_frac && result.t_frac) {
    copMatrix = {W_frac: result.W_frac, t_frac: result.t_frac, op_type: opType || "matrix", op_params: opParams || {}, result};
    html += `<p id="cop-anim-msg" class="hint">Use Start with the current Atoms mode: Clear, selected atoms, Unit cell only, or Displayed all.</p>`;
  }
  div.innerHTML = html;
  div.hidden = false;
  renderAtoms();
  renderOperationDetails();
}

function currentAnimationAtoms() {
  const all = atoms.map(atom => atom.index);
  if (state.scope === "representative") return all.slice(0, 1);
  if (state.scope === "unit_cell") return all;
  if (state.scope === "displayed") return all;
  if (state.scope === "selected") return state.selected_atoms && state.selected_atoms.length ? state.selected_atoms : selectedAtomIndices();
  return all;
}

function currentAnimationUnitCellOnly() {
  return state.scope === "unit_cell" || state.scope === "representative" || state.scope === "selected";
}

function sendCurrentCustomAnimation(startPlaying = true) {
  const msg = document.getElementById("cop-anim-msg");
  if (!copMatrix) {
    if (msg) msg.textContent = "Check the custom operation first.";
    else document.getElementById("status").textContent = "Check the custom operation first.";
    return;
  }
  const indices = currentAnimationAtoms();
  if (!indices.length) {
    if (msg) msg.textContent = "No atoms selected.";
    return;
  }
  if (msg) msg.textContent = "";
  sendCopAnimate(indices, currentAnimationUnitCellOnly(), startPlaying);
}

async function sendCopAnimate(atomIndices, unitCellOnly = false, startPlaying = true) {
  if (!copMatrix || atomIndices.length === 0) {
    return;
  }
  const body = {
    custom_op_animate: {
      atom_indices: atomIndices,
      W_frac: copMatrix.W_frac,
      t_frac: copMatrix.t_frac,
      op_type: copMatrix.op_type,
      op_params: copMatrix.op_params,
      unit_cell_only: Boolean(unitCellOnly),
      animate_id: Date.now(),
    },
    playing: Boolean(startPlaying),
  };
  await postState(body);
}

async function sendCopCheck() {
  const payload = buildCopPayload();
  const resultDiv = document.getElementById("cop-result");
  resultDiv.className = "cop-result";
  resultDiv.innerHTML = "Checking…";
  resultDiv.hidden = false;
  try {
    const result = await api("/api/check_operation", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    displayCopResult(result, payload.type, payload.params);
    // notify PyVista to highlight unmapped atoms
    state = await api("/api/state", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({custom_op_check_id: payload.request_id}),
    });
  } catch (err) {
    resultDiv.className = "cop-result fail";
    resultDiv.innerHTML = `<strong>Error:</strong> ${err}`;
  }
}

document.getElementById("btn-check-op").addEventListener("click", sendCopCheck);
document.getElementById("btn-clear-check").addEventListener("click", async () => {
  document.getElementById("cop-result").hidden = true;
  copMatrix = null;
  copSelectedAtoms = new Set();
  copAllUnmapped = [];
  customUnmappedAtoms = new Set();
  state = await api("/api/state", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({clear_custom_check: true}),
  });
  renderAtoms();
  renderOperationDetails();
});

async function boot() {
  const st = document.getElementById("status");
  st.textContent = "Connecting…";
  const [info, atomInfo, stateInfo] = await Promise.all([
    api("/api/operations"),
    api("/api/atoms"),
    api("/api/state"),
  ]);
  operations = info.operations;
  summariesReady = Boolean(info.summaries_ready);
  st.textContent = `Loaded ${operations.length} operations`;
  atoms = atomInfo.atoms;
  st.textContent = `Loaded ${operations.length} operations, ${atoms.length} atoms`;
  state = stateInfo;
  if (state.source_kind === "crystal" || state.source_kind === "molecule") {
    selectedStructureKind = state.source_kind;
  }
  sourceKind = state.source_kind || "crystal";
  setDefaultOperationSortForSourceKind();
  syncSourceKindControls();
  renderDirectionFilter();
  renderAtomElementFilter();
  renderElementColorControls();
  syncSpeedButtons();
  syncDisplayButtons();
  syncProjectionButtons();
  syncImproperModeControl();
  syncAtomModeButtons();
  syncPlayToggleButton();
  syncGifSavingControls();
  renderOperations();
  renderAtoms();
  renderStructureInfo();
  renderStatus();
  renderOperationDetails();
  setInterval(() => {
    refreshState().catch(error => {
      document.getElementById("status").textContent = `Refresh error: ${error}`;
    });
  }, 1000);
}
boot().catch(error => {
  document.getElementById("status").textContent = `Boot error: ${error}`;
});
</script>
</body>
</html>
"""

HTML = HTML.replace("__STRUCTURE_KIND_CONFIG__", source_kind_ui_config_json())
