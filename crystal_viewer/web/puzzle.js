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

function el(id) {
  return document.getElementById(id);
}

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error((await response.text()) || `${response.status} ${response.statusText}`);
  return response.json();
}

function difficultyStars(pointGroup) {
  const pg = String(pointGroup || "").trim();
  if (/^[OTI]/.test(pg)) return 3; // cubic / icosahedral: Oh, O, Td, Th, T, Ih, I
  if (/^D/.test(pg)) return 2; // dihedral: D6h, D4h, D3h, D2d, D∞h…
  return 1; // C-/S-groups
}

function starLabel(count) {
  return "★".repeat(count) + "☆".repeat(3 - count);
}

async function buildPicker() {
  const catalog = await getJson("/api/examples");
  moleculeExamples = (catalog.molecule || []).slice().sort(
    (a, b) => difficultyStars(a.point_group) - difficultyStars(b.point_group),
  );
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
      `<span class="puzzle-structure-name">${example.name}</span>` +
      `<span class="puzzle-structure-meta">${example.point_group || ""} ・ ` +
      `<span class="puzzle-stars">${starLabel(difficultyStars(example.point_group))}</span></span>`;
    button.addEventListener("click", () => startStructure(example).catch(showError));
    list.appendChild(button);
  }
  root.appendChild(list);
}

function showError(error) {
  const result = el("puzzle-result");
  result.hidden = false;
  result.className = "puzzle-result miss";
  result.textContent = `エラー: ${error.message || error}`;
}

async function startStructure(example) {
  el("puzzle-picker").hidden = true;
  el("puzzle-play").hidden = false;
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
  if (!questions.length) {
    el("puzzle-question").textContent = "この分子には出題できる回転軸がありません。別の分子を選んでください。";
    el("puzzle-options").innerHTML = "";
    el("puzzle-check").hidden = true;
    el("puzzle-again").hidden = true;
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
    ? `正解！ 正しくは ${result.correct_orders.map((o) => `${o}回`).join("・")} です。`
    : `おしい！ 正しくは ${result.correct_orders.map((o) => `${o}回`).join("・")} です。`;
  el("puzzle-again").hidden = false;
  // Reveal: spin the molecule once for each correct order.
  for (const order of result.correct_orders) {
    await view.playRotation(360 / order);
  }
}

function setupPlayControls() {
  el("puzzle-check").addEventListener("click", () => onCheck().catch(showError));
  el("puzzle-again").addEventListener("click", () => {
    if (questions.length) beginRound();
  });
  el("puzzle-other").addEventListener("click", () => {
    el("puzzle-play").hidden = true;
    el("puzzle-picker").hidden = false;
  });
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
