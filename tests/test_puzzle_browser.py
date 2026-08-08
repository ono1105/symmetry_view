"""End-to-end checks that drive the real puzzle UI in headless Chromium.

Everything else in the suite stops at the HTTP boundary or at the JavaScript
source; this file plays the quizzes the way a person does, so it covers what
only the browser can show: that the prompt on screen names the operation the
server published, that a structure with no questions leaves no dead controls
behind, and that answering a high-symmetry crystal does not stall the page.

Requires the test-only extras (see requirements-dev.txt):

    .venv/bin/python -m pip install -r requirements-dev.txt
    .venv/bin/playwright install chromium

The whole module skips itself when playwright or the browser binary is missing,
so neither is needed to run the rest of the tests or to package the viewer.
"""

import json
import re
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - exercised only where the extra is absent
    sync_playwright = None

ROOT = Path(__file__).resolve().parent.parent
# Long enough for a cold structure load (analysis + export + first render), which
# dominates every wait here; the assertions below carry their own tighter budgets.
LOAD_TIMEOUT_MS = 90000
READY = '() => !document.getElementById("puzzle-check").disabled'
VERDICT = """() => {
  const box = document.getElementById('puzzle-result');
  return !box.hidden && box.textContent.includes('正解');
}"""


def _browser_available() -> bool:
    if sync_playwright is None:
        return False
    try:
        with sync_playwright() as play:
            play.chromium.launch().close()
        return True
    except Exception:
        return False


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@unittest.skipUnless(_browser_available(), "playwright + chromium are not installed")
class PuzzleBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server = subprocess.Popen(
            [sys.executable, "tools/view_json_server.py", "--port", str(cls.port),
             "--no-browser", "--mode", "puzzle"],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(cls.base_url + "/api/state", timeout=1).read()
                break
            except (urllib.error.URLError, OSError):
                time.sleep(0.3)
        else:
            cls.server.kill()
            raise RuntimeError("the puzzle server did not come up")

        cls.play = sync_playwright().start()
        cls.browser = cls.play.chromium.launch()
        cls.page = cls.browser.new_page(viewport={"width": 1280, "height": 900})
        cls.errors = []
        cls.page.on("pageerror", lambda exc: cls.errors.append(str(exc)))
        cls.page.goto(cls.base_url, wait_until="networkidle")
        cls.page.wait_for_selector(".puzzle-quiz-card", state="visible", timeout=30000)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.play.stop()
        cls.server.terminate()
        try:
            cls.server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.server.kill()

    # --- driving the UI the way a player does ---------------------------------

    def text(self, selector: str) -> str:
        return (self.page.text_content(selector) or "").strip()

    def open_quiz(self, quiz: str, structure: str, kind: str = "分子"):
        """Quiz select -> structure picker -> a playable round."""
        page = self.page
        if page.is_hidden(".puzzle-quiz-card"):
            if page.is_hidden("#puzzle-picker"):
                page.click("#puzzle-other")
                page.wait_for_selector(".puzzle-structure", state="visible")
            page.click("#puzzle-picker-back")
            page.wait_for_selector(".puzzle-quiz-card", state="visible")
        page.click(f'.puzzle-quiz-card[data-quiz="{quiz}"]')
        # buildPicker() is async, so wait for it before reaching for its buttons.
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

    def answer_operation_quiz(self) -> tuple[str, float]:
        """Tick a kind (plus a fold when one is needed) and press 回答.

        Pressing 回答 while the operations are still playing is answered with a
        prompt in the same box, which is intended behaviour — retry until the box
        holds a verdict.
        """
        page = self.page
        for _ in range(60):
            page.wait_for_function(READY, timeout=LOAD_TIMEOUT_MS)
            page.locator('#puzzle-options input[name="op-kind"]').first.check()
            orders = page.locator('#puzzle-options input[name="op-order"]')
            if orders.count():
                orders.first.check()
            started = time.perf_counter()
            page.click("#puzzle-check")
            try:
                page.wait_for_function(VERDICT, timeout=8000)
            except Exception:
                page.wait_for_timeout(200)
                continue
            return self.text("#puzzle-result"), time.perf_counter() - started
        self.fail(f"no verdict; the result box said {self.text('#puzzle-result')!r}")

    def next_round(self):
        self.page.wait_for_selector("#puzzle-again:not([hidden])", timeout=LOAD_TIMEOUT_MS)
        self.page.click("#puzzle-again")
        self.page.wait_for_function(
            '() => document.getElementById("puzzle-result").hidden', timeout=LOAD_TIMEOUT_MS)

    def ring_count(self) -> int:
        return int(self.page.evaluate(
            "() => document.getElementById('puzzle-view')?.dataset?.pickMarkerCount ?? 0"))

    # --- the checks -----------------------------------------------------------

    def test_mapping_prompt_names_an_operation_the_server_published(self):
        # benzene's principal axis is labelled S6 but also carries S3, so the
        # prompt has to name the operation being asked about, not its axis.
        self.open_quiz("mapping", "C6H6")
        self.page.wait_for_function(READY, timeout=LOAD_TIMEOUT_MS)
        published = json.loads(
            urllib.request.urlopen(self.base_url + "/api/puzzle/mapping", timeout=10).read()
        )["questions"]
        labels = {q["operation"]["notation"] for q in published}
        self.assertIn("S3", labels)
        self.assertIn("S6", labels)
        # The client rewrites "sigma" to σ and drops underscores for display.
        shown = {label.replace("sigma", "σ").replace("_", "") for label in labels}
        for _ in range(6):
            match = re.search(r"操作 (\S+) で", self.text("#puzzle-question"))
            self.assertIsNotNone(match, "the mapping prompt must name the operation")
            self.assertIn(match.group(1), shown)
            self.page.click("#puzzle-other")
            self.page.wait_for_selector(".puzzle-structure", state="visible")
            self.page.click('.puzzle-structure:has-text("C6H6")')
            self.page.wait_for_function(READY, timeout=LOAD_TIMEOUT_MS)

    def test_answering_adds_the_target_ring_to_the_source_and_guess_rings(self):
        self.open_quiz("mapping", "C6H6")
        self.page.wait_for_function(READY, timeout=LOAD_TIMEOUT_MS)
        self.assertEqual(self.ring_count(), 1, "the source atom is ringed on its own first")
        box = self.page.locator("#puzzle-view").bounding_box()
        for fy in (0.5, 0.4, 0.6, 0.32, 0.68):
            for fx in (0.5, 0.4, 0.6, 0.32, 0.68, 0.24, 0.76):
                self.page.mouse.click(box["x"] + box["width"] * fx,
                                      box["y"] + box["height"] * fy)
                self.page.wait_for_timeout(40)
                if self.ring_count() > 1:
                    break
            if self.ring_count() > 1:
                break
        self.assertEqual(self.ring_count(), 2, "clicking a destination adds the guess ring")
        self.page.click("#puzzle-check")
        self.page.wait_for_function(VERDICT, timeout=LOAD_TIMEOUT_MS)
        self.page.wait_for_timeout(2500)  # let the reveal animation land
        self.assertEqual(self.ring_count(), 3,
                         "the answer ring joins the source and guess rings")

    def test_structure_with_no_questions_leaves_no_dead_controls(self):
        # HCl has no mapping question. This path returns before beginRound(),
        # which is what normally decides the buttons, so a leftover 「操作要素方向
        # から見る」 would sit there doing nothing when pressed.
        self.open_quiz("mapping", "C6H6")
        self.page.wait_for_function(READY, timeout=LOAD_TIMEOUT_MS)
        self.assertTrue(self.page.is_visible("#puzzle-view-along"))
        self.page.click("#puzzle-other")
        self.page.wait_for_selector(".puzzle-structure", state="visible")
        self.page.click('.puzzle-structure:has-text("HCl")')
        self.page.wait_for_function(
            '() => document.getElementById("puzzle-question").textContent.includes("ありません")',
            timeout=LOAD_TIMEOUT_MS,
        )
        self.assertTrue(self.page.is_hidden("#puzzle-view-along"))
        self.assertTrue(self.page.is_hidden("#puzzle-check"))
        self.assertTrue(self.page.is_hidden("#puzzle-playback"))

    def test_composition_reveal_never_prints_two_conflicting_notations(self):
        # "回映（S3）（S6）" is what an axis-derived label produced: the kind label
        # spells out the fold, and the notation used to contradict it.
        self.open_quiz("composition", "C6H6")
        verdicts = []
        for _ in range(8):
            verdict, _ = self.answer_operation_quiz()
            verdicts.append(verdict)
            self.next_round()
        for verdict in verdicts:
            self.assertIsNone(
                re.search(r"（S\d+）（|（-\d+）（", verdict),
                f"the reveal contradicts itself: {verdict}",
            )
            self.assertRegex(verdict, r"正解")

    def test_answering_a_high_symmetry_crystal_stays_responsive(self):
        # Halite evaluates ~19k ordered pairs. Before the integer fast path and
        # the question cache, every answer stalled the page for about 1.5s.
        self.open_quiz("composition", "NaCl", kind="結晶")
        elapsed = []
        for _ in range(3):
            _, seconds = self.answer_operation_quiz()
            elapsed.append(seconds)
            self.next_round()
        self.assertLess(max(elapsed), 1.0,
                        f"answering halite took {max(elapsed):.2f}s on screen")

    def test_no_uncaught_page_errors(self):
        self.assertEqual(self.errors, [])


if __name__ == "__main__":
    unittest.main()
