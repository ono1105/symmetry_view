import { StaticStructureView } from "/static/three_view.js";

// Puzzle: "how many-fold is this rotation axis?" (docs/PUZZLE_SPEC.md §3).
// The 3D view reuses the analysis-mode renderer (StaticStructureView), so atoms,
// the unit cell and the reveal animation match the analysis mode exactly. Pick a
// structure, one rotation axis is highlighted, choose its highest fold (the n of
// an n-fold axis: 2/3/4/6, or ∞ for a linear molecule), then check — the reveal
// replays that rotation operation's animation (periodic-aware, from the server).

let view = null;
let started = false;
let catalog = null;
let currentKind = "molecule";
let questions = [];
let currentQuestion = null;
let revealOperation = null; // operation index to animate, handed out on /check
let revealAnim = null; // active reveal animation token

const REVEAL_DURATION_MS = 1600;
const INFINITE = "inf";

function el(id) {
  return document.getElementById(id);
}

function formatFormula(text) {
  // Render a chemical formula with subscripted digit runs (C6H6 -> C₆H₆).
  return String(text).replace(/(\d+)/g, "<sub>$1</sub>");
}

function formatOrder(order) {
  return order === INFINITE ? "無限回" : `${order}回`;
}

// The catalog stores reduced formulae (benzene -> "HC"), which are wrong as
// molecular formulae. For the curated example molecules keep proper, familiar
// formulae; anything else falls back to the catalog value or the name.
const MOLECULAR_FORMULA = {
  water: "H2O",
  ammonia: "NH3",
  benzene: "C6H6",
  methane: "CH4",
  carbon_dioxide: "CO2",
  boron_trifluoride: "BF3",
  sulfur_hexafluoride: "SF6",
  xenon_tetrafluoride: "XeF4",
  allene: "C3H4",
  ethene: "C2H4",
  hydrogen_chloride: "HCl",
};

function displayLabel(example) {
  // Molecules keep a curated molecular formula; crystals use the catalog
  // (reduced) formula, which is the correct formula unit for them.
  const source = example.kind === "molecule" ? MOLECULAR_FORMULA[example.name] : null;
  return formatFormula(source || example.formula || example.name);
}

function showHome() {
  el("puzzle-picker").hidden = false;
  el("puzzle-play").hidden = true;
  el("puzzle-back").hidden = false; // return-to-selection lives on the home screen only
}

function showPlay() {
  el("puzzle-picker").hidden = true;
  el("puzzle-play").hidden = false;
  el("puzzle-back").hidden = true;
}

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error((await response.text()) || `${response.status} ${response.statusText}`);
  return response.json();
}

const STRUCTURE_KINDS = [
  { kind: "molecule", label: "分子" },
  { kind: "crystal", label: "結晶" },
];

async function buildPicker() {
  if (!catalog) catalog = await getJson("/api/examples");
  const root = el("puzzle-picker");
  root.innerHTML = "";

  const kindRow = document.createElement("div");
  kindRow.className = "puzzle-kind-row";
  for (const item of STRUCTURE_KINDS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `puzzle-kind${item.kind === currentKind ? " selected" : ""}`;
    button.textContent = item.label;
    button.addEventListener("click", () => {
      if (currentKind === item.kind) return;
      currentKind = item.kind;
      buildPicker();
    });
    kindRow.appendChild(button);
  }
  root.appendChild(kindRow);

  const heading = document.createElement("h2");
  heading.className = "puzzle-picker-title";
  heading.textContent = currentKind === "crystal" ? "結晶を選んでください" : "分子を選んでください";
  root.appendChild(heading);
  const list = document.createElement("div");
  list.className = "puzzle-picker-list";
  for (const example of catalog[currentKind] || []) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "puzzle-structure";
    // Only the name/formula — the point/space group would give the answer away.
    button.innerHTML = `<span class="puzzle-structure-name">${displayLabel(example)}</span>`;
    button.addEventListener("click", () => startStructure(example).catch(showError));
    list.appendChild(button);
  }
  root.appendChild(list);
}

function buildLegend() {
  // Reuse the element/colour list the shared view already computed.
  const legend = el("puzzle-legend");
  if (!legend) return;
  legend.innerHTML = "";
  for (const [element, color] of view.legendItems || []) {
    const item = document.createElement("span");
    item.className = "puzzle-legend-item";
    item.innerHTML = `<span class="puzzle-legend-swatch" style="background:${color}"></span>${element}`;
    legend.appendChild(item);
  }
}

function showError(error) {
  const result = el("puzzle-result");
  result.hidden = false;
  result.className = "puzzle-result miss";
  result.textContent = `エラー: ${error.message || error}`;
}

async function startStructure(example) {
  showPlay();
  // Name/formula only; the point/space group would reveal the axis order.
  el("puzzle-structure-title").innerHTML = displayLabel(example);
  el("puzzle-question").textContent = "読み込み中…";
  await getJson("/api/open_example", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind: example.kind, path: example.path, request_id: Date.now() }),
  });
  // Render the structure with the shared analysis-mode view (atoms + unit cell
  // for crystals + fitted camera), then fetch the axis questions for it.
  await view.refresh();
  buildLegend();
  const puzzlePayload = await getJson("/api/puzzle/axis_orders");
  questions = puzzlePayload.questions || [];
  if (!questions.length) {
    view.clearSymmetryElements();
    const noun = example.kind === "crystal" ? "結晶" : "分子";
    el("puzzle-question").textContent = `この${noun}には出題できる回転軸がありません。別の${noun}を選んでください。`;
    el("puzzle-options").innerHTML = "";
    el("puzzle-check").hidden = true;
    el("puzzle-again").hidden = true;
    el("puzzle-playback").hidden = true;
    return;
  }
  beginRound();
}

function beginRound() {
  cancelReveal();
  currentQuestion = questions[Math.floor(Math.random() * questions.length)];
  revealOperation = null;
  view.clearSymmetryElements();
  view.addAxis(
    { direction_cart: currentQuestion.direction_cart, point_cart: currentQuestion.point_cart },
    view.sceneSpan(),
  );
  view.resetAnimation();
  el("puzzle-question").textContent = "青い軸は何回回転軸ですか？";
  const options = el("puzzle-options");
  options.innerHTML = "";
  const choices = [...currentQuestion.options];
  if (currentQuestion.infinite) choices.push(INFINITE);
  for (const order of choices) {
    const label = document.createElement("label");
    label.className = "puzzle-option";
    label.innerHTML = `<input type="radio" name="puzzle-order" value="${order}"><span>${formatOrder(order)}</span>`;
    options.appendChild(label);
  }
  const result = el("puzzle-result");
  result.hidden = true;
  el("puzzle-check").hidden = false;
  el("puzzle-check").disabled = false;
  el("puzzle-again").hidden = true;
  el("puzzle-playback").hidden = true; // reveal controls appear after answering
  el("puzzle-slider").value = "0";
  el("puzzle-replay").disabled = false;
}

function setSlider(fraction) {
  el("puzzle-slider").value = String(Math.round(fraction * 1000));
}

// Drive the shared view's animation progress from 0 to 1 over the duration; this
// reuses StaticStructureView.applyAnimationProgress (periodic-aware). Returns a
// promise that resolves at the end or when cancelled (slider / next question).
function animateReveal() {
  cancelReveal();
  return new Promise((resolve) => {
    const token = { resolve, start: performance.now() };
    revealAnim = token;
    const step = (now) => {
      if (revealAnim !== token) return; // superseded/cancelled
      const t = Math.min((now - token.start) / REVEAL_DURATION_MS, 1);
      view.setAnimationProgress(t);
      setSlider(t);
      if (t >= 1) {
        revealAnim = null;
        resolve();
        return;
      }
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

function cancelReveal() {
  const anim = revealAnim;
  revealAnim = null;
  if (anim) anim.resolve();
}

// Load the answered fold's rotation operation and play its animation once.
async function playReveal() {
  if (revealOperation == null) return; // e.g. an infinite axis: nothing to play
  el("puzzle-replay").disabled = true;
  try {
    // Force "displayed" scope so the reveal animates every atom, even if the
    // analysis mode left a single-atom selection in the shared session.
    await view.loadAnimationPaths(Number(revealOperation), ++view.pathGeneration, "displayed");
    view.resetAnimation();
    await animateReveal();
  } finally {
    el("puzzle-replay").disabled = false;
  }
}

function selectedOrder() {
  const checked = el("puzzle-options").querySelector("input:checked");
  return checked ? checked.value : null;
}

async function onCheck() {
  if (!currentQuestion) return;
  const selected = selectedOrder();
  if (selected == null) {
    const result = el("puzzle-result");
    result.hidden = false;
    result.className = "puzzle-result miss";
    result.textContent = "回数を1つ選んでください。";
    return;
  }
  el("puzzle-check").disabled = true;
  const result = await getJson("/api/puzzle/axis_orders/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_id: currentQuestion.id, selected_order: selected }),
  });
  const box = el("puzzle-result");
  box.hidden = false;
  box.className = `puzzle-result ${result.correct ? "hit" : "miss"}`;
  box.textContent = result.correct ? "正解" : `不正解（正解は ${formatOrder(result.answer)}）`;
  revealOperation = result.reveal_operation;
  el("puzzle-again").hidden = false;
  if (revealOperation == null) {
    // Infinite axis (or no discrete rotation): no animation to show.
    el("puzzle-playback").hidden = true;
  } else {
    el("puzzle-playback").hidden = false;
    playReveal().catch(showError);
  }
}

function toggleProjection() {
  // The button shows the current projection; clicking switches to the other.
  const button = el("puzzle-projection");
  const next = button.dataset.projection === "perspective" ? "orthographic" : "perspective";
  view.setProjection(next);
  button.dataset.projection = next;
  button.textContent = next === "perspective" ? "透視投影" : "平行投影";
}

// Camera controls reuse StaticStructureView's own methods, the same ones the
// analysis-mode Simple camera tab drives.
const CAMERA_DIRECTIONS = {
  "puzzle-cam-left": "left",
  "puzzle-cam-right": "right",
  "puzzle-cam-up": "up",
  "puzzle-cam-down": "down",
  "puzzle-cam-roll-left": "roll-left",
  "puzzle-cam-roll-right": "roll-right",
};

function setupCameraControls() {
  for (const [id, direction] of Object.entries(CAMERA_DIRECTIONS)) {
    el(id).addEventListener("click", () => {
      view.rotateCamera(direction, Number(el("puzzle-cam-angle").value) || 0);
    });
  }
  el("puzzle-view-along").addEventListener("click", () => {
    if (!currentQuestion) return;
    // Look straight down the highlighted axis, centred on its point.
    view.viewAlongCartesianDirection(currentQuestion.direction_cart, currentQuestion.point_cart);
  });
}

function setupPlayControls() {
  el("puzzle-projection").addEventListener("click", toggleProjection);
  setupCameraControls();
  el("puzzle-check").addEventListener("click", () => onCheck().catch(showError));
  el("puzzle-replay").addEventListener("click", () => playReveal().catch(showError));
  el("puzzle-slider").addEventListener("input", (event) => {
    cancelReveal();
    view.setAnimationProgress(Number(event.target.value) / 1000);
  });
  el("puzzle-again").addEventListener("click", () => {
    if (questions.length) beginRound();
  });
  el("puzzle-other").addEventListener("click", showHome);
}

window.addEventListener("symmetry-enter-puzzle", async () => {
  if (!started) {
    started = true;
    view = new StaticStructureView(el("puzzle-view"));
    view.setBackgroundMode("light");
    setupPlayControls();
    try {
      await buildPicker();
    } catch (error) {
      showError(error);
    }
  } else if (view) {
    view.resize();
  }
});
