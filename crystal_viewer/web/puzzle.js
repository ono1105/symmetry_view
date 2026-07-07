import { PuzzleView } from "/static/puzzle_view.js";

// Puzzle: "how many-fold is this rotation axis?" (docs/PUZZLE_SPEC.md §3).
// Pick a molecule, one rotation axis is highlighted, choose every order that
// maps it onto itself (2/3/4/6), then check — the reveal spins the molecule.

let view = null;
let started = false;
let moleculeExamples = [];
let renderData = null;
let sceneSpan = 4;
let questions = [];
let currentQuestion = null;
let lastCorrectOrders = [];
let revealing = false;

function el(id) {
  return document.getElementById(id);
}

function formatFormula(text) {
  // Render a chemical formula with subscripted digit runs (C6H6 -> C₆H₆).
  return String(text).replace(/(\d+)/g, "<sub>$1</sub>");
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

function displayFormula(example) {
  return formatFormula(MOLECULAR_FORMULA[example.name] || example.formula || example.name);
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

async function buildPicker() {
  const catalog = await getJson("/api/examples");
  moleculeExamples = catalog.molecule || [];
  const root = el("puzzle-picker");
  root.innerHTML = "";
  const heading = document.createElement("h2");
  heading.className = "puzzle-picker-title";
  heading.textContent = "分子を選んでください";
  root.appendChild(heading);
  const list = document.createElement("div");
  list.className = "puzzle-picker-list";
  for (const example of moleculeExamples) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "puzzle-structure";
    button.innerHTML =
      `<span class="puzzle-structure-name">${displayFormula(example)}</span>` +
      `<span class="puzzle-structure-meta">${example.point_group || ""}</span>`;
    button.addEventListener("click", () => startStructure(example).catch(showError));
    list.appendChild(button);
  }
  root.appendChild(list);
}

function buildLegend(payload) {
  const legend = el("puzzle-legend");
  if (!legend) return;
  const atoms = (payload.render_data && payload.render_data.atoms) || payload.display_atoms || [];
  const styles = new Map((payload.atom_styles || []).map((s) => [Number(s.index), s]));
  const colors = new Map();
  for (const atom of atoms) {
    const style = styles.get(Number(atom.source_atom ?? atom.index));
    if (style && !colors.has(atom.element)) colors.set(atom.element, style.color);
  }
  legend.innerHTML = "";
  for (const [element, color] of colors) {
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
  el("puzzle-question").textContent = "読み込み中…";
  await getJson("/api/open_example", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind: "molecule", path: example.path, request_id: Date.now() }),
  });
  const [puzzlePayload, dataPayload] = await Promise.all([
    getJson("/api/puzzle/axis_orders"),
    getJson("/api/render_data"),
  ]);
  questions = puzzlePayload.questions || [];
  renderData = dataPayload.render_data || {};
  sceneSpan = view.sceneSpan(renderData);
  view.setMolecule(dataPayload);
  buildLegend(dataPayload);
  if (!questions.length) {
    el("puzzle-question").textContent = "この分子には出題できる回転軸がありません。別の分子を選んでください。";
    el("puzzle-options").innerHTML = "";
    el("puzzle-check").hidden = true;
    el("puzzle-again").hidden = true;
    el("puzzle-playback").hidden = true;
    return;
  }
  beginRound();
}

function beginRound() {
  currentQuestion = questions[Math.floor(Math.random() * questions.length)];
  view.showAxis(currentQuestion.direction_cart, currentQuestion.point_cart, sceneSpan);
  el("puzzle-question").textContent = "青い軸のまわりで、何回回すと重なりますか？（当てはまるものをすべて選ぶ）";
  const options = el("puzzle-options");
  options.innerHTML = "";
  for (const order of currentQuestion.options) {
    const label = document.createElement("label");
    label.className = "puzzle-option";
    label.innerHTML = `<input type="checkbox" value="${order}"><span>${order}回</span>`;
    options.appendChild(label);
  }
  const result = el("puzzle-result");
  result.hidden = true;
  el("puzzle-check").hidden = false;
  el("puzzle-check").disabled = false;
  el("puzzle-again").hidden = true;
  el("puzzle-playback").hidden = true; // reveal controls appear after answering
  el("puzzle-slider").value = "0";
  view.setRotationFraction(0);
}

function setSlider(fraction) {
  el("puzzle-slider").value = String(Math.round(fraction * 1000));
}

// Rotate up to the first overlap (360/n for the finest correct order) so the
// molecule lands back on the start markers. The slider (a full turn) still lets
// the user explore further. Playback drives the slider so they stay in sync.
async function playReveal() {
  if (revealing) return;
  revealing = true;
  el("puzzle-replay").disabled = true;
  try {
    setSlider(0);
    view.setRotationFraction(0);
    const target = lastCorrectOrders.length ? 1 / Math.max(...lastCorrectOrders) : 1;
    await view.playRotation(target, 1600, setSlider);
  } finally {
    revealing = false;
    el("puzzle-replay").disabled = false;
  }
}

function selectedOrders() {
  return [...el("puzzle-options").querySelectorAll("input:checked")].map((input) => Number(input.value));
}

async function onCheck() {
  if (!currentQuestion) return;
  el("puzzle-check").disabled = true;
  const result = await getJson("/api/puzzle/axis_orders/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_id: currentQuestion.id, selected_orders: selectedOrders() }),
  });
  const box = el("puzzle-result");
  box.hidden = false;
  box.className = `puzzle-result ${result.correct ? "hit" : "miss"}`;
  box.textContent = result.correct
    ? "正解"
    : `不正解（正解は ${result.correct_orders.map((o) => `${o}回`).join("・")}）`;
  lastCorrectOrders = result.correct_orders;
  el("puzzle-again").hidden = false;
  el("puzzle-playback").hidden = false;
  await playReveal();
}

function setupPlayControls() {
  el("puzzle-check").addEventListener("click", () => onCheck().catch(showError));
  el("puzzle-replay").addEventListener("click", () => playReveal().catch(showError));
  el("puzzle-slider").addEventListener("input", (event) => {
    view.setRotationFraction(Number(event.target.value) / 1000);
  });
  el("puzzle-again").addEventListener("click", () => {
    if (questions.length) beginRound();
  });
  el("puzzle-other").addEventListener("click", showHome);
}

window.addEventListener("symmetry-enter-puzzle", async () => {
  if (!started) {
    started = true;
    view = new PuzzleView(el("puzzle-view"));
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
