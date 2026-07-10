import { StaticStructureView } from "/static/three_view.js";

// Puzzle mode (docs/PUZZLE_SPEC.md). Two quizzes share one flow — pick a quiz,
// pick a structure, answer — and both reuse the analysis-mode StaticStructureView
// so atoms, the unit cell and the (periodic-aware) animation match the analysis.
//   * "axis"      — a highlighted axis is shown; name its highest rotation fold.
//   * "operation" — one symmetry operation is animated; name its kind (+ fold).

let view = null;
let started = false;
let catalog = null;
let currentQuiz = "axis"; // "axis" | "operation"
let currentOperationDifficulty = "normal"; // "normal" | "hard"
let currentKind = "molecule"; // structure picker toggle
let currentSourceKind = "molecule"; // kind of the loaded structure (for answer options)
let questions = [];
let currentQuestion = null;
let revealOperation = null; // operation index to animate for the reveal
let revealAnim = null; // active reveal animation token
let roundGeneration = 0; // invalidates async work from prior rounds/screens
let operationAnswered = false;

const REVEAL_DURATION_MS = 1600;
const INFINITE = "inf";
const SHIFT_OPTIONS = ["1/6", "1/4", "1/3", "1/2", "2/3", "3/4", "5/6"];
const PUZZLE_CRYSTAL_EXAMPLES = new Set([
  "Antimony",
  "BaTiO3",
  "Bromine",
  "Cadmoselite",
  "Edgarite",
  "Ge Hf O4",
  "Halite",
  "Helium",
  "Manganese-beta",
  "NbP",
  "Qusongite",
  "Tellurium",
]);

// Operation-identify answer vocabulary (canonical kinds match game/operation_identify.py).
// `orders` lists the folds offered for that kind (null = kind only). The improper
// kind shown depends on the structure: molecules use rotoreflection Sn (回映),
// crystals use rotoinversion -n (回反).
const OP_KIND_MOLECULE = { kind: "rotoreflection", label: "回映", orders: [3, 4, 6] };
const OP_KIND_CRYSTAL = { kind: "rotoinversion", label: "回反", orders: [3, 4, 6] };

function operationKinds() {
  if (currentOperationDifficulty === "hard") {
    return [
      { kind: "screw", label: "らせん", orders: [2, 3, 4, 6] },
      { kind: "glide", label: "映進", orders: null },
    ];
  }
  // Linear molecules have a C∞ axis, so molecules offer ∞ as a rotation fold;
  // the crystallographic restriction means crystals never do.
  const rotationOrders = currentSourceKind === "crystal" ? [2, 3, 4, 6] : [2, 3, 4, 6, INFINITE];
  return [
    { kind: "rotation", label: "回転", orders: rotationOrders },
    { kind: "mirror", label: "鏡映", orders: null },
    { kind: "inversion", label: "反転", orders: null },
    currentSourceKind === "crystal" ? OP_KIND_CRYSTAL : OP_KIND_MOLECULE,
  ];
}

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

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatOperationNotation(notation) {
  return escapeHtml(notation).replace(/_([0-9]+)/g, "<sub>$1</sub>");
}

function formatOperationAnswer(kind, order, shift = null, notation = null) {
  let text = kind;
  if (kind === "rotation") text = `${order}回回転`;
  if (kind === "mirror") text = "鏡映";
  if (kind === "inversion") text = "反転";
  if (kind === "rotoreflection") text = `回映（S${order}）`;
  if (kind === "rotoinversion") text = `回反（-${order}）`;
  if (kind === "screw") text = `${order}回らせん`;
  if (kind === "glide") text = "映進";
  if (shift) text += `、並進成分 ${shift}`;
  const escaped = escapeHtml(text);
  return notation ? `${escaped}（${formatOperationNotation(notation)}）` : escaped;
}

function formatOperationAnswers(answers) {
  // Coincident motions accept more than one name (e.g. CO2: 反転 or 鏡映).
  return (answers || [])
    .map((a) => formatOperationAnswer(a.kind, a.order, a.shift, a.notation || a.symbol))
    .join(" または ");
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
  const source = example.kind === "molecule" ? MOLECULAR_FORMULA[example.name] : null;
  return formatFormula(source || example.formula || example.name);
}

// --- Screens: quiz select -> structure picker -> play ---

function showQuizSelect() {
  el("puzzle-quiz-select").hidden = false;
  el("puzzle-operation-difficulty").hidden = true;
  el("puzzle-picker-back").hidden = true;
  el("puzzle-picker").hidden = true;
  el("puzzle-play").hidden = true;
  el("puzzle-back").hidden = false;
}

function showOperationDifficulty() {
  roundGeneration += 1;
  cancelReveal();
  operationAnswered = false;
  el("puzzle-quiz-select").hidden = true;
  el("puzzle-operation-difficulty").hidden = false;
  el("puzzle-picker-back").hidden = false;
  el("puzzle-picker").hidden = true;
  el("puzzle-play").hidden = true;
  el("puzzle-back").hidden = false;
}

function showPicker() {
  roundGeneration += 1;
  cancelReveal();
  operationAnswered = false;
  el("puzzle-quiz-select").hidden = true;
  el("puzzle-operation-difficulty").hidden = true;
  el("puzzle-picker-back").hidden = false;
  el("puzzle-picker").hidden = false;
  el("puzzle-play").hidden = true;
  el("puzzle-back").hidden = false;
}

function showPlay() {
  el("puzzle-quiz-select").hidden = true;
  el("puzzle-operation-difficulty").hidden = true;
  el("puzzle-picker-back").hidden = true;
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
  const structureKinds =
    currentQuiz === "operation" && currentOperationDifficulty === "hard"
      ? STRUCTURE_KINDS.filter((item) => item.kind === "crystal")
      : STRUCTURE_KINDS;
  if (!structureKinds.some((item) => item.kind === currentKind)) {
    currentKind = structureKinds[0]?.kind || "molecule";
  }

  const kindRow = document.createElement("div");
  kindRow.className = "puzzle-kind-row";
  for (const item of structureKinds) {
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
  const examples = (catalog[currentKind] || []).filter(
    (example) => currentKind !== "crystal" || PUZZLE_CRYSTAL_EXAMPLES.has(example.name),
  );
  for (const example of examples) {
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

function showPrompt(message) {
  const result = el("puzzle-result");
  result.hidden = false;
  result.className = "puzzle-result miss";
  result.textContent = message;
}

async function startStructure(example) {
  const generation = ++roundGeneration;
  cancelReveal();
  operationAnswered = false;
  showPlay();
  // Name/formula only; the point/space group would reveal the answer.
  el("puzzle-structure-title").innerHTML = displayLabel(example);
  el("puzzle-question").textContent = "読み込み中…";
  await getJson("/api/open_example", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind: example.kind, path: example.path, request_id: Date.now() }),
  });
  if (generation !== roundGeneration) return;
  // Render with the shared analysis-mode view (atoms + unit cell + fitted camera).
  // Keep puzzle crystals to the unit-cell atoms; target markers show where the
  // operation sends them without moving extra periodic images.
  view.renderDataQuery = example.kind === "crystal" ? "?display_mode=source&boundary_images=0" : "";
  view.animationPathQuery = example.kind === "crystal" ? "&display_mode=source&boundary_images=0" : "";
  view.symmetryElementQuery = example.kind === "crystal" ? "&display_mode=source" : "";
  view.showAnimationTargets = example.kind === "crystal";
  await view.refresh();
  if (generation !== roundGeneration) return;
  buildLegend();
  const endpoint =
    currentQuiz === "axis"
      ? `/api/puzzle/axis_orders${example.kind === "crystal" ? "?display_mode=source" : ""}`
      : `/api/puzzle/operations?difficulty=${currentOperationDifficulty}`;
  const payload = await getJson(endpoint);
  if (generation !== roundGeneration) return;
  currentSourceKind = payload.source_kind || example.kind;
  questions = payload.questions || [];
  if (!questions.length) {
    view.clearSymmetryElements();
    const noun = example.kind === "crystal" ? "結晶" : "分子";
    const what =
      currentQuiz === "axis"
        ? "回転軸"
        : currentOperationDifficulty === "hard"
          ? "並進を含む操作（らせん・映進）"
          : "基本操作";
    el("puzzle-question").textContent = `この${noun}には出題できる${what}がありません。別の${noun}を選んでください。`;
    el("puzzle-options").innerHTML = "";
    el("puzzle-check").hidden = true;
    el("puzzle-again").hidden = true;
    el("puzzle-playback").hidden = true;
    return;
  }
  beginRound();
}

function pickQuestion() {
  // The operation quiz balances by answer type: a highly symmetric crystal has
  // many equivalent operations of the common kinds, so pick a random group
  // (opaque answer-type bucket) first, then a random question within it. The axis
  // quiz is already one-per-inequivalent-axis, so a plain random pick is fine.
  if (currentQuiz === "operation") {
    const groups = new Map();
    for (const question of questions) {
      const key = question.group ?? question.id;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(question);
    }
    const keys = [...groups.keys()];
    const bucket = groups.get(keys[Math.floor(Math.random() * keys.length)]);
    return bucket[Math.floor(Math.random() * bucket.length)];
  }
  return questions[Math.floor(Math.random() * questions.length)];
}

function beginRound() {
  roundGeneration += 1;
  cancelReveal();
  currentQuestion = pickQuestion();
  revealOperation = null;
  operationAnswered = false;
  view.clearSymmetryElements();
  view.resetAnimation();
  const result = el("puzzle-result");
  result.hidden = true;
  el("puzzle-options").innerHTML = "";
  el("puzzle-check").hidden = false;
  el("puzzle-check").disabled = false;
  el("puzzle-again").hidden = true;
  el("puzzle-slider").value = "0";
  el("puzzle-replay").disabled = false;
  if (currentQuiz === "axis") beginAxisRound();
  else beginOperationRound();
}

function beginAxisRound() {
  view.addAxis(
    { direction_cart: currentQuestion.direction_cart, point_cart: currentQuestion.point_cart },
    view.sceneSpan(),
  );
  el("puzzle-question").textContent = "青い軸は何回回転軸ですか？";
  const options = el("puzzle-options");
  const choices = [...currentQuestion.options];
  if (currentQuestion.infinite) choices.push(INFINITE);
  for (const order of choices) {
    const label = document.createElement("label");
    label.className = "puzzle-option";
    label.innerHTML = `<input type="radio" name="puzzle-order" value="${order}"><span>${formatOrder(order)}</span>`;
    options.appendChild(label);
  }
  el("puzzle-playback").hidden = true; // reveal controls appear after answering
}

function beginOperationRound() {
  el("puzzle-question").textContent =
    currentOperationDifficulty === "hard"
      ? "このアニメーションで示された対称操作の種類と並進成分を選んでください。"
      : "このアニメーションはどの操作ですか？";
  renderOperationOptions();
  // The animation IS the question, so show the playback controls and play it now.
  revealOperation = currentQuestion.operation_index;
  el("puzzle-playback").hidden = false;
  playReveal().catch(showError);
}

function renderOperationOptions() {
  const root = el("puzzle-options");
  const kinds = operationKinds();
  const kindRow = document.createElement("div");
  kindRow.className = "puzzle-op-group";
  kindRow.innerHTML = `<span class="puzzle-op-label">操作の種類</span>`;
  for (const { kind, label } of kinds) {
    const item = document.createElement("label");
    item.className = "puzzle-option";
    item.innerHTML = `<input type="radio" name="op-kind" value="${kind}"><span>${label}</span>`;
    kindRow.appendChild(item);
  }
  root.appendChild(kindRow);

  // The order row is always present (with reserved height) so selecting a kind
  // that needs a fold does not resize/shift the layout; only its contents change.
  const orderRow = document.createElement("div");
  orderRow.className = "puzzle-op-group puzzle-op-order";
  root.appendChild(orderRow);

  const shiftRow = document.createElement("div");
  shiftRow.className = "puzzle-op-group puzzle-op-order";
  if (currentOperationDifficulty === "hard") {
    shiftRow.hidden = true;
    shiftRow.innerHTML = `<span class="puzzle-op-label">並進成分</span>`;
    for (const shift of SHIFT_OPTIONS) {
      const item = document.createElement("label");
      item.className = "puzzle-option";
      item.innerHTML = `<input type="radio" name="op-shift" value="${shift}"><span>${shift}</span>`;
      shiftRow.appendChild(item);
    }
    root.appendChild(shiftRow);
  }

  kindRow.addEventListener("change", () => {
    const config = kinds.find((k) => k.kind === kindRow.querySelector("input:checked")?.value);
    orderRow.innerHTML = config?.orders ? `<span class="puzzle-op-label">回転次数</span>` : "";
    for (const order of config?.orders || []) {
      const item = document.createElement("label");
      item.className = "puzzle-option";
      item.innerHTML = `<input type="radio" name="op-order" value="${order}"><span>${formatOrder(order)}</span>`;
      orderRow.appendChild(item);
    }
    if (currentOperationDifficulty === "hard") {
      shiftRow.hidden = !(config?.kind === "screw" || config?.kind === "glide");
    }
  });
}

// --- Reveal animation (shared) ---

function setSlider(fraction) {
  el("puzzle-slider").value = String(Math.round(fraction * 1000));
}

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

async function playReveal() {
  if (revealOperation == null) return; // e.g. an infinite axis: nothing to play
  const generation = roundGeneration;
  el("puzzle-replay").disabled = true;
  try {
    // Override the shared analysis selection so puzzle rounds animate their own
    // displayed/unit-cell atoms consistently.
    await view.loadAnimationPaths(Number(revealOperation), ++view.pathGeneration, view.showAnimationTargets ? "unit_cell" : "displayed");
    if (generation !== roundGeneration) return;
    view.resetAnimation();
    await animateReveal();
    revealOperationElements(generation);
  } finally {
    if (generation === roundGeneration) el("puzzle-replay").disabled = false;
  }
}

function revealOperationElements(generation = roundGeneration) {
  if (!operationAnswered || generation !== roundGeneration || revealOperation == null) return;
  // Use the current path generation. If a replay supersedes this request, the
  // StaticStructureView guard discards it, and replay completion calls us again.
  view.loadSymmetryElements(Number(revealOperation), view.pathGeneration).catch(() => {});
}

// --- Checking answers ---

async function onCheck() {
  if (!currentQuestion) return;
  if (currentQuiz === "axis") return onCheckAxis();
  return onCheckOperation();
}

function selectedOrder() {
  const checked = el("puzzle-options").querySelector('input[name="puzzle-order"]:checked');
  return checked ? checked.value : null;
}

async function onCheckAxis() {
  const generation = roundGeneration;
  const selected = selectedOrder();
  if (selected == null) {
    showPrompt("回数を1つ選んでください。");
    return;
  }
  el("puzzle-check").disabled = true;
  const result = await getJson("/api/puzzle/axis_orders/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_id: currentQuestion.id, selected_order: selected }),
  });
  if (generation !== roundGeneration) return;
  const box = el("puzzle-result");
  box.hidden = false;
  box.className = `puzzle-result ${result.correct ? "hit" : "miss"}`;
  box.textContent = result.correct ? "正解" : `不正解（正解は ${formatOrder(result.answer)}）`;
  revealOperation = result.reveal_operation;
  el("puzzle-again").hidden = false;
  if (revealOperation == null) {
    el("puzzle-playback").hidden = true; // infinite axis: nothing to animate
  } else {
    el("puzzle-playback").hidden = false;
    playReveal().catch(showError);
  }
}

function selectedOperationAnswer() {
  const root = el("puzzle-options");
  const kind = root.querySelector('input[name="op-kind"]:checked')?.value || null;
  const orderInput = root.querySelector('input[name="op-order"]:checked');
  const shiftInput = root.querySelector('input[name="op-shift"]:checked');
  // Raw value ("2" or "inf"); the server normalises it.
  return {
    kind,
    order: orderInput ? orderInput.value : null,
    shift: shiftInput ? shiftInput.value : null,
  };
}

async function onCheckOperation() {
  const generation = roundGeneration;
  const { kind, order, shift } = selectedOperationAnswer();
  if (!kind) {
    showPrompt("操作の種類を選んでください。");
    return;
  }
  const config = operationKinds().find((k) => k.kind === kind);
  if (config?.orders && order == null) {
    showPrompt("回数も選んでください。");
    return;
  }
  if (currentOperationDifficulty === "hard" && shift == null) {
    showPrompt("並進成分も選んでください。");
    return;
  }
  el("puzzle-check").disabled = true;
  const result = await getJson("/api/puzzle/operations/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_id: currentQuestion.id, kind, order, shift, difficulty: currentOperationDifficulty }),
  });
  if (generation !== roundGeneration) return;
  const box = el("puzzle-result");
  box.hidden = false;
  box.className = `puzzle-result ${result.correct ? "hit" : "miss"}`;
  const answerText = formatOperationAnswers(result.answers);
  if (result.correct) {
    // When a motion carries more than one valid name, say so.
    box.innerHTML = result.answers.length > 1 ? `正解（${answerText} のいずれも正解）` : `正解（${answerText}）`;
  } else {
    box.innerHTML = `不正解（正解は ${answerText}）`;
  }
  el("puzzle-again").hidden = false;
  operationAnswered = true;
  // Reveal where the operation's symmetry element sits (axis / plane / centre /
  // glide arrow) now that the answer is in — the same elements the analysis shows.
  revealOperationElements(generation);
}

// --- Camera controls (reuse StaticStructureView's own methods) ---

const CAMERA_DIRECTIONS = {
  "puzzle-cam-left": "left",
  "puzzle-cam-right": "right",
  "puzzle-cam-up": "up",
  "puzzle-cam-down": "down",
  "puzzle-cam-roll-left": "roll-left",
  "puzzle-cam-roll-right": "roll-right",
};

function toggleProjection() {
  const button = el("puzzle-projection");
  const next = button.dataset.projection === "perspective" ? "orthographic" : "perspective";
  view.setProjection(next);
  button.dataset.projection = next;
  button.textContent = next === "perspective" ? "透視投影" : "平行投影";
}

function setupCameraControls() {
  for (const [id, direction] of Object.entries(CAMERA_DIRECTIONS)) {
    el(id).addEventListener("click", () => {
      view.rotateCamera(direction, Number(el("puzzle-cam-angle").value) || 0);
    });
  }
  el("puzzle-view-along").addEventListener("click", () => {
    // Only the axis quiz has a highlighted axis to look down.
    if (currentQuiz !== "axis" || !currentQuestion) return;
    view.viewAlongCartesianDirection(currentQuestion.direction_cart, currentQuestion.point_cart);
  });
}

function setupControls() {
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
  el("puzzle-other").addEventListener("click", showPicker);
  el("puzzle-picker-back").addEventListener("click", () => {
    if (currentQuiz === "operation" && el("puzzle-picker").hidden === false) {
      showOperationDifficulty();
    } else {
      showQuizSelect();
    }
  });
  for (const card of document.querySelectorAll("[data-quiz]")) {
    card.addEventListener("click", () => {
      currentQuiz = card.dataset.quiz;
      if (currentQuiz === "operation") {
        showOperationDifficulty();
      } else {
        buildPicker().then(showPicker).catch(showError);
      }
    });
  }
  for (const card of document.querySelectorAll("[data-operation-difficulty]")) {
    card.addEventListener("click", () => {
      currentOperationDifficulty = card.dataset.operationDifficulty || "normal";
      // Screw/glide exist only in crystals, so open the hard quiz on crystals.
      if (currentOperationDifficulty === "hard") currentKind = "crystal";
      buildPicker().then(showPicker).catch(showError);
    });
  }
}

window.addEventListener("symmetry-enter-puzzle", () => {
  if (!started) {
    started = true;
    view = new StaticStructureView(el("puzzle-view"));
    view.setBackgroundMode("light");
    setupControls();
  } else if (view) {
    view.resize();
  }
  showQuizSelect();
});
