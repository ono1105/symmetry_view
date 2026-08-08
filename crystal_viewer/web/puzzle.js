import { StaticStructureView } from "/static/three_view.js";

// Puzzle mode (docs/PUZZLE_SPEC.md). Two quizzes share one flow — pick a quiz,
// pick a structure, answer — and both reuse the analysis-mode StaticStructureView
// so atoms, the unit cell and the (periodic-aware) animation match the analysis.
//   * "axis"      — a highlighted axis is shown; name its highest rotation fold.
//   * "operation" — one symmetry operation is animated; name its kind (+ fold).

let view = null;
let started = false;
let catalog = null;
let currentQuiz = "axis"; // "axis" | "operation" | "composition" | "mapping"
let currentOperationDifficulty = "normal"; // "normal" | "hard"
let currentKind = "molecule"; // structure picker toggle
let currentSourceKind = "molecule"; // kind of the loaded structure (for answer options)
let questions = [];
let currentQuestion = null;
let revealOperation = null; // operation index to animate for the reveal
let revealAnim = null; // active reveal animation token
let roundGeneration = 0; // invalidates async work from prior rounds/screens
let operationAnswered = false;
let mappingGuess = null; // mapping quiz: the atom the player clicked
let mappingRevealTarget = null; // mapping quiz: the correct target atom (after answering)
let compositionPlaybackGeneration = 0;
let compositionQuestionReady = false;
let mappingPlaybackGeneration = 0;
let mappingQuestionReady = false;

const REVEAL_DURATION_MS = 1600;
const INFINITE = "inf";
const SHIFT_OPTIONS = ["1/6", "1/4", "1/3", "1/2", "2/3", "3/4", "5/6"];
// Mapping quiz: ring colours (source / player's guess / correct target) and how
// far to preview the motion so the direction of a rotation is unambiguous while
// the final landing still has to be predicted.
const PICK_SOURCE_COLOR = 0xffd23f;
const PICK_GUESS_COLOR = 0x3d9be9;
const PICK_TARGET_COLOR = 0x35c46a;
const MAPPING_CURVED_PREVIEW = 0.18;
const MAPPING_STRAIGHT_PREVIEW = 0.10;
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
  // The kind label already spells out Sn / -n, so repeating the notation would
  // read "回映（S3）（S3）". Compare loosely so a unicode minus or stray spacing
  // in the notation still counts as the same text.
  const canonical =
    kind === "rotoreflection" ? `S${order}` : kind === "rotoinversion" ? `-${order}` : null;
  const normalize = (value) => String(value).replace(/\s+/g, "").replace(/[−–—]/g, "-");
  const redundantNotation = canonical !== null && normalize(notation) === normalize(canonical);
  return notation && !redundantNotation
    ? `${escaped}（${formatOperationNotation(notation)}）`
    : escaped;
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

function invalidatePuzzleWork() {
  roundGeneration += 1;
  compositionPlaybackGeneration += 1;
  mappingPlaybackGeneration += 1;
  compositionQuestionReady = false;
  mappingQuestionReady = false;
  cancelReveal();
  operationAnswered = false;
  currentQuestion = null;
  if (view) {
    view.pathGeneration += 1;
    view.animationPaths.clear();
    view.setAnimationSourceAtoms(null);
    view.onAtomPick = null;
    view.clearPickMarkers();
    view.clearTargetMarkers();
    view.clearSymmetryElements();
    view.resetAnimation();
  }
  return roundGeneration;
}

function showQuizSelect() {
  invalidatePuzzleWork();
  el("puzzle-quiz-select").hidden = false;
  el("puzzle-operation-difficulty").hidden = true;
  el("puzzle-picker-back").hidden = true;
  el("puzzle-picker").hidden = true;
  el("puzzle-play").hidden = true;
  el("puzzle-back").hidden = false;
}

function showOperationDifficulty() {
  invalidatePuzzleWork();
  el("puzzle-quiz-select").hidden = true;
  el("puzzle-operation-difficulty").hidden = false;
  el("puzzle-picker-back").hidden = false;
  el("puzzle-picker").hidden = true;
  el("puzzle-play").hidden = true;
  el("puzzle-back").hidden = false;
}

function showPicker() {
  invalidatePuzzleWork();
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
      : currentQuiz === "mapping"
        ? STRUCTURE_KINDS.filter((item) => item.kind === "molecule")
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
    const item = document.createElement("button");
    const visible = !view.hiddenElements?.has(element);
    item.type = "button";
    item.className = "puzzle-legend-item";
    item.dataset.visible = visible ? "true" : "false";
    item.title = `${element} の表示を切り替え`;
    item.innerHTML = `<span class="puzzle-legend-swatch" style="background:${color}"></span>${element}`;
    item.addEventListener("click", () => {
      const nextVisible = view.hiddenElements?.has(element);
      view.setElementVisibility(element, nextVisible);
      buildLegend();
    });
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
  const generation = invalidatePuzzleWork();
  showPlay();
  // Name/formula only; the point/space group would reveal the answer.
  el("puzzle-structure-title").innerHTML = displayLabel(example);
  el("puzzle-question").textContent = "読み込み中…";
  el("puzzle-options").innerHTML = "";
  el("puzzle-result").hidden = true;
  el("puzzle-check").hidden = false;
  el("puzzle-check").disabled = true;
  el("puzzle-again").hidden = true;
  el("puzzle-playback").hidden = true;
  el("puzzle-view-along").hidden = true;
  setStageCaption("");
  await getJson("/api/open_example", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind: example.kind, path: example.path, request_id: Date.now() }),
  });
  if (generation !== roundGeneration) return;
  // Render with the shared analysis-mode view (atoms + unit cell + fitted camera).
  // Keep puzzle crystals to the unit-cell atoms; optional neighbouring-cell
  // copies provide crystal context without animating extra periodic images.
  view.renderDataQuery = example.kind === "crystal" ? "?display_mode=source&boundary_images=0" : "";
  view.animationPathQuery = example.kind === "crystal" ? "&display_mode=source&boundary_images=0" : "";
  view.symmetryElementQuery = example.kind === "crystal" ? "&display_mode=source" : "";
  view.showAnimationTargets = example.kind === "crystal";
  view.showAnimationTargetCopies = false;
  view.showTrajectories = false;
  el("puzzle-target-copies").hidden = example.kind !== "crystal";
  el("puzzle-trajectories").hidden = true;
  hidePuzzleGifButton();
  syncTargetCopiesButton();
  syncTrajectoriesButton();
  await view.refresh();
  if (generation !== roundGeneration) return;
  buildLegend();
  const endpoint =
    currentQuiz === "axis"
      ? `/api/puzzle/axis_orders${example.kind === "crystal" ? "?display_mode=source" : ""}`
      : currentQuiz === "composition"
        ? "/api/puzzle/composition"
        : currentQuiz === "mapping"
          ? "/api/puzzle/mapping"
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
        : currentQuiz === "composition"
          ? "2つの操作を合成してできる操作"
          : currentQuiz === "mapping"
            ? "移り先を答えられる原子"
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
  // The operation and composition quizzes balance by answer type: a highly
  // symmetric structure has many equivalent operations (or products) of the
  // common kinds, so pick a random group (opaque answer-type bucket) first, then
  // a random question within it. The axis quiz is already one-per-inequivalent
  // axis, so a plain random pick is fine.
  if (currentQuiz === "operation" || currentQuiz === "composition" || currentQuiz === "mapping") {
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
  invalidatePuzzleWork();
  currentQuestion = pickQuestion();
  revealOperation = null;
  view.showTrajectories = false;
  view.updateTrajectoryLines();
  view.updateAnimationTargetMarkers();
  mappingGuess = null;
  mappingRevealTarget = null;
  const result = el("puzzle-result");
  result.hidden = true;
  el("puzzle-options").innerHTML = "";
  el("puzzle-check").hidden = false;
  el("puzzle-check").disabled = false;
  el("puzzle-again").hidden = true;
  el("puzzle-slider").value = "0";
  el("puzzle-slider").hidden = false;
  el("puzzle-replay").disabled = false;
  el("puzzle-trajectories").hidden = true;
  const viewAlong = el("puzzle-view-along");
  viewAlong.hidden = !(currentQuiz === "axis" || currentQuiz === "mapping");
  viewAlong.textContent = currentQuiz === "mapping" ? "操作要素方向から見る" : "軸方向から見る";
  setStageCaption("");
  hidePuzzleGifButton();
  syncTrajectoriesButton();
  if (currentQuiz === "axis") beginAxisRound();
  else if (currentQuiz === "composition") beginCompositionRound();
  else if (currentQuiz === "mapping") beginMappingRound().catch(showError);
  else beginOperationRound();
}

function beginAxisRound() {
  view.addAxis(
    { direction_cart: currentQuestion.direction_cart, point_cart: currentQuestion.point_cart },
    view.sceneSpan(),
  );
  view.render();
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
  setPuzzleGifButtonReady(false);
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

// --- Composition quiz ("A then B" -> which single operation?) ---

function setStageCaption(text) {
  const caption = el("puzzle-stage-caption");
  if (caption) caption.textContent = text || "";
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function shortOperationLabel(answer) {
  const notation = answer?.notation || answer?.symbol;
  if (notation) return String(notation).replace(/sigma/gi, "σ").replace(/_/g, "");
  if (answer?.kind === "rotation") return `C${answer.order}`;
  if (answer?.kind === "mirror") return "σ";
  if (answer?.kind === "inversion") return "i";
  if (answer?.kind === "rotoreflection") return `S${answer.order}`;
  if (answer?.kind === "rotoinversion") return `-${answer.order}`;
  return "?";
}

function compositionStageLabel(stage, answer) {
  return `${stage}（${shortOperationLabel(answer)}）`;
}

function beginCompositionRound() {
  // The product is always a point operation, so answer with the normal vocabulary.
  currentOperationDifficulty = "normal";
  el("puzzle-question").textContent =
    "操作A を行い、続けて操作B を行うと、全体としてどの1つの操作と同じになりますか？";
  renderOperationOptions();
  // The two animations ARE the question. A single scrub slider is confusing across
  // the two phases, so hide it; the 再生 button replays A then B.
  el("puzzle-slider").hidden = true;
  el("puzzle-playback").hidden = false;
  el("puzzle-check").disabled = true;
  hidePuzzleGifButton();
  playCompositionQuestion().catch(showError);
}

async function playSingleOperation(operationIndex, generation, caption, isCurrent = null) {
  const stillCurrent = isCurrent || (() => generation === roundGeneration);
  if (!stillCurrent()) return false;
  view.setAnimationSourceAtoms(null);
  setStageCaption(caption);
  await view.loadAnimationPaths(
    Number(operationIndex),
    ++view.pathGeneration,
    view.showAnimationTargets ? "unit_cell" : "displayed",
  );
  if (!stillCurrent()) return false;
  view.resetAnimation();
  await animateReveal();
  return stillCurrent();
}

async function playCompositionQuestion() {
  const generation = roundGeneration;
  const question = currentQuestion;
  const playback = ++compositionPlaybackGeneration;
  const isCurrent = () =>
    generation === roundGeneration
    && playback === compositionPlaybackGeneration
    && question === currentQuestion
    && !operationAnswered;
  compositionQuestionReady = false;
  el("puzzle-check").disabled = true;
  el("puzzle-replay").disabled = true;
  let completed = false;
  try {
    const labelA = compositionStageLabel("操作A", question.operation_a);
    const labelB = compositionStageLabel("操作B", question.operation_b);
    if (!await playSingleOperation(question.operation_index_a, generation, labelA, isCurrent)) return;
    await sleep(450);
    if (!isCurrent()) return;
    if (!await playSingleOperation(question.operation_index_b, generation, labelB, isCurrent)) return;
    if (!isCurrent()) return;
    setStageCaption(`${labelA} → ${labelB}`);
    completed = true;
  } finally {
    if (isCurrent()) {
      compositionQuestionReady = completed;
      el("puzzle-check").disabled = !completed;
      el("puzzle-replay").disabled = false;
    }
  }
}

async function playCompositionProduct(generation = roundGeneration) {
  const playback = ++compositionPlaybackGeneration;
  const isCurrent = () =>
    generation === roundGeneration
    && playback === compositionPlaybackGeneration
    && operationAnswered
    && revealOperation != null;
  cancelReveal();
  el("puzzle-replay").disabled = true;
  try {
    if (!await playSingleOperation(revealOperation, generation, "合成の結果", isCurrent)) return;
    if (!isCurrent()) return;
    setStageCaption("合成の結果");
    revealOperationElements(generation);
  } finally {
    if (isCurrent()) el("puzzle-replay").disabled = false;
  }
}

async function onCheckComposition() {
  const generation = roundGeneration;
  if (!compositionQuestionReady) {
    showPrompt("操作A・Bの再生が終わってから回答してください。");
    return;
  }
  const { kind, order } = selectedOperationAnswer();
  if (!kind) {
    showPrompt("操作の種類を選んでください。");
    return;
  }
  const config = operationKinds().find((k) => k.kind === kind);
  if (config?.orders && order == null) {
    showPrompt("回数も選んでください。");
    return;
  }
  compositionQuestionReady = false;
  compositionPlaybackGeneration += 1;
  cancelReveal();
  view.pathGeneration += 1;
  el("puzzle-check").disabled = true;
  el("puzzle-replay").disabled = true;
  let result;
  try {
    result = await getJson("/api/puzzle/composition/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_id: currentQuestion.id, kind, order }),
    });
  } catch (error) {
    // A transient POST failure must not strand the round with both controls
    // disabled.  Keep the already-viewed question answerable and replayable.
    if (generation === roundGeneration) {
      compositionQuestionReady = true;
      el("puzzle-check").disabled = false;
      el("puzzle-replay").disabled = false;
    }
    throw error;
  }
  if (generation !== roundGeneration) return;
  const box = el("puzzle-result");
  box.hidden = false;
  box.className = `puzzle-result ${result.correct ? "hit" : "miss"}`;
  const answerText = formatOperationAnswers(result.answers);
  box.innerHTML = result.correct ? `正解（${answerText}）` : `不正解（正解は ${answerText}）`;
  operationAnswered = true;
  el("puzzle-again").hidden = false;
  // Reveal the product: play its animation, then show its symmetry element.
  revealOperation = result.product_index;
  await playCompositionProduct(generation);
}

// --- Reveal animation (shared) ---

function setSlider(fraction) {
  el("puzzle-slider").value = String(Math.round(fraction * 1000));
}

function animateProgress(from, to, durationMs) {
  cancelReveal();
  return new Promise((resolve) => {
    const token = { resolve, start: performance.now() };
    revealAnim = token;
    const step = (now) => {
      if (revealAnim !== token) return; // superseded/cancelled
      const k = Math.min((now - token.start) / durationMs, 1);
      const fraction = from + (to - from) * k;
      view.setAnimationProgress(fraction);
      setSlider(fraction);
      if (k >= 1) {
        revealAnim = null;
        resolve();
        return;
      }
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

function animateReveal() {
  return animateProgress(0, 1, REVEAL_DURATION_MS);
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
  if (!el("puzzle-save-gif").hidden) el("puzzle-save-gif").disabled = true;
  try {
    // Override the shared analysis selection so puzzle rounds animate their own
    // displayed/unit-cell atoms consistently.
    await view.loadAnimationPaths(Number(revealOperation), ++view.pathGeneration, view.showAnimationTargets ? "unit_cell" : "displayed");
    if (generation !== roundGeneration) return;
    view.resetAnimation();
    await animateReveal();
    revealOperationElements(generation);
  } finally {
    if (generation === roundGeneration) {
      el("puzzle-replay").disabled = false;
      if (!el("puzzle-save-gif").hidden) {
        el("puzzle-save-gif").disabled = !view.animationPaths.size;
      }
    }
  }
}

function revealOperationElements(generation = roundGeneration) {
  if (!operationAnswered || generation !== roundGeneration || revealOperation == null) return;
  // Use the current path generation. If a replay supersedes this request, the
  // StaticStructureView guard discards it, and replay completion calls us again.
  view.loadSymmetryElements(Number(revealOperation), view.pathGeneration).catch(() => {});
}

// --- Mapping quiz ("where does this atom go?") ---

function atomStartMarker(sourceAtom) {
  for (const instance of view.atomInstances.values()) {
    if (instance.sourceAtom === Number(sourceAtom)) {
      return { position: instance.start, radius: instance.radius };
    }
  }
  return null;
}

function refreshMappingMarkers({ revealTarget = null } = {}) {
  const entries = [{ atom: currentQuestion.source_atom_index, color: PICK_SOURCE_COLOR }];
  if (mappingGuess != null && mappingGuess !== currentQuestion.source_atom_index) {
    // The blue ring means "the destination I clicked", so keep it at that
    // original site while all atoms move during the reveal.  Following the atom
    // that happened to occupy the site would give the colour a different meaning.
    const guess = atomStartMarker(mappingGuess);
    if (guess) {
      entries.push({
        position: [...guess.position],
        color: PICK_GUESS_COLOR,
        // Sits inside the yellow ring, which the source atom carries at radius
        // 1.0. Leave the same visible gap the green answer ring has on the
        // outside, so a correct guess reads as three rings and not one band.
        radius: guess.radius * 0.84,
      });
    }
  }
  if (revealTarget != null) {
    // A fixed ring at the target atom's start position: the highlighted atom lands
    // inside it as the operation completes (the target atom itself moves away).
    const target = atomStartMarker(revealTarget);
    if (target) {
      entries.push({
        position: [...target.position],
        color: PICK_TARGET_COLOR,
        // A correct blue guess and the green answer are concentric.  Different
        // radii leave both visible instead of letting one ring completely hide.
        radius: target.radius * 1.18,
      });
    }
  }
  view.setPickMarkers(entries);
}

function orientPlanarMappingStructure() {
  const coords = (view.renderData?.atoms || [])
    .map((atom) => atom.cart?.map(Number))
    .filter((cart) => Array.isArray(cart) && cart.length === 3 && cart.every(Number.isFinite));
  if (coords.length < 2) return;
  const add = (a, b) => a.map((value, axis) => value + b[axis]);
  const subtract = (a, b) => a.map((value, axis) => value - b[axis]);
  const scale = (a, factor) => a.map((value) => value * factor);
  const dot = (a, b) => a.reduce((sum, value, axis) => sum + value * b[axis], 0);
  const cross = (a, b) => [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
  const length = (a) => Math.sqrt(dot(a, a));
  const center = scale(coords.reduce(add, [0, 0, 0]), 1 / coords.length);
  const centered = coords.map((point) => subtract(point, center));
  const primary = centered.reduce(
    (best, point) => (length(point) > length(best) ? point : best),
    [0, 0, 0],
  );
  const extent = length(primary);
  if (!(extent > 1e-10)) return;

  // A cross product finds the normal regardless of how the molecule is oriented
  // in Cartesian space.  If all points are collinear, choose a stable direction
  // perpendicular to the molecular line instead.
  let normal = centered.reduce(
    (best, point) => (length(cross(primary, point)) > length(best) ? cross(primary, point) : best),
    [0, 0, 0],
  );
  if (length(normal) <= extent * extent * 1e-8) {
    const leastAligned = Math.abs(primary[0]) <= Math.abs(primary[1])
      && Math.abs(primary[0]) <= Math.abs(primary[2])
      ? [1, 0, 0]
      : Math.abs(primary[1]) <= Math.abs(primary[2]) ? [0, 1, 0] : [0, 0, 1];
    normal = cross(primary, leastAligned);
  }
  const normalLength = length(normal);
  if (!(normalLength > 1e-10)) return;
  normal = scale(normal, 1 / normalLength);
  const thickness = Math.max(...centered.map((point) => Math.abs(dot(point, normal))));
  if (thickness > extent * 0.08) return;
  view.viewAlongCartesianDirection(normal, center);
}

async function beginMappingRound() {
  mappingGuess = null;
  const operationLabel = shortOperationLabel(currentQuestion.operation);
  el("puzzle-question").textContent =
    `黄色の原子は、操作 ${operationLabel} でどの原子に移りますか？移り先の原子をクリックしてから回答してください。`;
  setStageCaption(`操作 ${operationLabel}（一部をプレビュー）`);
  el("puzzle-options").innerHTML = ""; // the answer is a click, not a radio choice
  el("puzzle-slider").hidden = true;
  el("puzzle-playback").hidden = false;
  el("puzzle-check").disabled = true;
  hidePuzzleGifButton();
  // Face planar/linear molecules along their thin axis so candidate sites do not
  // overlap (notably benzene's C/H rings in the default oblique camera).
  orientPlanarMappingStructure();
  view.onAtomPick = (atomIndex) => {
    if (operationAnswered || !mappingQuestionReady || atomIndex == null) return;
    mappingGuess = Number(atomIndex);
    refreshMappingMarkers();
  };
  await playMappingPreview();
}

function mappingPreviewFraction() {
  const operation = (view.renderData?.operations || []).find(
    (item) => Number(item.index) === Number(currentQuestion?.operation_index),
  );
  const kind = String(operation?.kind || "");
  const curved =
    kind.startsWith("rotation_")
    || kind.startsWith("improper_")
    || kind.startsWith("rotoreflection")
    || kind.startsWith("rotoinversion");
  return curved ? MAPPING_CURVED_PREVIEW : MAPPING_STRAIGHT_PREVIEW;
}

async function playMappingPreview() {
  const generation = roundGeneration;
  const question = currentQuestion;
  const playback = ++mappingPlaybackGeneration;
  const isCurrent = () =>
    generation === roundGeneration
    && playback === mappingPlaybackGeneration
    && question === currentQuestion
    && !operationAnswered;
  mappingQuestionReady = false;
  el("puzzle-check").disabled = true;
  el("puzzle-replay").disabled = true;
  let completed = false;
  try {
    view.setAnimationSourceAtoms([question.source_atom_index]);
    const pathGeneration = ++view.pathGeneration;
    const elementRequest = view
      .loadSymmetryElements(Number(question.operation_index), pathGeneration)
      .catch(() => {});
    await view.loadAnimationPaths(Number(question.operation_index), pathGeneration, "displayed");
    await elementRequest;
    if (!isCurrent()) return;
    view.resetAnimation();
    refreshMappingMarkers();
    // Move only the yellow source atom. Candidate atoms remain fixed, so clicking
    // a site has an unambiguous meaning even for indistinguishable atoms.
    const fraction = mappingPreviewFraction();
    await animateProgress(0, fraction, Math.max(280, REVEAL_DURATION_MS * fraction));
    completed = isCurrent();
  } finally {
    if (isCurrent()) {
      mappingQuestionReady = completed;
      el("puzzle-check").disabled = !completed;
      el("puzzle-replay").disabled = false;
    }
  }
}

async function playMappingReveal(generation = roundGeneration) {
  const playback = ++mappingPlaybackGeneration;
  const isCurrent = () =>
    generation === roundGeneration
    && playback === mappingPlaybackGeneration
    && operationAnswered;
  cancelReveal();
  el("puzzle-replay").disabled = true;
  view.setAnimationSourceAtoms(null);
  view.resetAnimation();
  refreshMappingMarkers({ revealTarget: mappingRevealTarget });
  try {
    await animateProgress(0, 1, REVEAL_DURATION_MS);
  } finally {
    if (isCurrent()) el("puzzle-replay").disabled = false;
  }
}

async function onCheckMapping() {
  const generation = roundGeneration;
  if (!mappingQuestionReady) {
    showPrompt("プレビューが終わってから移り先を選んでください。");
    return;
  }
  if (mappingGuess == null) {
    showPrompt("移り先の原子をクリックしてください。");
    return;
  }
  mappingQuestionReady = false;
  mappingPlaybackGeneration += 1;
  cancelReveal();
  view.pathGeneration += 1;
  el("puzzle-check").disabled = true;
  el("puzzle-replay").disabled = true;
  let result;
  try {
    result = await getJson("/api/puzzle/mapping/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_id: currentQuestion.id, selected_atom_index: mappingGuess }),
    });
  } catch (error) {
    if (generation === roundGeneration) {
      mappingQuestionReady = true;
      el("puzzle-check").disabled = false;
      el("puzzle-replay").disabled = false;
    }
    throw error;
  }
  if (generation !== roundGeneration) return;
  operationAnswered = true;
  const box = el("puzzle-result");
  box.hidden = false;
  box.className = `puzzle-result ${result.correct ? "hit" : "miss"}`;
  box.textContent = result.correct ? "正解" : "不正解";
  el("puzzle-again").hidden = false;
  mappingRevealTarget = result.target_atom_index; // keep the guess ring; add the target
  // Reveal the full operation from rest: the yellow atom lands on the fixed green
  // destination ring while the rest of the molecule follows the same operation.
  await playMappingReveal(generation);
}

// --- Checking answers ---

async function onCheck() {
  if (!currentQuestion) return;
  if (currentQuiz === "axis") return onCheckAxis();
  if (currentQuiz === "composition") return onCheckComposition();
  if (currentQuiz === "mapping") return onCheckMapping();
  return onCheckOperation();
}

function onReplay() {
  // Composition replays its own two-phase sequence (or the product, once answered).
  if (currentQuiz === "composition") {
    if (operationAnswered && revealOperation != null) {
      return playCompositionProduct();
    }
    return playCompositionQuestion();
  }
  if (currentQuiz === "mapping") {
    if (!operationAnswered) return playMappingPreview();
    return playMappingReveal();
  }
  return playReveal();
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
    el("puzzle-trajectories").hidden = false;
    setPuzzleGifButtonReady(false);
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
  el("puzzle-trajectories").hidden = false;
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

function syncTargetCopiesButton() {
  const button = el("puzzle-target-copies");
  const enabled = view.showAnimationTargetCopies !== false;
  button.dataset.enabled = enabled ? "true" : "false";
  button.textContent = enabled ? "隣接セル: 表示" : "隣接セル: 非表示";
}

function toggleTargetCopies() {
  view.showAnimationTargetCopies = view.showAnimationTargetCopies === false;
  view.updateAnimationTargetMarkers();
  syncTargetCopiesButton();
}

function syncTrajectoriesButton() {
  const button = el("puzzle-trajectories");
  const enabled = view.showTrajectories === true;
  button.dataset.enabled = enabled ? "true" : "false";
  button.textContent = enabled ? "軌道: 表示" : "軌道: 非表示";
}

function toggleTrajectories() {
  view.showTrajectories = view.showTrajectories !== true;
  view.updateTrajectoryLines();
  syncTrajectoriesButton();
}

function hidePuzzleGifButton() {
  const button = el("puzzle-save-gif");
  button.hidden = true;
  button.disabled = true;
  button.textContent = "GIFを保存";
}

function setPuzzleGifButtonReady(ready) {
  const button = el("puzzle-save-gif");
  button.hidden = false;
  button.disabled = !ready;
  button.textContent = "GIFを保存";
}

async function savePuzzleGif() {
  const button = el("puzzle-save-gif");
  if (view.recording) return;
  const controls = [...el("puzzle-play").querySelectorAll("button, input")];
  const disabled = new Map(controls.map(control => [control, control.disabled]));
  for (const control of controls) control.disabled = true;
  button.disabled = true;
  button.textContent = "保存中...";
  try {
    await view.recordGif("puzzle-animation");
  } finally {
    for (const [control, wasDisabled] of disabled) control.disabled = wasDisabled;
    button.textContent = "GIFを保存";
  }
}

function setupCameraControls() {
  for (const [id, direction] of Object.entries(CAMERA_DIRECTIONS)) {
    el(id).addEventListener("click", () => {
      view.rotateCamera(direction, Number(el("puzzle-cam-angle").value) || 0);
    });
  }
  el("puzzle-view-along").addEventListener("click", () => {
    if (!currentQuestion) return;
    if (currentQuiz === "axis") {
      view.viewAlongCartesianDirection(currentQuestion.direction_cart, currentQuestion.point_cart);
    } else if (currentQuiz === "mapping") {
      view.viewAlongCurrentOperation();
    }
  });
}

function setupControls() {
  el("puzzle-projection").addEventListener("click", toggleProjection);
  el("puzzle-target-copies").addEventListener("click", toggleTargetCopies);
  el("puzzle-trajectories").addEventListener("click", toggleTrajectories);
  setupCameraControls();
  el("puzzle-check").addEventListener("click", () => onCheck().catch(showError));
  el("puzzle-replay").addEventListener("click", () => onReplay().catch(showError));
  el("puzzle-save-gif").addEventListener("click", () => savePuzzleGif().catch(showError));
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

function enterPuzzle() {
  if (!started) {
    started = true;
    view = new StaticStructureView(el("puzzle-view"));
    view.setBackgroundMode("light");
    // Puzzle clicks are never analysis selections. The mapping round installs its
    // own hook; all other puzzle screens simply ignore atom clicks.
    view.disableAtomSelection = true;
    setupControls();
  } else if (view) {
    view.resize();
  }
  showQuizSelect();
}

window.addEventListener("symmetry-enter-puzzle", enterPuzzle);

// In --mode puzzle the classic UI script can dispatch its entry event before this
// module has registered the listener. Recover from that ordering by inspecting the
// already-rendered screen; `started` keeps the path idempotent.
if (el("puzzle-mode")?.hidden === false) queueMicrotask(enterPuzzle);
