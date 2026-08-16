#!/usr/bin/env python
"""Walk the real viewer in headless Chromium and save the report figures.

This is the "通し確認" pass from docs/REPORT_OUTLINE.md: it plays all four
quizzes the way a person does and exercises analysis mode, saving the figures
listed in the 図表リスト along the way. The server never publishes the correct
answer, so rounds are guessed and replayed until one comes back correct; a
figure showing 正解 is therefore evidence that the path really works.

Needs the test-only extras (playwright and a chromium binary):

    .venv/bin/python -m pip install -r requirements-dev.txt
    .venv/bin/python tools/capture_report_figures.py [--only puzzle|analysis]

The figure list and the pitfalls behind the odd-looking choices in here are in
docs/figures/README.md.
"""

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
FIGURES = ROOT / "docs" / "figures"
LOAD_TIMEOUT_MS = 90000
READY = '() => !document.getElementById("puzzle-check").disabled'
# 不正解 contains 正解, so this waits for a verdict of either kind -- which is
# what the callers want, since a wrong answer still ends the round.
VERDICT = """() => {
  const box = document.getElementById('puzzle-result');
  return !box.hidden && box.textContent.includes('正解');
}"""

log_lines: list[str] = []


def log(message: str) -> None:
    print(message, flush=True)
    log_lines.append(message)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Server:
    def __init__(self) -> None:
        self.port = free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"

    def __enter__(self):
        self.proc = subprocess.Popen(
            [sys.executable, "tools/view_json_server.py", "--port", str(self.port),
             "--no-browser"],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(self.base_url + "/api/state", timeout=1).read()
                return self
            except (urllib.error.URLError, OSError):
                time.sleep(0.3)
        self.proc.kill()
        raise RuntimeError("the viewer server did not come up")

    def __exit__(self, *exc):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


# --- shared helpers ---------------------------------------------------------

def shot(target, name: str) -> None:
    """Save a figure and record it in the walkthrough log."""
    path = FIGURES / f"{name}.png"
    target.screenshot(path=str(path))
    log(f"  saved {path.relative_to(ROOT)}")


def text(page, selector: str) -> str:
    return (page.text_content(selector) or "").strip()


def shot_puzzle(page, name: str, quiet: bool = False) -> None:
    """The puzzle screen, clipped to where its content actually ends.

    The mode is an overlay that fills the window, so a plain page screenshot
    leaves a third of the figure as empty background.
    """
    bottom = 0.0
    # #puzzle-result is measured on its own: it is revealed after the round and
    # can end up taller than the box that nominally contains it.
    for selector in ("#puzzle-play", "#puzzle-result", "#puzzle-quiz-select",
                     "#puzzle-picker", "#puzzle-operation-difficulty"):
        locator = page.locator(selector)
        if locator.count() and locator.is_visible():
            box = locator.bounding_box()
            if box:
                bottom = max(bottom, box["y"] + box["height"])
    size = page.viewport_size
    height = min(size["height"], int(bottom) + 40) if bottom else size["height"]
    path = FIGURES / f"{name}.png"
    page.screenshot(path=str(path),
                    clip={"x": 0, "y": 0, "width": size["width"], "height": height})
    if not quiet:
        log(f"  saved {path.relative_to(ROOT)}")


# --- puzzle mode ------------------------------------------------------------

def enter_puzzle(page) -> None:
    page.click("#enter-puzzle")
    page.wait_for_selector("#puzzle-quiz-select", state="visible", timeout=LOAD_TIMEOUT_MS)


def go_to_quiz_select(page) -> None:
    """Back out of whatever screen we are on until the quiz list is showing.

    The operation quiz puts a difficulty screen between the quiz list and the
    structure picker, so one 戻る does not always reach the list.
    """
    for _ in range(4):
        if page.is_visible("#puzzle-quiz-select"):
            return
        if page.is_hidden("#puzzle-picker") and page.is_hidden("#puzzle-operation-difficulty"):
            page.click("#puzzle-other")  # a played round -> back to its picker
            page.wait_for_selector(".puzzle-structure", state="visible")
        page.click("#puzzle-picker-back")
        page.wait_for_timeout(500)
    raise RuntimeError("could not get back to the quiz list")


def open_quiz(page, quiz: str, structure: str, kind: str = "分子",
              difficulty: str | None = None) -> None:
    """Quiz select -> (difficulty) -> structure picker -> a playable round."""
    go_to_quiz_select(page)
    page.click(f'#puzzle-quiz-select .puzzle-quiz-card[data-quiz="{quiz}"]')
    if difficulty:
        card = f'#puzzle-operation-difficulty .puzzle-quiz-card[data-operation-difficulty="{difficulty}"]'
        page.wait_for_selector(card, state="visible", timeout=LOAD_TIMEOUT_MS)
        page.click(card)
    page.wait_for_selector(".puzzle-structure", state="visible", timeout=LOAD_TIMEOUT_MS)
    if page.locator(f'.puzzle-kind:has-text("{kind}")').count():
        page.click(f'.puzzle-kind:has-text("{kind}")')
    page.wait_for_selector(f'.puzzle-structure:has-text("{structure}")', state="visible")
    page.click(f'.puzzle-structure:has-text("{structure}")')
    page.wait_for_function(
        '() => !document.getElementById("puzzle-play").hidden'
        ' && document.getElementById("puzzle-question").textContent.length > 0',
        timeout=LOAD_TIMEOUT_MS,
    )


def next_round(page) -> None:
    page.wait_for_selector("#puzzle-again:not([hidden])", timeout=LOAD_TIMEOUT_MS)
    page.click("#puzzle-again")
    page.wait_for_function(
        '() => document.getElementById("puzzle-result").hidden', timeout=LOAD_TIMEOUT_MS)


def press_check(page, timeout_ms: int = 8000) -> str | None:
    """Press 回答 and return the verdict text, or None if the box never settled.

    Pressing while the operations are still playing is answered with a prompt in
    the same box, which is intended behaviour, so the caller retries.
    """
    page.click("#puzzle-check")
    try:
        page.wait_for_function(VERDICT, timeout=timeout_ms)
    except Exception:
        return None
    return text(page, "#puzzle-result")


def capture_round(page, name: str, answer, rounds: int = 40) -> str:
    """Play rounds until one is answered correctly; save the before/after pair.

    `answer` drives one attempt and returns the verdict text (or None).  The
    question shot is taken before answering and only kept once the same round
    turns out to be correct, so the two figures always show one round.

    Answers here are guesses -- the server never publishes the correct one --
    so a quiz whose answer space is wide can run out of rounds.  Rather than
    leave a hole in the figure set, the last round is then kept as it stands and
    reported as a wrong answer, which still shows the reveal.
    """
    for attempt in range(1, rounds + 1):
        page.wait_for_function(READY, timeout=LOAD_TIMEOUT_MS)
        page.wait_for_timeout(400)  # let the first render settle before shooting
        shot_puzzle(page, f"{name}_question", quiet=True)
        verdict = answer()
        correct = bool(verdict) and "不正解" not in verdict
        if correct or (attempt == rounds and verdict):
            page.wait_for_timeout(2500)  # let the reveal animation land
            log(f"  saved docs/figures/{name}_question.png")
            shot_puzzle(page, f"{name}_answer")
            outcome = f"correct on attempt {attempt}" if correct else (
                f"NOT correct in {rounds} rounds; kept a wrong answer")
            log(f"  {outcome}: {verdict.splitlines()[0][:70]}")
            return verdict
        next_round(page)
    raise RuntimeError(f"{name}: no round ever produced a verdict")


def answer_operation_style(page):
    """Tick a kind, plus the fold and translation part when the round wants them.

    The hard difficulty always requires a 並進成分, and its row only appears once
    a kind is ticked, so the three are picked in that order.  The counters step
    by different amounts so repeated rounds sweep combinations instead of
    retrying the same one.
    """
    for _ in range(10):
        page.wait_for_function(READY, timeout=LOAD_TIMEOUT_MS)
        kinds = page.locator('#puzzle-options input[name="op-kind"]')
        kinds.nth(answer_operation_style.kind_pick % kinds.count()).check()
        orders = page.locator('#puzzle-options input[name="op-order"]')
        if orders.count():
            orders.nth(answer_operation_style.order_pick % orders.count()).check()
        shifts = page.locator('#puzzle-options input[name="op-shift"]')
        if shifts.count() and shifts.first.is_visible():
            shifts.nth(answer_operation_style.shift_pick % shifts.count()).check()
        verdict = press_check(page)
        if verdict is not None:
            answer_operation_style.kind_pick += 1
            answer_operation_style.order_pick += 1
            answer_operation_style.shift_pick += 3
            return verdict
        page.wait_for_timeout(200)  # the operations are probably still playing
    return None


answer_operation_style.kind_pick = 0
answer_operation_style.order_pick = 0
answer_operation_style.shift_pick = 0


def answer_axis(page):
    options = page.locator('#puzzle-options input[name="puzzle-order"]')
    options.nth(answer_axis.pick % options.count()).check()
    answer_axis.pick += 1
    return press_check(page)


answer_axis.pick = 0


def ring_count(page) -> int:
    return int(page.evaluate(
        "() => document.getElementById('puzzle-view')?.dataset?.pickMarkerCount ?? 0"))


MAPPING_SPOTS = [(fx / 20, fy / 20) for fy in range(5, 16) for fx in range(4, 17)]


def answer_mapping(page):
    """Click destinations in the 3D view until one registers, then answer.

    The destination is a click, not a listed option, so there is nothing to
    cycle through; the grid is swept instead, densely enough to reach every
    atom rather than only the large ones near the middle.
    """
    box = page.locator("#puzzle-view").bounding_box()
    start = answer_mapping.pick
    spots = MAPPING_SPOTS
    for offset in range(len(spots)):
        fx, fy = spots[(start + offset) % len(spots)]
        page.mouse.click(box["x"] + box["width"] * fx, box["y"] + box["height"] * fy)
        page.wait_for_timeout(60)
        if ring_count(page) > 1:
            # Step well past the spot that just worked: neighbouring points land
            # on the same atom, and a round that guesses the same atom again
            # learns nothing.
            answer_mapping.pick = start + offset + 17
            return press_check(page)
    return None


answer_mapping.pick = 0


def capture_puzzle(page, base_url: str) -> None:
    log("puzzle mode")
    enter_puzzle(page)
    shot_puzzle(page, "fig04a_quiz_select")

    # Figure 4: the annotated layout shot. Any playable round shows every part,
    # so it is taken from the axis quiz before that quiz's own figures.
    open_quiz(page, "axis", "C6H6")
    page.wait_for_function(READY, timeout=LOAD_TIMEOUT_MS)
    page.wait_for_timeout(600)
    shot_puzzle(page, "fig04_puzzle_layout")

    log(" 回転軸クイズ (benzene)")
    capture_round(page, "fig05_axis", lambda: answer_axis(page))

    log(" 操作あてクイズ・普通 (benzene)")
    open_quiz(page, "operation", "C6H6", difficulty="normal")
    capture_round(page, "fig06_operation_normal", lambda: answer_operation_style(page))

    log(" 操作あてクイズ・難しい (halite)")
    open_quiz(page, "operation", "NaCl", kind="結晶", difficulty="hard")
    # Kind x fold x translation is a much larger answer space than the other
    # quizzes, so guessing needs more rounds to land on a correct one.
    capture_round(page, "fig06b_operation_hard", lambda: answer_operation_style(page),
                  rounds=80)

    log(" 合成クイズ (benzene)")
    open_quiz(page, "composition", "C6H6")
    capture_round(page, "fig07_composition", lambda: answer_operation_style(page))

    # Methane rather than benzene: the destination is guessed by clicking, and
    # with 12 atoms to choose from a guessing run rarely lands on the right one.
    log(" 移り先クイズ (methane)")
    open_quiz(page, "mapping", "CH4")
    capture_round(page, "fig08_mapping", lambda: answer_mapping(page), rounds=60)

    # 戻る is hidden while a round is in play, so leaving the mode means backing
    # out to the quiz list first.
    go_to_quiz_select(page)
    page.click("#puzzle-back")
    page.wait_for_selector("#enter-analysis", state="visible", timeout=LOAD_TIMEOUT_MS)


# --- analysis mode ----------------------------------------------------------

def open_example(page, base_url: str, kind: str, path: str) -> None:
    """Load an example and prove it actually loaded.

    The picker lists one kind at a time and rebuilds its options when the kind
    changes, so a value set too early is silently dropped and the previous
    structure stays on screen. `.operation-row` is already present from that
    structure, so waiting for it proves nothing — check the server's state and
    the drawn list instead, or the figures record the wrong structure.
    """
    directory = f"examples/{'cif' if kind == 'crystal' else 'molecules'}/"
    for _ in range(3):
        listed = page.evaluate(
            """directory => [...document.getElementById('example-select').options]
                              .some(option => option.value.startsWith(directory))""",
            directory,
        )
        if listed:
            break
        page.click("#structure-kind-toggle")
        page.wait_for_timeout(500)
    else:
        raise RuntimeError(f"the example picker never listed {directory}")

    selected = page.evaluate(
        """path => {
             const select = document.getElementById('example-select');
             select.value = path;
             select.dispatchEvent(new Event('change', {bubbles: true}));
             return select.value;
           }""",
        path,
    )
    if selected != path:
        raise RuntimeError(f"{path} is not among the picker's options")
    page.click("#open-example")

    stem = Path(path).stem
    deadline = time.monotonic() + LOAD_TIMEOUT_MS / 1000
    while time.monotonic() < deadline:
        loaded = json.loads(
            urllib.request.urlopen(base_url + "/api/state", timeout=10).read()
        ).get("json_path", "")
        if stem.lower().replace("-", "_") in Path(loaded).stem:
            break
        time.sleep(0.3)
    else:
        raise RuntimeError(f"{path} never became the loaded structure (still {loaded})")
    page.wait_for_timeout(1200)  # first render of the structure


def scroll_operations_to_top(page) -> None:
    """The list scrolls the selected operation into view; a figure wants row 1."""
    page.evaluate("() => { document.getElementById('operations').scrollTop = 0; }")
    page.wait_for_timeout(200)


def select_operation(page, index: int) -> None:
    page.click(f'.operation-row[data-index="{index}"]')
    page.wait_for_timeout(900)


def operations(base_url: str) -> list[dict]:
    payload = json.loads(urllib.request.urlopen(base_url + "/api/operations", timeout=60).read())
    return payload["operations"] if isinstance(payload, dict) else payload


def first_of_kind(ops: list[dict], *kinds: str) -> int | None:
    for kind in kinds:
        for op in ops:
            if op["kind"] == kind or op["kind"].startswith(kind):
                return op["index"]
    return None


def first_drawn_glide(ops: list[dict]) -> int | None:
    """A glide whose in-plane translation is drawn as an arrow.

    Only the general "g" glides carry an explicit vector; the axial ones (a, b,
    c, n) are named by their ITC symbol instead and get no arrow, so picking the
    first glide in the list would give a figure with a bare plane in it.
    """
    for op in ops:
        if op["kind"].startswith("glide") and "glide (" in op["element_summary"]:
            return op["index"]
    return None


def view_along_axis(page, tilt_deg: int = 25) -> None:
    """Look down the selected element, then tilt off it slightly.

    Straight down a rotation axis the structure is face-on but the axis itself
    is a dot; a small tilt keeps both the ring and the axis readable.
    """
    page.evaluate("() => { document.getElementById('view-panel').open = true; }")
    page.wait_for_selector("#view-direction", state="visible")
    page.click("#view-direction")
    page.wait_for_timeout(900)
    page.fill("#camera-angle", str(tilt_deg))
    page.click("#camera-down")
    page.wait_for_timeout(900)
    page.evaluate("() => { document.getElementById('view-panel').open = false; }")
    page.wait_for_timeout(300)


def set_progress(page, value: float) -> None:
    page.evaluate(
        """v => {
             const slider = document.getElementById('movement-progress');
             slider.value = String(Math.round(v * 1000));
             slider.dispatchEvent(new Event('input', {bubbles: true}));
           }""",
        value,
    )
    page.wait_for_timeout(800)


def capture_analysis(page, base_url: str) -> None:
    log("analysis mode")
    page.click("#enter-analysis")
    # #example-select is an aria-hidden proxy behind the rich select, so the
    # button next to it is what tells us the panel is live.
    page.wait_for_selector("#open-example", state="visible", timeout=LOAD_TIMEOUT_MS)

    # Figure 2: the operation catalogue. Benzene carries rotation, mirror,
    # inversion and both improper families in one list.
    open_example(page, base_url, "molecule", "examples/molecules/benzene.xyz")
    ops = operations(base_url)
    log(f"  benzene: {len(ops)} operations, kinds="
        f"{sorted({op['kind'] for op in ops})}")
    scroll_operations_to_top(page)
    shot(page, "fig02a_analysis_benzene")
    shot(page.locator("#standard-panel"), "fig02b_operation_list_molecule")

    # Figure 3: one operation, three frames of its animation. The default camera
    # meets benzene edge-on, where a rotation about the ring normal barely moves
    # anything on screen, so look down the axis before scrubbing.
    c6 = next(op["index"] for op in ops if op["symbol"] == "C6")
    select_operation(page, c6)
    shot(page.locator("#three-view"), "fig09a_element_axis_edge_on")
    view_along_axis(page)
    log(f"  C6 selected: {text(page, '#op-details')[:80]!r}")
    shot(page, "fig09a_element_axis")
    for label, value in (("before", 0.0), ("mid", 0.5), ("after", 1.0)):
        set_progress(page, value)
        shot(page.locator("#three-view"), f"fig03_anim_{label}")
    set_progress(page, 0.0)

    # Figure 9: what each kind of symmetry element looks like.
    for name, kinds in (("plane", ("mirror",)), ("center", ("inversion",)),
                        ("improper", ("rotoreflection", "improper", "rotoinversion"))):
        index = first_of_kind(ops, *kinds)
        if index is None:
            log(f"  no {name} operation in benzene; skipped")
            continue
        select_operation(page, index)
        log(f"  {name}: op {index} — {text(page, '#op-details')[:80]!r}")
        shot(page.locator("#three-view"), f"fig09_element_{name}")

    # The crystal side: halite for the list, and a glide for the arrow figure.
    open_example(page, base_url, "crystal", "examples/cif/Halite.cif")
    ops = operations(base_url)
    log(f"  halite: {len(ops)} operations, kinds={sorted({op['kind'] for op in ops})}")
    shot(page, "fig02c_analysis_halite")
    shot(page.locator("#standard-panel"), "fig02d_operation_list_crystal")
    for name, index in (("glide", first_drawn_glide(ops)),
                        ("screw", first_of_kind(ops, "screw"))):
        if index is None:
            log(f"  no {name} operation in halite; skipped")
            continue
        select_operation(page, index)
        summary = next(op["element_summary"] for op in ops if op["index"] == index)
        log(f"  {name}: op {index} — {summary!r}")
        shot(page.locator("#three-view"), f"fig09_element_{name}")


# --- entry point ------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["puzzle", "analysis"])
    args = parser.parse_args()

    FIGURES.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with Server() as server, sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960},
                                device_scale_factor=2)
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda msg: errors.append(f"console[error]: {msg.text}")
                if msg.type == "error" else None)
        page.goto(server.base_url, wait_until="networkidle")
        page.wait_for_selector("#enter-puzzle", state="visible", timeout=LOAD_TIMEOUT_MS)

        if args.only != "analysis":
            capture_puzzle(page, server.base_url)
        if args.only != "puzzle":
            if args.only == "analysis":
                page.wait_for_selector("#enter-analysis", state="visible")
            capture_analysis(page, server.base_url)
        browser.close()

    log("")
    if errors:
        log(f"page errors ({len(errors)}):")
        for error in errors:
            log(f"  {error}")
    else:
        log("no uncaught page errors")
    (FIGURES / "walkthrough.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
