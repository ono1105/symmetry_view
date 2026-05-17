from __future__ import annotations

import argparse
import datetime as dt
import json
import threading
import webbrowser
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import _bootstrap  # noqa: F401

import logging
import numpy as np
import imageio.v2 as imageio
import pyvista as pv

from tools import view_json_pyvista as viewer
from tools.view_json_gui import NativePyVistaViewer

logging.getLogger("pyvista").setLevel(logging.ERROR)
logging.getLogger("vtkmodules").setLevel(logging.ERROR)


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
    .mode-button.selected {
      background: #7dd3fc;
      color: #081017;
    }
    .atom-mode-button.selected {
      background: #7dd3fc;
      color: #081017;
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
    <div class="button-row flush" id="mode-controls">
      <button class="secondary mode-button selected" data-mode="standard">Symmetry operation</button>
      <button class="secondary mode-button" data-mode="custom">Custom operation</button>
    </div>
  </div>
  <div class="grid">
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
          <label>Direction</label>
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
          <button id="play">Play</button>
          <button id="stop" class="secondary">Stop</button>
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
        <p class="hint">Play the selected operation and save the current view as a GIF.</p>
        <h2 class="section-title">Camera</h2>
        <div class="button-row flush">
          <button id="view-direction" class="secondary">View along direction</button>
          <button id="reset-view" class="secondary">Reset view center</button>
        </div>
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
        <p class="hint">Align to the selected axis, plane normal, or translation direction, then rotate the current view.</p>
        <h2 class="section-title">Display</h2>
        <label>Range</label>
        <div class="button-row flush" id="display-controls">
          <button class="secondary display-button selected" data-display-mode="source">Unit cell</button>
          <button class="secondary display-button" data-display-mode="expanded_quarter">±1/4</button>
          <button class="secondary display-button" data-display-mode="expanded_half">±1/2</button>
          <button class="secondary display-button" data-display-mode="expanded_0_75">±3/4</button>
          <button class="secondary display-button" data-display-mode="expanded_1_0">±1</button>
        </div>
      </section>
      <section class="panel">
        <h2 class="section-title">Atoms</h2>
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

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  if (response.status === 204) return null;
  return await response.json();
}

function optionText(operation) {
  const element = operation.element_summary ? ` | ${operation.element_summary}` : "";
  return `op ${operation.index}: ${formatSymbol(operation.display_symbol || operation.symbol)}${element}`;
}

function renderHtml(text) {
  const template = document.createElement("template");
  template.innerHTML = text;
  return template.content;
}

function formatSymbol(symbol) {
  return String(symbol)
    .replaceAll("_1", "₁")
    .replaceAll("_2", "₂")
    .replaceAll("_3", "₃")
    .replaceAll("_4", "₄")
    .replaceAll("_5", "₅")
    .replaceAll("_6", "₆");
}

function atomText(atom) {
  const frac = atom.frac_label ? ` frac=${atom.frac_label}` : "";
  const asym = atom.asymmetric_index === null || atom.asymmetric_index === undefined
    ? ""
    : ` asym=${atom.asymmetric_index}`;
  return `${atom.index}: ${atom.element}${frac}${asym}`;
}

function renderOperations() {
  const root = document.getElementById("operations");
  root.innerHTML = "";
  for (const operation of sortedOperations()) {
    if (directionFilterValue && operation.direction_sort_key !== directionFilterValue) continue;
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
  const directions = [...new Map(
    operations
      .filter(operation => operation.direction_sort_key && operation.direction_sort_key !== "none")
      .map(operation => [
        operation.direction_sort_key,
        operation.direction_label || operation.direction_filter_label || operation.direction_sort_key,
      ])
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
  for (const [value, label] of directions) {
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
  if (directionFilterValue && !directions.some(([value]) => value === directionFilterValue)) {
    directionFilterValue = "";
    renderDirectionFilter();
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
  return `${operation.display_symbol || operation.symbol || ""}`.replace(/_/g, "");
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
  if (Math.abs(r) < 1e-8) return "0";
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
  const W = op.matrix_frac;
  const t = op.translation_frac;
  if (!W || !t) { div.textContent = ""; return; }

  let lines = [];
  lines.push(`${stripHtml(optionText(op))}`);
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
    const span = document.createElement("span");
    span.appendChild(renderHtml(text));
    if (customUnmappedAtoms.has(atom.index)) {
      const badge = document.createElement("span");
      badge.className = "atom-badge";
      badge.textContent = "do not map";
      span.appendChild(badge);
    }
    label.appendChild(checkbox);
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

function syncAtomModeButtons() {
  const scope = state.scope || "representative";
  for (const button of document.querySelectorAll(".atom-mode-button")) {
    button.classList.toggle("selected", button.dataset.scope === scope);
  }
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
    `display: ${state.display_mode || "source"}\\n` +
    `scope: ${scopeLabel}\\n` +
    `selected atoms: ${selected}\\n` +
    `gif: ${state.gif_status || "-"}`;
}

async function postState(update) {
  state = await api("/api/state", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(update),
  });
  syncSpeedButtons();
  syncDisplayButtons();
  syncAtomModeButtons();
  renderOperations();
  renderAtoms();
  renderStatus();
  renderOperationDetails();
}

function setActiveMode(mode) {
  activeMode = mode === "custom" ? "custom" : "standard";
  document.getElementById("standard-panel").hidden = activeMode !== "standard";
  document.getElementById("custom-panel").hidden = activeMode !== "custom";
  for (const button of document.querySelectorAll(".mode-button")) {
    button.classList.toggle("selected", button.dataset.mode === activeMode);
  }
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
  state = await api("/api/state");
  syncOperationSelection();
  syncSpeedButtons();
  syncDisplayButtons();
  syncAtomModeButtons();
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
}

document.getElementById("operation-sort").addEventListener("change", renderOperations);
for (const button of document.querySelectorAll(".mode-button")) {
  button.addEventListener("click", () => setActiveMode(button.dataset.mode));
}
document.getElementById("play").addEventListener("click", () => {
  if (activeMode === "custom") {
    sendCurrentCustomAnimation(true);
    return;
  }
  postState({playing: true});
});
document.getElementById("stop").addEventListener("click", () => postState({playing: false}));
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
document.getElementById("view-direction").addEventListener("click", () => {
  postState({view_request_id: Date.now()});
});
document.getElementById("reset-view").addEventListener("click", () => {
  postState({reset_view_request_id: Date.now()});
});
document.getElementById("save-gif").addEventListener("click", () => {
  if (activeMode === "custom") {
    sendCurrentCustomAnimation(false);
    window.setTimeout(() => postState({gif_request_id: Date.now(), playing: false}), 120);
    return;
  }
  postState({gif_request_id: Date.now(), playing: false});
});
document.getElementById("save-gif-3view").addEventListener("click", () => {
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
    html += `<p id="cop-anim-msg" class="hint">Use Play with the current Atoms mode: Clear, selected atoms, Unit cell only, or Displayed all.</p>`;
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
  const info = await api("/api/operations");
  operations = info.operations;
  summariesReady = Boolean(info.summaries_ready);
  st.textContent = `Loaded ${operations.length} operations`;
  const atomInfo = await api("/api/atoms");
  atoms = atomInfo.atoms;
  st.textContent = `Loaded ${operations.length} operations, ${atoms.length} atoms`;
  state = await api("/api/state");
  renderDirectionFilter();
  renderAtomElementFilter();
  syncSpeedButtons();
  syncDisplayButtons();
  syncAtomModeButtons();
  renderOperations();
  renderAtoms();
  renderStatus();
  renderOperationDetails();
  setInterval(refreshState, 500);
}
boot().catch(error => {
  document.getElementById("status").textContent = `Boot error: ${error}`;
});
</script>
</body>
</html>
"""


class BrowserControlledViewer(NativePyVistaViewer):
    def __init__(
        self,
        *args,
        shared_state: dict,
        state_lock: threading.Lock,
        element_context_cache: dict[int, tuple[list[dict], list[dict], list[dict]]] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.shared_state = shared_state
        self.state_lock = state_lock
        self.element_context_cache = element_context_cache or {}
        # Disable VTK depth peeling to prevent transparency-related warning loops
        # on WSL/Mesa drivers. Translucent objects render without correct sorting
        # but without recursive PyVista→logging→VTK→PyVista error floods.
        try:
            for renderer in self.plotter.renderers:
                renderer.UseDepthPeelingOff()
        except Exception:
            pass
        self.last_operation_index: int | None = None
        self.last_scope: str | None = None
        self.last_selected_atoms: tuple[int, ...] | None = None
        self.last_display_mode: str | None = self.display_mode
        self.last_active_mode: str | None = None
        self.last_view_request_id: int | None = None
        self.last_reset_view_request_id: int | None = None
        self.last_camera_request_id: int | None = None
        self.last_gif_request_id: int | None = None
        self.last_gif_3view_request_id: int | None = None
        self.last_custom_op_check_id: object = None
        self.custom_check_actors: list = []
        self.custom_view_direction_cart: np.ndarray | None = None
        self.custom_focus_cart: np.ndarray | None = None
        self.custom_speed_multiplier: float = 1.0
        self.last_custom_op_animate_id: object = None
        self.using_custom_paths: bool = False

    def add_controls(self) -> None:
        self.plotter.add_key_event("space", self.toggle_play_from_keyboard)
        self.plotter.add_key_event("r", self.reset_from_keyboard)

    def on_timer(self, step: int) -> None:
        self._on_timer_inner(step)

    def _on_timer_inner(self, step: int) -> None:
        del step
        should_render = False
        should_update_status = False
        with self.state_lock:
            operation_index = int(self.shared_state["operation_index"])
            requested_playing = bool(self.shared_state["playing"])
            scope = str(self.shared_state.get("scope", "representative"))
            selected_atoms = tuple(int(index) for index in self.shared_state.get("selected_atoms", []))
            speed = float(self.shared_state.get("speed", 1.0))
            display_mode = str(self.shared_state.get("display_mode", self.display_mode))
            active_mode = str(self.shared_state.get("active_mode", "standard"))
            view_request_id = self.shared_state.get("view_request_id")
            reset_view_request_id = self.shared_state.get("reset_view_request_id")
            camera_request_id = self.shared_state.get("camera_request_id")
            camera_direction = str(self.shared_state.get("camera_direction", ""))
            camera_angle = float(self.shared_state.get("camera_angle", 90.0))
            gif_request_id = self.shared_state.get("gif_request_id")
            gif_3view_request_id = self.shared_state.get("gif_3view_request_id")
            custom_op_check_id = self.shared_state.get("custom_op_check_id")
            clear_custom_check = bool(self.shared_state.pop("clear_custom_check", False))
            custom_op_result = self.shared_state.get("custom_op_result")
            custom_op_animate = self.shared_state.get("custom_op_animate")
            reset = bool(self.shared_state.pop("reset", False))

        self.speed = max(speed, 0.1)

        if active_mode != self.last_active_mode:
            if active_mode == "custom":
                self.hide_element_actors()
                self.hide_start_markers()
            else:
                self.clear_custom_check_actors()
                if self.using_custom_paths:
                    self.using_custom_paths = False
                    self.build_paths()
                    reset = True
                self.show_element_actors(self.current_operation()["index"])
                self.update_start_markers()
            self.last_active_mode = active_mode
            should_render = True

        if operation_index != self.last_operation_index:
            self.set_operation_index(operation_index)
            self.last_operation_index = operation_index
            self.using_custom_paths = False
            if active_mode == "custom":
                self.hide_element_actors()
            reset = True
            should_render = True
            should_update_status = True

        if scope != self.last_scope or selected_atoms != self.last_selected_atoms:
            self.using_custom_paths = False
            self.scope = scope
            self.selected_atoms = selected_atoms
            self.build_paths()
            self.update_start_markers()
            self.last_scope = scope
            self.last_selected_atoms = selected_atoms
            reset = True
            should_render = True
            should_update_status = True

        if display_mode != self.last_display_mode:
            self.playing = False
            self.hide_element_actors()
            old_display_mode = self.display_mode
            self.rebuild_display_atoms(display_mode)
            self.last_display_mode = display_mode
            self.recenter_camera_for_display_mode(old_display_mode, display_mode)
            if active_mode == "standard":
                self.show_element_actors(self.current_operation()["index"])
            reset = True
            should_render = True
            should_update_status = True

        if reset:
            self.frame_position = 0.0
            self.update_atoms(0.0)
            should_render = True

        if view_request_id is not None and view_request_id != self.last_view_request_id:
            self.view_along_current_operation()
            self.last_view_request_id = view_request_id
            should_render = True

        if reset_view_request_id is not None and reset_view_request_id != self.last_reset_view_request_id:
            self.reset_view_center()
            self.last_reset_view_request_id = reset_view_request_id
            should_render = True

        if camera_request_id is not None and camera_request_id != self.last_camera_request_id:
            self.rotate_current_camera(camera_direction, camera_angle)
            self.last_camera_request_id = camera_request_id
            should_render = True

        if gif_request_id is not None and gif_request_id != self.last_gif_request_id:
            self.playing = False
            self.save_current_gif()
            self.last_gif_request_id = gif_request_id
            should_update_status = True
            should_render = True

        if gif_3view_request_id is not None and gif_3view_request_id != self.last_gif_3view_request_id:
            self.playing = False
            self.save_three_view_gifs()
            self.last_gif_3view_request_id = gif_3view_request_id
            should_update_status = True
            should_render = True

        if clear_custom_check:
            self.clear_custom_check_actors()
            self.using_custom_paths = False
            self.build_paths()
            with self.state_lock:
                self.shared_state["custom_op_result"] = None
                self.shared_state["custom_op_animate"] = None
            reset = True
            should_render = True
        elif custom_op_check_id is not None and custom_op_check_id != self.last_custom_op_check_id:
            self.last_custom_op_check_id = custom_op_check_id  # update first to prevent exception loops
            try:
                self.apply_custom_check(custom_op_result)
            except Exception as exc:
                self.clear_custom_check_actors()
                self.set_gif_status(f"check highlight failed: {exc}")
                should_update_status = True
            # New check discards any previous custom animation paths
            if self.using_custom_paths:
                self.using_custom_paths = False
                self.build_paths()
                reset = True
            should_render = True

        if custom_op_animate is not None:
            animate_id = custom_op_animate.get("animate_id")
            if animate_id != self.last_custom_op_animate_id:
                atom_indices = custom_op_animate.get("atom_indices", [])
                W_frac = np.asarray(custom_op_animate.get("W_frac"), dtype=float)
                t_frac = np.asarray(custom_op_animate.get("t_frac"), dtype=float)
                op_type = str(custom_op_animate.get("op_type", "matrix"))
                op_params = custom_op_animate.get("op_params") or {}
                unit_cell_only = bool(custom_op_animate.get("unit_cell_only", False))
                self.paths = self.build_custom_animation_paths(
                    atom_indices,
                    W_frac,
                    t_frac,
                    op_type=op_type,
                    op_params=op_params,
                    unit_cell_only=unit_cell_only,
                )
                self.using_custom_paths = True
                self.custom_speed_multiplier = custom_operation_speed_multiplier(op_type)
                self.last_custom_op_animate_id = animate_id
                self.update_start_markers()
                reset = True
                should_render = True

        if requested_playing != self.playing:
            should_update_status = True
        self.playing = requested_playing
        if self.playing and self.paths:
            if self.frame_position >= self.frame_count - 1:
                self.frame_position = 0.0
            multiplier = self.custom_speed_multiplier if self.using_custom_paths else operation_speed_multiplier(self.current_operation())
            frame_step = self.speed * multiplier
            self.frame_position = min(self.frame_position + frame_step, self.frame_count - 1)
            self.update_atoms(self.frame_position / max(self.frame_count - 1, 1))
            should_render = True
            if self.frame_position >= self.frame_count - 1:
                self.playing = False
                should_update_status = True

        with self.state_lock:
            self.shared_state["playing"] = self.playing

        if should_update_status:
            self.update_status()
            should_render = True
        if should_render:
            self.plotter.render()

    def set_operation_index(self, operation_index: int) -> None:
        for position, operation in enumerate(self.operations):
            if operation["index"] == operation_index:
                self.set_operation_position(position)
                return

    def show_element_actors(self, operation_index: int) -> None:
        cache_key = (operation_index, self.display_mode)
        if cache_key not in self.element_actor_cache:
            cached = self.element_context_cache.get(operation_index)
            if cached is not None:
                axes, planes, centers = cached
                actors = viewer.add_symmetry_element_actors(
                    self.plotter,
                    self.render_data,
                    axes,
                    planes,
                    centers,
                    display_mode=self.display_mode,
                )
            else:
                actors = viewer.add_symmetry_elements(
                    self.plotter,
                    self.render_data,
                    self.atom_mappings,
                    operation_index=operation_index,
                    element_index=None,
                    display_mode=self.display_mode,
                )
            self.element_actor_cache[cache_key] = actors
        self.element_actors = self.element_actor_cache[cache_key]
        for actor in self.element_actors:
            try:
                actor.SetVisibility(True)
            except Exception:
                pass

    def toggle_play_from_keyboard(self) -> None:
        with self.state_lock:
            self.shared_state["playing"] = not bool(self.shared_state["playing"])

    def reset_from_keyboard(self) -> None:
        with self.state_lock:
            self.shared_state["playing"] = False
            self.shared_state["reset"] = True

    def view_along_current_operation(self) -> None:
        basis = self.operation_camera_basis()
        if basis is None:
            return
        center, direction, up, distance = basis
        self.set_camera_view(center, direction, up, distance)

    def operation_camera_basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, float] | None:
        if self.custom_view_direction_cart is not None:
            direction = self.custom_view_direction_cart
            if np.linalg.norm(direction) < 1e-10:
                return None
            direction = viewer.normalize(direction)
            center = self.custom_focus_cart if self.custom_focus_cart is not None else self.display_center()
            distance = max(viewer.display_scene_span(self.render_data, self.display_mode) * 1.8, 1.0)
            up = camera_up_vector(direction)
            return center, direction, up, distance

        operation = self.current_operation()
        axes, planes, centers = self.element_context_cache.get(operation["index"], (None, None, None))
        if axes is None or planes is None or centers is None:
            axes, planes, centers = viewer.display_symmetry_elements(
                self.render_data,
                self.atom_mappings,
                operation["index"],
                element_index=None,
            )
        direction = None
        if is_pure_translation_operation(operation):
            direction = visual_translation_direction_cart(self.render_data, operation, self.atom_mappings)
        if direction is None:
            direction = operation_view_direction_cart(self.render_data, operation, axes, planes, centers)
        if direction is None:
            return None
        direction = viewer.normalize(direction)
        center = operation_focus_point_cart(self.render_data, operation, axes, planes, centers, self.display_mode)
        distance = max(viewer.display_scene_span(self.render_data, self.display_mode) * 1.8, 1.0)
        up = camera_up_vector(direction)
        return center, direction, up, distance

    def set_camera_view(self, center: np.ndarray, direction: np.ndarray, up: np.ndarray, distance: float) -> None:
        self.plotter.camera_position = [
            tuple(center + direction * distance),
            tuple(center),
            tuple(up),
        ]
        self.plotter.reset_camera_clipping_range()

    def rotate_current_camera(self, direction: str, angle_deg: float) -> None:
        angle = float(np.clip(angle_deg, 0.0, 180.0))
        if angle <= 1e-8:
            return
        position = np.asarray(self.plotter.camera.GetPosition(), dtype=float)
        focal_point = np.asarray(self.plotter.camera.GetFocalPoint(), dtype=float)
        up = viewer.normalize(np.asarray(self.plotter.camera.GetViewUp(), dtype=float))
        radius_vector = position - focal_point
        if np.linalg.norm(radius_vector) < 1e-10:
            return
        view_direction = viewer.normalize(focal_point - position)
        screen_right = viewer.normalize(np.cross(view_direction, up))
        if direction == "right":
            axis = up
            signed_angle = angle
        elif direction == "left":
            axis = up
            signed_angle = -angle
        elif direction == "up":
            axis = screen_right
            signed_angle = -angle
        elif direction == "down":
            axis = screen_right
            signed_angle = angle
        else:
            return

        rotated_radius = rotate_vector(radius_vector, axis, np.deg2rad(signed_angle))
        rotated_up = rotate_vector(up, axis, np.deg2rad(signed_angle))
        self.plotter.camera_position = [
            tuple(focal_point + rotated_radius),
            tuple(focal_point),
            tuple(viewer.normalize(rotated_up)),
        ]
        self.plotter.reset_camera_clipping_range()

    def display_center(self) -> np.ndarray:
        return viewer.display_scene_center(self.render_data, self.display_mode)

    def reset_view_center(self) -> None:
        new_center = self.display_center()
        position = np.asarray(self.plotter.camera.GetPosition(), dtype=float)
        focal_point = np.asarray(self.plotter.camera.GetFocalPoint(), dtype=float)
        up = viewer.normalize(np.asarray(self.plotter.camera.GetViewUp(), dtype=float))
        shift = new_center - focal_point
        self.plotter.camera_position = [
            tuple(position + shift),
            tuple(new_center),
            tuple(up),
        ]
        self.plotter.reset_camera_clipping_range()

    def recenter_camera_for_display_mode(self, old_display_mode: str, new_display_mode: str) -> None:
        old_center = viewer.display_scene_center(self.render_data, old_display_mode)
        new_center = viewer.display_scene_center(self.render_data, new_display_mode)
        shift = new_center - old_center
        if np.linalg.norm(shift) < 1e-10:
            return
        position = np.asarray(self.plotter.camera.GetPosition(), dtype=float)
        focal_point = np.asarray(self.plotter.camera.GetFocalPoint(), dtype=float)
        up = viewer.normalize(np.asarray(self.plotter.camera.GetViewUp(), dtype=float))
        self.plotter.camera_position = [
            tuple(position + shift),
            tuple(focal_point + shift),
            tuple(up),
        ]
        self.plotter.reset_camera_clipping_range()

    def save_current_gif(self, *, suffix: str | None = None, timestamp: str | None = None) -> bool:
        if not self.paths:
            self.set_gif_status("skipped: no animation path")
            return False
        operation = self.current_operation()
        output_path = self.gif_output_path(operation, custom=self.using_custom_paths, suffix=suffix, timestamp=timestamp)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        original_frame = float(self.frame_position)
        frames = max(self.frame_count // 2, 24)
        multiplier = self.custom_speed_multiplier if self.using_custom_paths else operation_speed_multiplier(operation)
        fps = 10.0 * max(self.speed, 0.1) * multiplier
        images = []
        saved = False
        self.set_gif_status(f"writing {output_path}")
        try:
            for frame in range(frames):
                s = frame / max(frames - 1, 1)
                self.update_atoms(s)
                self.plotter.render()
                image = self.plotter.screenshot(return_img=True)
                if image is not None:
                    images.append(image)
            if images:
                imageio.mimsave(output_path, images, fps=fps)
                self.set_gif_status(f"saved {output_path}")
                saved = True
            else:
                self.set_gif_status("failed: no frames captured")
        except Exception as exc:
            self.set_gif_status(f"failed: {exc}")
        finally:
            self.frame_position = original_frame
            self.update_atoms(original_frame / max(self.frame_count - 1, 1))
        return saved

    def save_three_view_gifs(self) -> None:
        if not self.paths:
            self.set_gif_status("skipped: no animation path")
            return
        basis = self.operation_camera_basis()
        if basis is None:
            self.set_gif_status("skipped: no view direction")
            return

        center, front_direction, front_up, distance = basis
        front_direction = viewer.normalize(front_direction)
        front_up = viewer.normalize(front_up)
        right_direction = viewer.normalize(np.cross(front_direction, front_up))
        top_direction = front_up
        top_up = viewer.normalize(-front_direction)
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        original_camera_position = self.plotter.camera_position
        views = [
            ("front", front_direction, front_up),
            ("right", right_direction, front_up),
            ("top", top_direction, top_up),
        ]
        failed_labels = []
        try:
            for label, direction, up in views:
                self.set_camera_view(center, direction, up, distance)
                if not self.save_current_gif(suffix=label, timestamp=timestamp):
                    failed_labels.append(label)
            if failed_labels:
                self.set_gif_status(f"3-view GIF incomplete; failed: {', '.join(failed_labels)}")
            else:
                self.set_gif_status(f"saved 3-view GIFs ({timestamp})")
        finally:
            self.plotter.camera_position = original_camera_position
            self.plotter.reset_camera_clipping_range()

    def gif_output_path(
        self,
        operation: dict,
        *,
        custom: bool = False,
        suffix: str | None = None,
        timestamp: str | None = None,
    ) -> Path:
        stem = self.json_path.stem
        scope = self.scope or "representative"
        timestamp = timestamp or dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        op_label = "custom" if custom else f"op{int(operation['index']):03d}"
        suffix_part = f"_{suffix}" if suffix else ""
        filename = f"{stem}_{op_label}_{scope}{suffix_part}_{timestamp}.gif"
        return export_gif_dir(self.json_path) / stem / filename

    def set_gif_status(self, status: str) -> None:
        with self.state_lock:
            self.shared_state["gif_status"] = status

    def build_custom_animation_paths(
        self,
        atom_indices: list[int],
        W_frac: np.ndarray,
        t_frac: np.ndarray,
        *,
        op_type: str = "matrix",
        op_params: dict | None = None,
        unit_cell_only: bool = False,
    ) -> dict[int, dict]:
        """Build operation-aware animation paths for a user-supplied (W|t) operation."""
        unit_cell = self.render_data.get("unit_cell")
        if unit_cell is None:
            return {}
        lattice = np.asarray(unit_cell["lattice"], dtype=float)
        W_cart = lattice.T @ W_frac @ np.linalg.inv(lattice.T)
        t_cart = t_frac @ lattice
        op_params = op_params or {}

        # Build symmetry element dicts so build_operation_path can use arcs/reflections
        axis_dict: dict | None = None
        plane_dict: dict | None = None
        center_dict: dict | None = None

        if op_type in ("rotation", "screw"):
            uvw = np.asarray(op_params.get("axis", [0, 0, 1]), dtype=float)
            d_cart = viewer.normalize(uvw @ lattice)
            p_cart = np.asarray(op_params.get("point", [0, 0, 0]), dtype=float) @ lattice
            axis_dict = {"point_cart": p_cart.tolist(), "direction_cart": d_cart.tolist()}
        elif op_type in ("mirror", "glide"):
            hkl = np.asarray(op_params.get("normal", [0, 0, 1]), dtype=float)
            n_cart = viewer.normalize(np.linalg.inv(lattice) @ hkl)
            p_cart = np.asarray(op_params.get("point", [0, 0, 0]), dtype=float) @ lattice
            plane_dict = {"point_cart": p_cart.tolist(), "normal_cart": n_cart.tolist()}
        elif op_type == "inversion":
            c_cart = np.asarray(op_params.get("center", [0, 0, 0]), dtype=float) @ lattice
            center_dict = {"point_cart": c_cart.tolist()}
        elif op_type == "rotoinversion":
            uvw = np.asarray(op_params.get("axis", [0, 0, 1]), dtype=float)
            d_cart = viewer.normalize(uvw @ lattice)
            c_cart = np.asarray(op_params.get("center", [0, 0, 0]), dtype=float) @ lattice
            axis_dict = {"point_cart": c_cart.tolist(), "direction_cart": d_cart.tolist()}
            center_dict = {"point_cart": c_cart.tolist()}

        # Map to kind strings expected by build_operation_path
        _kind_map = {
            "rotation": "rotation_n",
            "screw": "screw_n",
            "mirror": "mirror",
            "glide": "glide",
            "inversion": "inversion",
            "rotoinversion": "rotoinversion_or_improper_n",
        }
        kind = _kind_map.get(op_type, "identity")
        angle_deg = float(op_params.get("angle", 90)) if op_params else 90.0
        fake_op = {"kind": kind, "angle_deg": angle_deg, "order": None, "matrix_cart": None}

        idx_set = set(int(i) for i in atom_indices)
        paths = {}
        for item in self.animated_atoms:
            atom = item["atom"]
            if atom["index"] not in idx_set:
                continue
            start = np.asarray(atom["cart"], dtype=float)
            target = W_cart @ start + t_cart
            path = viewer.build_operation_path(
                start, target, fake_op,
                axis=axis_dict, plane=plane_dict, center=center_dict,
            )
            if unit_cell_only:
                path["unit_cell_only"] = True
            paths[atom["index"]] = path
        return paths

    def apply_custom_check(self, result: dict | None) -> None:
        self.clear_custom_check_actors()
        if not result or result.get("error"):
            return

        elements = result.get("elements") or {}
        axes = elements.get("axes") or []
        planes = elements.get("planes") or []
        centers = elements.get("centers") or []
        if axes or planes or centers:
            self.custom_check_actors.extend(
                viewer.add_symmetry_element_actors(
                    self.plotter,
                    self.render_data,
                    axes,
                    planes,
                    centers,
                    display_mode=self.display_mode,
                )
            )
        direction = result.get("view_direction_cart")
        if direction is not None:
            self.custom_view_direction_cart = np.asarray(direction, dtype=float)
        self.custom_focus_cart = custom_focus_point_cart(result, self.render_data, self.display_mode)

        if not result.get("unmapped"):
            return
        unmapped_set = {item["source"] for item in result["unmapped"]}
        span = viewer.scene_span(self.render_data)
        for atom in self.render_data.get("atoms", []):
            if atom["index"] not in unmapped_set:
                continue
            center = np.asarray(atom["cart"], dtype=float)
            radius = viewer.atom_radius(atom["atomic_number"], span) * 1.28
            sphere = pv.Sphere(radius=radius, center=center, theta_resolution=24, phi_resolution=14)
            actor = self.plotter.add_mesh(
                sphere,
                color="#ff8a80",
                style="wireframe",
                line_width=1,
                opacity=0.55,
            )
            self.custom_check_actors.append(actor)

    def clear_custom_check_actors(self) -> None:
        for actor in self.custom_check_actors:
            try:
                self.plotter.remove_actor(actor)
            except Exception:
                pass
        self.custom_check_actors = []
        self.custom_view_direction_cart = None
        self.custom_focus_cart = None
        self.custom_speed_multiplier = 1.0


def make_handler(
    summaries_ref: list,
    atoms: list[dict],
    render_data: dict,
    shared_state: dict,
    state_lock: threading.Lock,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self.send_bytes(HTML.encode("utf-8"), content_type="text/html; charset=utf-8")
                return
            if path == "/api/operations":
                with state_lock:
                    ready = shared_state.get("summaries_ready", True)
                body = {
                    "operations": summaries_ref[0],
                    "summaries_ready": ready,
                }
                self.send_json(body)
                return
            if path == "/api/atoms":
                body = {
                    "atoms": [
                        {
                            "index": atom["index"],
                            "element": atom["element"],
                            "frac": atom.get("frac"),
                            "frac_label": atom_frac_label(atom),
                            "cart": atom.get("cart"),
                            "asymmetric_index": atom.get("asymmetric_index"),
                        }
                        for atom in atoms
                    ]
                }
                self.send_json(body)
                return
            if path == "/api/state":
                with state_lock:
                    body = dict(shared_state)
                self.send_json(body)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")

            if path == "/api/check_operation":
                unit_cell = render_data.get("unit_cell")
                if unit_cell is None:
                    self.send_json({"error": "No unit cell in render_data"})
                    return
                lattice = np.asarray(unit_cell["lattice"], dtype=float)
                op_type = str(payload.get("type", ""))
                params = payload.get("params", {})
                tolerance = float(payload.get("tolerance", 0.1))
                result = build_custom_operation_frac(op_type, params, lattice)
                if isinstance(result, str):
                    self.send_json({"error": result})
                    return
                W_frac, t_frac = result
                check_result = check_custom_operation(render_data, W_frac, t_frac, tolerance)
                visuals = custom_operation_visuals(op_type, params, lattice, W_frac, t_frac)
                # include the operation matrix so the browser can request animation
                check_result["W_frac"] = W_frac.tolist()
                check_result["t_frac"] = t_frac.tolist()
                check_result.update(visuals)
                # store result for PyVista highlight
                with state_lock:
                    shared_state["custom_op_result"] = check_result
                self.send_json(check_result)
                return

            if path != "/api/state":
                self.send_error(404)
                return

            allowed = {
                "operation_index",
                "playing",
                "reset",
                "selected_atoms",
                "speed",
                "display_mode",
                "active_mode",
                "scope",
                "view_request_id",
                "reset_view_request_id",
                "camera_request_id",
                "camera_direction",
                "camera_angle",
                "gif_request_id",
                "gif_3view_request_id",
                "custom_op_check_id",
                "clear_custom_check",
                "custom_op_animate",
            }
            with state_lock:
                for key, value in payload.items():
                    if key in allowed:
                        shared_state[key] = value
                body = dict(shared_state)
            self.send_json(body)

        def send_json(self, body: dict) -> None:
            self.send_bytes(json.dumps(body).encode("utf-8"), content_type="application/json")

        def send_bytes(self, body: bytes, *, content_type: str) -> None:
            try:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                return

        def log_message(self, *args) -> None:
            return

    return Handler


def open_url(url: str) -> None:
    """Open URL in the default browser.  On WSL, webbrowser.open() often fails
    because there is no Linux browser; use cmd.exe instead to open Windows Edge."""
    import platform
    import subprocess
    if "microsoft" in platform.uname().release.lower():
        try:
            subprocess.run(
                ["cmd.exe", "/c", "start", "", url],
                check=False,
                capture_output=True,
            )
            return
        except FileNotFoundError:
            pass
    webbrowser.open(url)


def start_server(host: str, port: int, handler: type[BaseHTTPRequestHandler]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def operation_exists(operations: list[dict], operation_index: int) -> bool:
    return any(operation["index"] == operation_index for operation in operations)


def operation_speed_multiplier(operation: dict) -> float:
    kind = str(operation.get("kind", ""))
    if kind == "mirror" or kind == "inversion" or "translation" in kind or "glide" in kind:
        return 2.0
    return 1.0


def custom_operation_speed_multiplier(op_type: str) -> float:
    if op_type in {"mirror", "inversion", "translation", "glide"}:
        return 2.0
    return 1.0


def export_gif_dir(json_path: Path) -> Path:
    if json_path.parent.name == "json" and json_path.parent.parent.name == "exports":
        return json_path.parent.parent / "gifs"
    if json_path.parent.name == "exports":
        return json_path.parent / "gifs"
    return json_path.parent / "gifs"


def rotation_matrix_from_axis_angle(axis: np.ndarray, angle: float) -> np.ndarray:
    """Rodrigues rotation formula. axis must be a unit vector."""
    c, s = np.cos(angle), np.sin(angle)
    t = 1.0 - c
    x, y, z = axis
    return np.array([
        [t*x*x + c,   t*x*y - s*z, t*x*z + s*y],
        [t*x*y + s*z, t*y*y + c,   t*y*z - s*x],
        [t*x*z - s*y, t*y*z + s*x, t*z*z + c  ],
    ])


def build_custom_operation_frac(
    op_type: str,
    params: dict,
    lattice: np.ndarray,
) -> tuple[np.ndarray, np.ndarray] | str:
    """
    Convert human-friendly parameters to (W_frac 3x3, t_frac 3D).
    lattice: 3x3 with rows = a,b,c vectors (pymatgen convention).
    Convention: x'_frac = W_frac @ x_frac + t_frac  (column vector, spglib-style).
    Returns error string on bad input.
    """
    try:
        inv_lt = np.linalg.inv(lattice.T)
        lt = lattice.T

        def w_from_cart(W_cart: np.ndarray) -> np.ndarray:
            return inv_lt @ W_cart @ lt

        if op_type == "identity":
            return np.eye(3), np.zeros(3)

        if op_type == "translation":
            t = np.asarray(params["vector"], dtype=float)
            return np.eye(3), t

        if op_type == "rotation":
            uvw = np.asarray(params["axis"], dtype=float)
            d_cart = uvw @ lattice
            if np.linalg.norm(d_cart) < 1e-10:
                return "Axis direction is zero vector"
            d_hat = d_cart / np.linalg.norm(d_cart)
            angle = np.deg2rad(float(params["angle"]))
            W_cart = rotation_matrix_from_axis_angle(d_hat, angle)
            W_frac = w_from_cart(W_cart)
            p = np.asarray(params.get("point", [0, 0, 0]), dtype=float)
            return W_frac, (np.eye(3) - W_frac) @ p

        if op_type == "mirror":
            hkl = np.asarray(params["normal"], dtype=float)
            # hkl = L @ n_cart  →  n_cart = inv(L) @ hkl
            n_cart = np.linalg.inv(lattice) @ hkl
            if np.linalg.norm(n_cart) < 1e-10:
                return "Plane normal is zero vector"
            n_hat = n_cart / np.linalg.norm(n_cart)
            W_cart = np.eye(3) - 2.0 * np.outer(n_hat, n_hat)
            W_frac = w_from_cart(W_cart)
            p = np.asarray(params.get("point", [0, 0, 0]), dtype=float)
            return W_frac, (np.eye(3) - W_frac) @ p

        if op_type == "inversion":
            c = np.asarray(params.get("center", [0, 0, 0]), dtype=float)
            W_frac = -np.eye(3)
            return W_frac, 2.0 * c

        if op_type == "screw":
            uvw = np.asarray(params["axis"], dtype=float)
            d_cart = uvw @ lattice
            if np.linalg.norm(d_cart) < 1e-10:
                return "Axis direction is zero vector"
            d_hat = d_cart / np.linalg.norm(d_cart)
            angle = np.deg2rad(float(params["angle"]))
            W_cart = rotation_matrix_from_axis_angle(d_hat, angle)
            W_frac = w_from_cart(W_cart)
            p = np.asarray(params.get("point", [0, 0, 0]), dtype=float)
            screw = np.asarray(params.get("screw", [0, 0, 0]), dtype=float)
            return W_frac, (np.eye(3) - W_frac) @ p + screw

        if op_type == "glide":
            hkl = np.asarray(params["normal"], dtype=float)
            n_cart = np.linalg.inv(lattice) @ hkl
            if np.linalg.norm(n_cart) < 1e-10:
                return "Plane normal is zero vector"
            n_hat = n_cart / np.linalg.norm(n_cart)
            W_cart = np.eye(3) - 2.0 * np.outer(n_hat, n_hat)
            W_frac = w_from_cart(W_cart)
            p = np.asarray(params.get("point", [0, 0, 0]), dtype=float)
            glide = np.asarray(params.get("glide", [0, 0, 0]), dtype=float)
            return W_frac, (np.eye(3) - W_frac) @ p + glide

        if op_type == "rotoinversion":
            uvw = np.asarray(params["axis"], dtype=float)
            d_cart = uvw @ lattice
            if np.linalg.norm(d_cart) < 1e-10:
                return "Axis direction is zero vector"
            d_hat = d_cart / np.linalg.norm(d_cart)
            angle = np.deg2rad(float(params["angle"]))
            W_rot_cart = rotation_matrix_from_axis_angle(d_hat, angle)
            W_cart = -W_rot_cart  # rotoinversion = rotation then inversion
            W_frac = w_from_cart(W_cart)
            c = np.asarray(params.get("center", [0, 0, 0]), dtype=float)
            return W_frac, (np.eye(3) - W_frac) @ c

        if op_type == "matrix":
            W_frac = np.asarray(params["W"], dtype=float).reshape(3, 3)
            t_frac = np.asarray(params["t"], dtype=float)
            return W_frac, t_frac

        return f"Unknown operation type: {op_type!r}"

    except (KeyError, ValueError, TypeError) as exc:
        return f"Parameter error: {exc}"


def custom_operation_visuals(
    op_type: str,
    params: dict,
    lattice: np.ndarray,
    W_frac: np.ndarray,
    t_frac: np.ndarray,
) -> dict:
    axes: list[dict] = []
    planes: list[dict] = []
    centers: list[dict] = []
    view_direction: np.ndarray | None = None

    try:
        if op_type in ("rotation", "screw"):
            uvw = np.asarray(params.get("axis", [0, 0, 1]), dtype=float)
            direction = uvw @ lattice
            if np.linalg.norm(direction) >= 1e-10:
                point = np.asarray(params.get("point", [0, 0, 0]), dtype=float) @ lattice
                direction = viewer.normalize(direction)
                axes.append(
                    {
                        "label": "custom axis",
                        "point_cart": point.tolist(),
                        "direction_cart": direction.tolist(),
                    }
                )
                view_direction = direction

        elif op_type in ("mirror", "glide"):
            hkl = np.asarray(params.get("normal", [0, 0, 1]), dtype=float)
            normal = np.linalg.inv(lattice) @ hkl
            if np.linalg.norm(normal) >= 1e-10:
                point = np.asarray(params.get("point", [0, 0, 0]), dtype=float) @ lattice
                normal = viewer.normalize(normal)
                basis1, basis2 = plane_basis_from_normal(normal)
                planes.append(
                    {
                        "label": "custom plane",
                        "point_cart": point.tolist(),
                        "normal_cart": normal.tolist(),
                        "basis1_cart": basis1.tolist(),
                        "basis2_cart": basis2.tolist(),
                    }
                )
                view_direction = normal

        elif op_type == "inversion":
            center = np.asarray(params.get("center", [0, 0, 0]), dtype=float) @ lattice
            centers.append({"label": "custom center", "point_cart": center.tolist()})

        elif op_type == "rotoinversion":
            uvw = np.asarray(params.get("axis", [0, 0, 1]), dtype=float)
            direction = uvw @ lattice
            center = np.asarray(params.get("center", [0, 0, 0]), dtype=float) @ lattice
            centers.append({"label": "custom center", "point_cart": center.tolist()})
            if np.linalg.norm(direction) >= 1e-10:
                direction = viewer.normalize(direction)
                axes.append(
                    {
                        "label": "custom axis",
                        "point_cart": center.tolist(),
                        "direction_cart": direction.tolist(),
                    }
                )
                view_direction = direction

        elif op_type == "translation":
            direction = np.asarray(t_frac, dtype=float) @ lattice
            if np.linalg.norm(direction) >= 1e-10:
                view_direction = direction

        elif op_type == "matrix":
            direction = np.asarray(t_frac, dtype=float) @ lattice
            if np.linalg.norm(direction) >= 1e-10:
                view_direction = direction

    except (KeyError, ValueError, TypeError, np.linalg.LinAlgError):
        pass

    return {
        "elements": {
            "axes": axes,
            "planes": planes,
            "centers": centers,
        },
        "view_direction_cart": None if view_direction is None else np.asarray(view_direction, dtype=float).tolist(),
    }


def plane_basis_from_normal(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    normal = viewer.normalize(np.asarray(normal, dtype=float))
    trial = np.array([1.0, 0.0, 0.0])
    if abs(float(np.dot(trial, normal))) > 0.85:
        trial = np.array([0.0, 1.0, 0.0])
    basis1 = viewer.normalize(np.cross(normal, trial))
    basis2 = viewer.normalize(np.cross(normal, basis1))
    return basis1, basis2


def check_custom_operation(
    render_data: dict,
    W_frac: np.ndarray,
    t_frac: np.ndarray,
    tolerance_cart: float = 0.1,
) -> dict:
    """
    Apply (W_frac, t_frac) to atoms in the exported unit cell only.
    For each transformed position, check if a same-element atom is within tolerance_cart.
    """
    atoms = [
        atom for atom in render_data.get("atoms", [])
        if atom.get("frac") is not None
    ]
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return {"error": "No unit cell — molecule mode not supported for custom operation check"}

    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    validity_error = custom_matrix_validity_error(W_frac, lattice)
    if validity_error is not None:
        return {"error": validity_error}

    fracs = {}
    for atom in atoms:
        frac = atom.get("frac")
        if frac is not None:
            fracs[atom["index"]] = np.asarray(frac, dtype=float)

    mapped = []
    unmapped = []
    for atom in atoms:
        frac = fracs.get(atom["index"])
        if frac is None:
            continue

        x_prime = W_frac @ frac + t_frac
        # wrap to [0,1)
        x_prime_w = x_prime - np.floor(x_prime + 1e-9)

        best_dist = float("inf")
        best_idx = None
        for other in atoms:
            if other["element"] != atom["element"]:
                continue
            other_frac = fracs.get(other["index"])
            if other_frac is None:
                continue
            delta = x_prime_w - other_frac
            delta -= np.round(delta)
            dist = float(np.linalg.norm(delta @ lattice))
            if dist < best_dist:
                best_dist = dist
                best_idx = other["index"]

        if best_dist <= tolerance_cart:
            mapped.append({
                "source": atom["index"],
                "target": best_idx,
                "element": atom["element"],
                "distance": round(best_dist, 6),
            })
        else:
            unmapped.append({
                "source": atom["index"],
                "element": atom["element"],
                "frac": [round(float(v), 4) for v in x_prime_w],
                "distance": round(best_dist, 6),
            })

    return {
        "is_symmetry": len(unmapped) == 0,
        "total": len(atoms),
        "mapped_count": len(mapped),
        "unmapped_count": len(unmapped),
        "unmapped": unmapped,
        "tolerance_cart": tolerance_cart,
    }


def custom_matrix_validity_error(W_frac: np.ndarray, lattice: np.ndarray) -> str | None:
    W_frac = np.asarray(W_frac, dtype=float)
    if W_frac.shape != (3, 3) or not np.all(np.isfinite(W_frac)):
        return "Operation matrix W must be a finite 3x3 matrix"
    try:
        W_cart = lattice.T @ W_frac @ np.linalg.inv(lattice.T)
    except np.linalg.LinAlgError:
        return "Unit-cell lattice is singular"
    determinant = float(np.linalg.det(W_cart))
    if abs(abs(determinant) - 1.0) > 1e-5:
        return "Operation matrix must preserve volume (determinant must be ±1)"
    metric = W_cart.T @ W_cart
    if not np.allclose(metric, np.eye(3), atol=1e-5):
        return "Operation matrix must preserve distances; scaling/shear is not a symmetry operation"
    return None


def operation_summaries(
    render_data: dict,
    atom_mappings: dict | None,
) -> tuple[list[dict], dict[int, tuple[list[dict], list[dict], list[dict]]]]:
    summaries = []
    element_context_cache = {}
    for operation in render_data["operations"]:
        summary_operation = dict(operation)
        visual_translation = visual_translation_direction_cart(render_data, operation, atom_mappings)
        if visual_translation is not None:
            summary_operation["_display_translation_cart"] = visual_translation.tolist()
        axes, planes, centers = viewer.display_symmetry_elements(
            render_data,
            atom_mappings,
            operation["index"],
            element_index=None,
        )
        element_context_cache[operation["index"]] = (axes, planes, centers)
        summaries.append(
            {
                "index": operation["index"],
                "label": operation["label"],
                "symbol": operation.get("symbol") or operation["label"],
                "display_symbol": display_operation_symbol(render_data, summary_operation, axes),
                "kind": operation["kind"],
                "order": operation.get("order"),
                "angle_deg": operation.get("angle_deg"),
                "element_summary": operation_element_summary(render_data, summary_operation, axes, planes, centers),
                "element_sort_key": operation_element_sort_key(render_data, summary_operation, axes, planes, centers),
                "direction_sort_key": operation_direction_sort_key(render_data, summary_operation, axes, planes, centers),
                "direction_label": operation_direction_label(render_data, summary_operation, axes, planes, centers),
                "direction_filter_label": operation_direction_filter_label(render_data, summary_operation, axes, planes, centers),
                "matrix_frac": operation.get("matrix_frac"),
                "translation_frac": operation.get("translation_frac"),
                "matrix_cart": operation.get("matrix_cart"),
                "translation_cart": operation.get("translation_cart"),
            }
        )
    return summaries, element_context_cache


def display_operation_symbol(render_data: dict, operation: dict, axes: list[dict]) -> str:
    symbol = operation.get("symbol") or operation["label"]
    if is_pure_translation_operation(operation):
        return "t"
    if "?" not in str(symbol):
        return str(symbol)
    if not str(operation["kind"]).startswith("screw") or not axes:
        return str(symbol)
    inferred = infer_screw_symbol(render_data, operation, axes[0])
    return inferred or str(symbol)


def infer_screw_symbol(render_data: dict, operation: dict, axis: dict) -> str | None:
    order = operation.get("order")
    matrix = operation.get("matrix_cart")
    translation = operation.get("translation_cart")
    unit_cell = render_data.get("unit_cell")
    if order is None or matrix is None or translation is None or unit_cell is None:
        return None

    point = np.asarray(axis["point_cart"], dtype=float)
    direction = viewer.normalize(np.asarray(axis["direction_cart"], dtype=float))
    moved = np.asarray(matrix, dtype=float) @ point + np.asarray(translation, dtype=float)
    displacement = moved - point
    projected = float(np.dot(displacement, direction))

    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac_direction = direction @ np.linalg.inv(lattice)
    primitive_frac = integer_index_vector(frac_direction)
    if primitive_frac is None:
        return None
    period = float(np.linalg.norm(primitive_frac @ lattice))
    if period < 1e-10:
        return None

    fraction = (projected / period) % 1.0
    screw = int(round(fraction * int(order))) % int(order)
    if screw == 0:
        if int(order) == 2:
            return "2_1"
        return None
    return f"{order}_{screw}"


def operation_element_summary(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> str:
    parts = []
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        axis = effective_axis
        parts.append(
            f"{axis_direction_label(render_data, axis)} "
            f"@ {point_label(render_data, axis['point_cart'])}"
        )
    if planes:
        plane = planes[0]
        parts.append(
            f"{plane_normal_label(render_data, plane)} "
            f"@ {point_label(render_data, plane['point_cart'])}"
        )
    if centers and effective_axis is None:
        center = centers[0]
        parts.append(f"@ {point_label(render_data, center['point_cart'])}")
    translation_direction = translation_direction_label(render_data, operation)
    if translation_direction is not None and not parts:
        parts.append(translation_direction)
    return "; ".join(parts)


def operation_element_sort_key(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> str:
    direction = operation_direction_sort_key(render_data, operation, axes, planes, centers)
    point = operation_point_sort_key(render_data, operation, axes, planes, centers)
    return f"{direction}|{point}|{operation.get('symbol', '')}"


def operation_direction_sort_key(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> str:
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        return "axis:" + plain_index_label(axis_direction_label(render_data, effective_axis))
    if planes:
        return "plane:" + plain_index_label(plane_normal_label(render_data, planes[0]))
    translation_direction = translation_direction_label(render_data, operation)
    if translation_direction is not None:
        return "translation:" + plain_index_label(translation_direction)
    if centers:
        return "center"
    return "none"


def operation_direction_label(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> str:
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        return axis_direction_label(render_data, effective_axis)
    if planes:
        return plane_normal_label(render_data, planes[0])
    translation_direction = translation_direction_label(render_data, operation)
    if translation_direction is not None:
        return translation_direction
    if centers:
        return "center"
    return "none"


def operation_direction_filter_label(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> str:
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        return axis_direction_label_text(render_data, effective_axis)
    if planes:
        return plane_normal_label_text(render_data, planes[0])
    translation_direction = translation_direction_label_text(render_data, operation)
    if translation_direction is not None:
        return translation_direction
    if centers:
        return "center"
    return "none"


def operation_point_sort_key(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> str:
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        return point_sort_key(render_data, effective_axis["point_cart"])
    if planes:
        return point_sort_key(render_data, planes[0]["point_cart"])
    if centers:
        return point_sort_key(render_data, centers[0]["point_cart"])
    return ""


def operation_view_direction_cart(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> np.ndarray | None:
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        return np.asarray(effective_axis["direction_cart"], dtype=float)
    if planes:
        return np.asarray(planes[0]["normal_cart"], dtype=float)
    return translation_direction_cart(operation)


def operation_focus_point_cart(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
    display_mode: str,
) -> np.ndarray:
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        return display_point_cart(render_data, effective_axis["point_cart"], display_mode)
    if planes:
        return display_point_cart(render_data, planes[0]["point_cart"], display_mode)
    if centers:
        return display_point_cart(render_data, centers[0]["point_cart"], display_mode)
    return viewer.display_scene_center(render_data, display_mode)


def custom_focus_point_cart(result: dict, render_data: dict, display_mode: str) -> np.ndarray | None:
    elements = result.get("elements") or {}
    for key in ("axes", "planes", "centers"):
        items = elements.get(key) or []
        if items:
            return display_point_cart(render_data, items[0]["point_cart"], display_mode)
    return None


def display_point_cart(render_data: dict, point_cart: list[float] | np.ndarray, display_mode: str) -> np.ndarray:
    point = np.asarray(point_cart, dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return point
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac = point @ np.linalg.inv(lattice)
    if display_mode == "source":
        wrapped = frac - np.floor(frac + 1e-9)
    else:
        wrapped = frac - np.round(frac)
        wrapped = np.where(wrapped >= 0.5 - 1e-9, wrapped - 1.0, wrapped)
    return wrapped @ lattice


def visual_translation_direction_cart(
    render_data: dict,
    operation: dict,
    atom_mappings: dict | None,
) -> np.ndarray | None:
    if not is_pure_translation_operation(operation):
        return None
    mapping = viewer.selected_mapping(atom_mappings, operation["index"])
    if mapping is None:
        return None
    paths = viewer.animation_paths(
        render_data,
        operation,
        mapping,
        animation_scope="representative",
    )
    if not paths:
        return None
    path = next(iter(paths.values()))
    start = np.asarray(path["start"], dtype=float)
    target = np.asarray(path["target"], dtype=float)
    displacement = target - start
    if np.linalg.norm(displacement) < 1e-10:
        return None
    return displacement


def translation_direction_label(render_data: dict, operation: dict) -> str | None:
    direction = translation_direction_cart(operation)
    if direction is None:
        return None
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(direction, bracket=("[", "]"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac_direction = direction @ np.linalg.inv(lattice)
    return integer_index_label(frac_direction, bracket=("[", "]"), orient_positive=False)


def translation_direction_label_text(render_data: dict, operation: dict) -> str | None:
    direction = translation_direction_cart(operation)
    if direction is None:
        return None
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(direction, bracket=("[", "]"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac_direction = direction @ np.linalg.inv(lattice)
    return integer_index_label_text(frac_direction, bracket=("[", "]"), orient_positive=False)


def translation_direction_cart(operation: dict) -> np.ndarray | None:
    if not is_pure_translation_operation(operation):
        return None
    display_translation = operation.get("_display_translation_cart")
    if display_translation is not None:
        direction = np.asarray(display_translation, dtype=float)
        if np.linalg.norm(direction) >= 1e-10:
            return direction
    translation = operation.get("translation_cart")
    if translation is None:
        return None
    direction = np.asarray(translation, dtype=float)
    if np.linalg.norm(direction) < 1e-10:
        return None
    return direction


def is_pure_translation_operation(operation: dict) -> bool:
    kind = str(operation.get("kind", ""))
    if "translation" not in kind:
        return False
    matrix = operation.get("matrix_cart")
    if matrix is None:
        return True
    return bool(np.allclose(np.asarray(matrix, dtype=float), np.eye(3), atol=1e-8))


def point_sort_key(render_data: dict, point_cart: list[float]) -> str:
    point = np.asarray(point_cart, dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        values = point
    else:
        lattice = np.asarray(unit_cell["lattice"], dtype=float)
        values = point @ np.linalg.inv(lattice)
        values = values - np.floor(values + 1e-9)
    return ",".join(f"{float(value):.6f}" for value in values)


def plain_index_label(label: str) -> str:
    return (
        label.replace("<span class=\"overline\">", "-")
        .replace("</span>", "")
        .replace("[", "")
        .replace("]", "")
        .replace("(", "")
        .replace(")", "")
    )


def effective_axis_from_operation(operation: dict, centers: list[dict]) -> dict | None:
    kind = str(operation["kind"])
    if "rotoinversion" not in kind and "rotoreflection" not in kind and "improper" not in kind:
        return None
    if not centers:
        return None
    center = centers[0]
    axis = viewer.effective_rotation_axis(operation, None, center)
    return axis


def axis_direction_label(render_data: dict, axis: dict) -> str:
    vector = np.asarray(axis["direction_cart"], dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(vector, bracket=("[", "]"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac_direction = vector @ np.linalg.inv(lattice)
    return integer_index_label(frac_direction, bracket=("[", "]"))


def axis_direction_label_text(render_data: dict, axis: dict) -> str:
    vector = np.asarray(axis["direction_cart"], dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(vector, bracket=("[", "]"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac_direction = vector @ np.linalg.inv(lattice)
    return integer_index_label_text(frac_direction, bracket=("[", "]"))


def plane_normal_label(render_data: dict, plane: dict) -> str:
    normal = np.asarray(plane["normal_cart"], dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(normal, bracket=("(", ")"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    # frac @ lattice is the Cartesian point.  Plane coefficients in fractional
    # coordinates are therefore proportional to lattice @ normal_cart.
    hkl = lattice @ normal
    return integer_index_label(hkl, bracket=("(", ")"))


def plane_normal_label_text(render_data: dict, plane: dict) -> str:
    normal = np.asarray(plane["normal_cart"], dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(normal, bracket=("(", ")"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    hkl = lattice @ normal
    return integer_index_label_text(hkl, bracket=("(", ")"))


def point_label(render_data: dict, point_cart: list[float]) -> str:
    point = np.asarray(point_cart, dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(point, bracket=("(", ")"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac = point @ np.linalg.inv(lattice)
    wrapped = frac - np.floor(frac + 1e-9)
    return "(" + ", ".join(format_fraction(value) for value in wrapped) + ")"


def atom_frac_label(atom: dict) -> str | None:
    frac = atom.get("frac")
    if frac is None:
        return None
    return "(" + ", ".join(format_fraction(float(value)) for value in frac) + ")"


def integer_index_label(values: np.ndarray, *, bracket: tuple[str, str], orient_positive: bool = True) -> str:
    ints = integer_index_vector(values, orient_positive=orient_positive)
    if ints is None:
        return f"{bracket[0]}0 0 0{bracket[1]}"
    return bracket[0] + " ".join(format_index(int(value)) for value in ints) + bracket[1]


def integer_index_label_text(values: np.ndarray, *, bracket: tuple[str, str], orient_positive: bool = True) -> str:
    ints = integer_index_vector(values, orient_positive=orient_positive)
    if ints is None:
        return f"{bracket[0]}0 0 0{bracket[1]}"
    return bracket[0] + " ".join(format_index_text(int(value)) for value in ints) + bracket[1]


def integer_index_vector(values: np.ndarray, *, orient_positive: bool = True) -> np.ndarray | None:
    values = np.asarray(values, dtype=float)
    if np.linalg.norm(values) < 1e-10:
        return None
    normalized = values / np.max(np.abs(values))
    best = None
    for scale in range(1, 13):
        candidate = np.rint(normalized * scale).astype(int)
        if not np.any(candidate):
            continue
        error = np.linalg.norm(normalized - candidate / max(np.max(np.abs(candidate)), 1))
        if best is None or error < best[0]:
            best = (error, candidate)
        if error < 1e-5:
            break
    ints = best[1] if best is not None else np.rint(normalized).astype(int)
    gcd = int(np.gcd.reduce(np.abs(ints[np.nonzero(ints)]))) if np.any(ints) else 1
    ints = ints // max(gcd, 1)
    first = next((value for value in ints if value != 0), 0)
    if orient_positive and first < 0:
        ints = -ints
    return ints


def format_index(value: int) -> str:
    return f"<span class=\"overline\">{abs(value)}</span>" if value < 0 else str(value)


def format_index_text(value: int) -> str:
    return f"{abs(value)}\u0305" if value < 0 else str(value)


def format_fraction(value: float) -> str:
    value = float(value)
    if abs(value) < 1e-8 or abs(value - 1.0) < 1e-8:
        return "0"
    fraction = Fraction(value).limit_denominator(24)
    if abs(value - float(fraction)) < 2e-3:
        if fraction.denominator == 1:
            return str(fraction.numerator)
        return f"{fraction.numerator}/{fraction.denominator}"
    return f"{value:.3f}"


def vector_label(values: np.ndarray, *, bracket: tuple[str, str]) -> str:
    return bracket[0] + ", ".join(f"{float(value):.3f}" for value in values) + bracket[1]


def scene_center(render_data: dict) -> np.ndarray:
    atoms = render_data.get("atoms", [])
    if atoms:
        points = np.asarray([atom["cart"] for atom in atoms], dtype=float)
        return np.mean(points, axis=0)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is not None:
        lattice = np.asarray(unit_cell["lattice"], dtype=float)
        return np.asarray([0.5, 0.5, 0.5]) @ lattice
    return np.zeros(3)


def camera_up_vector(direction: np.ndarray) -> np.ndarray:
    direction = viewer.normalize(direction)
    candidates = [
        np.asarray([0.0, 0.0, 1.0]),
        np.asarray([0.0, 1.0, 0.0]),
        np.asarray([1.0, 0.0, 0.0]),
    ]
    up = min(candidates, key=lambda candidate: abs(float(np.dot(candidate, direction))))
    up = up - np.dot(up, direction) * direction
    return viewer.normalize(up)


def rotate_vector(vector: np.ndarray, axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = viewer.normalize(axis)
    vector = np.asarray(vector, dtype=float)
    return (
        vector * np.cos(angle_rad)
        + np.cross(axis, vector) * np.sin(angle_rad)
        + axis * np.dot(axis, vector) * (1.0 - np.cos(angle_rad))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Browser controls + PyVista view for exported symmetry JSON.")
    parser.add_argument("json_path", type=Path)
    parser.add_argument("--operation", type=int, default=None, help="Initial operation index.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5173)
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    parser.add_argument(
        "--expanded",
        action="store_true",
        help="Show quarter-cell periodic display clones. Slower, but useful for boundary checks.",
    )
    args = parser.parse_args()

    payload = json.loads(args.json_path.read_text(encoding="utf-8"))
    render_data = payload["render_data"]
    operations = render_data["operations"]
    first_operation = operations[0]["index"] if operations else 0
    initial_operation = args.operation if args.operation is not None and operation_exists(operations, args.operation) else first_operation
    display_mode = "expanded_quarter" if args.expanded else "source"

    state_lock = threading.Lock()
    initial_selected_atoms = [atom["index"] for atom in render_data["atoms"]]
    shared_state = {
        "operation_index": initial_operation,
        "playing": False,
        "reset": False,
        "scope": "selected",
        "selected_atoms": initial_selected_atoms,
        "speed": 1.0,
        "display_mode": display_mode,
        "active_mode": "standard",
        "gif_status": "",
        "gif_request_id": None,
        "gif_3view_request_id": None,
        "custom_op_check_id": None,
        "custom_op_result": None,
    }
    operation_summary_items, element_context_cache = operation_summaries(
        render_data,
        payload.get("atom_mappings"),
    )
    summaries_ref = [operation_summary_items]
    shared_state["summaries_ready"] = True

    handler = make_handler(
        summaries_ref,
        render_data["atoms"],
        render_data,
        shared_state,
        state_lock,
    )
    server = start_server(args.host, args.port, handler)
    url = f"http://{args.host}:{server.server_port}/"
    print(f"Control panel: {url}")
    if not args.no_browser:
        open_url(url)

    app = BrowserControlledViewer(
        args.json_path,
        display_mode=display_mode,
        initial_operation=initial_operation,
        scope=shared_state["scope"],
        shared_state=shared_state,
        state_lock=state_lock,
        element_context_cache=element_context_cache,
    )
    app.show()
    server.shutdown()
    server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
