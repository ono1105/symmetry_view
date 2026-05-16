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

import numpy as np
import imageio.v2 as imageio

from tools import view_json_pyvista as viewer
from tools.view_json_gui import NativePyVistaViewer


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
    .section-title {
      margin: 0 0 12px;
      font-size: 15px;
      color: #f8fafc;
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
  </div>
  <div class="grid">
    <section class="panel">
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
    <div class="side-stack">
      <section class="panel">
        <h2 class="section-title">Animation</h2>
        <div class="button-row flush">
          <button id="play">Play</button>
          <button id="stop" class="secondary">Stop</button>
          <button id="reset" class="secondary">Reset</button>
          <button id="view-direction" class="secondary">View along direction</button>
          <button id="save-gif" class="secondary">Save GIF</button>
        </div>
        <label>Speed</label>
        <div class="button-row flush" id="speed-controls">
          <button class="secondary speed-button" data-speed="0.5">Slow</button>
          <button class="secondary speed-button selected" data-speed="1.0">Normal</button>
          <button class="secondary speed-button" data-speed="2.0">Fast</button>
        </div>
        <p class="hint">Play the selected symmetry operation or align the camera to its axis, plane normal, or translation direction.</p>
        <h2 class="section-title">Display</h2>
        <label>Range</label>
        <div class="button-row flush" id="display-controls">
          <button class="secondary display-button selected" data-display-mode="source">Unit cell</button>
          <button class="secondary display-button" data-display-mode="expanded_quarter">±1/4</button>
          <button class="secondary display-button" data-display-mode="expanded_half">±1/2</button>
        </div>
        <h2 class="section-title">Camera</h2>
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
        <p class="hint">Enter an angle in degrees, then rotate the current camera view around the structure.</p>
      </section>
      <section class="panel">
        <h2 class="section-title">Atoms</h2>
        <label>Element filter</label>
        <div class="direction-filter-list" id="atom-element-filter"></div>
        <label>Animated atoms</label>
        <div class="atom-list" id="atoms"></div>
        <div class="button-row">
          <button id="all-atoms" class="secondary">All atoms</button>
          <button id="clear-atoms" class="secondary">Representative</button>
        </div>
        <p class="hint">Check atoms to animate only those atoms. Clear selection to return to representative mode.</p>
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
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = atom.index;
    checkbox.checked = selected.has(atom.index);
    checkbox.addEventListener("change", onAtomSelectionChange);
    const span = document.createElement("span");
    span.appendChild(renderHtml(text));
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
  document.getElementById("status").textContent =
    `state: ${state.playing ? "playing" : "stopped"}\\n` +
    `operation: ${operation ? stripHtml(optionText(operation)) : state.operation_index}\\n` +
    `speed: ${state.speed || 1.0}x\\n` +
    `display: ${state.display_mode || "source"}\\n` +
    `scope: ${state.scope || "representative"}\\n` +
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
  renderOperations();
  renderAtoms();
  renderStatus();
}

async function refreshState() {
  state = await api("/api/state");
  syncOperationSelection();
  syncSpeedButtons();
  syncDisplayButtons();
  renderStatus();
}

document.getElementById("operation-sort").addEventListener("change", renderOperations);
document.getElementById("play").addEventListener("click", () => postState({playing: true}));
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
document.getElementById("save-gif").addEventListener("click", () => {
  postState({gif_request_id: Date.now(), playing: false});
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
document.getElementById("all-atoms").addEventListener("click", () => {
  postState({selected_atoms: atoms.map(atom => atom.index), scope: "selected", playing: false, reset: true});
});
document.getElementById("clear-atoms").addEventListener("click", () => {
  postState({selected_atoms: [], scope: "representative", playing: false, reset: true});
});

async function boot() {
  const info = await api("/api/operations");
  operations = info.operations;
  const atomInfo = await api("/api/atoms");
  atoms = atomInfo.atoms;
  state = await api("/api/state");
  renderDirectionFilter();
  renderAtomElementFilter();
  syncSpeedButtons();
  syncDisplayButtons();
  renderOperations();
  renderAtoms();
  renderStatus();
  setInterval(refreshState, 500);
}
boot().catch(error => {
  document.getElementById("status").textContent = `Error: ${error}`;
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
        self.last_operation_index: int | None = None
        self.last_scope: str | None = None
        self.last_selected_atoms: tuple[int, ...] | None = None
        self.last_display_mode: str | None = self.display_mode
        self.last_view_request_id: int | None = None
        self.last_camera_request_id: int | None = None
        self.last_gif_request_id: int | None = None

    def add_controls(self) -> None:
        self.plotter.add_key_event("space", self.toggle_play_from_keyboard)
        self.plotter.add_key_event("r", self.reset_from_keyboard)

    def on_timer(self, step: int) -> None:
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
            view_request_id = self.shared_state.get("view_request_id")
            camera_request_id = self.shared_state.get("camera_request_id")
            camera_direction = str(self.shared_state.get("camera_direction", ""))
            camera_angle = float(self.shared_state.get("camera_angle", 90.0))
            gif_request_id = self.shared_state.get("gif_request_id")
            reset = bool(self.shared_state.pop("reset", False))

        self.speed = max(speed, 0.1)

        if operation_index != self.last_operation_index:
            self.set_operation_index(operation_index)
            self.last_operation_index = operation_index
            reset = True
            should_render = True
            should_update_status = True

        if scope != self.last_scope or selected_atoms != self.last_selected_atoms:
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
            self.rebuild_display_atoms(display_mode)
            self.last_display_mode = display_mode
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

        if requested_playing != self.playing:
            should_update_status = True
        self.playing = requested_playing
        if self.playing and self.paths:
            if self.frame_position >= self.frame_count - 1:
                self.frame_position = 0.0
            frame_step = self.speed * operation_speed_multiplier(self.current_operation())
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
        if operation_index not in self.element_actor_cache:
            cached = self.element_context_cache.get(operation_index)
            if cached is not None:
                axes, planes, centers = cached
                actors = viewer.add_symmetry_element_actors(
                    self.plotter,
                    self.render_data,
                    axes,
                    planes,
                    centers,
                )
            else:
                actors = viewer.add_symmetry_elements(
                    self.plotter,
                    self.render_data,
                    self.atom_mappings,
                    operation_index=operation_index,
                    element_index=None,
                )
            self.element_actor_cache[operation_index] = actors
        self.element_actors = self.element_actor_cache[operation_index]
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
            return
        direction = viewer.normalize(direction)
        center = scene_center(self.render_data)
        distance = max(viewer.scene_span(self.render_data) * 1.8, 1.0)
        up = camera_up_vector(direction)
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

    def save_current_gif(self) -> None:
        if not self.paths:
            self.set_gif_status("skipped: no animation path")
            return
        operation = self.current_operation()
        output_path = self.gif_output_path(operation)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        original_frame = float(self.frame_position)
        frames = max(self.frame_count // 2, 24)
        fps = 10.0 * max(self.speed, 0.1) * operation_speed_multiplier(operation)
        images = []
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
            else:
                self.set_gif_status("failed: no frames captured")
        except Exception as exc:
            self.set_gif_status(f"failed: {exc}")
        finally:
            self.frame_position = original_frame
            self.update_atoms(original_frame / max(self.frame_count - 1, 1))

    def gif_output_path(self, operation: dict) -> Path:
        stem = self.json_path.stem
        scope = self.scope or "representative"
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{stem}_op{int(operation['index']):03d}_{scope}_{timestamp}.gif"
        return self.json_path.parent / "checks" / "current" / filename

    def set_gif_status(self, status: str) -> None:
        with self.state_lock:
            self.shared_state["gif_status"] = status


def make_handler(
    operation_summaries: list[dict],
    atoms: list[dict],
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
                body = {
                    "operations": operation_summaries
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
            if path != "/api/state":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            allowed = {
                "operation_index",
                "playing",
                "reset",
                "selected_atoms",
                "speed",
                "display_mode",
                "scope",
                "view_request_id",
                "camera_request_id",
                "camera_direction",
                "camera_angle",
                "gif_request_id",
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
        "gif_status": "",
    }
    operation_summary_items, element_context_cache = operation_summaries(
        render_data,
        payload.get("atom_mappings"),
    )
    handler = make_handler(
        operation_summary_items,
        render_data["atoms"],
        shared_state,
        state_lock,
    )
    server = start_server(args.host, args.port, handler)
    url = f"http://{args.host}:{server.server_port}/"
    print(f"Control panel: {url}")
    if not args.no_browser:
        webbrowser.open(url)

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
