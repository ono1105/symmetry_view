import colorsys
import re
import unittest
from pathlib import Path


WEB_DIR = Path("crystal_viewer/web")


def _search(source: str, pattern: str) -> float:
    match = re.search(pattern, source)
    assert match is not None, f"pattern not found in the client source: {pattern}"
    return float(match.group(1))


def _hue_separation_deg(first: int, second: int) -> float:
    """How far apart two 0xRRGGBB colours are on the hue circle.

    Channel-wise distance is the wrong measure for "do these read as the same
    colour": a green and a sky blue differ mostly in one channel yet are never
    confused, while two blues differ little in any channel and are.
    """
    hues = [
        colorsys.rgb_to_hsv(*[(color >> shift & 0xFF) / 255 for shift in (16, 8, 0)])[0] * 360
        for color in (first, second)
    ]
    delta = abs(hues[0] - hues[1]) % 360
    return min(delta, 360 - delta)


class PuzzleClientContractTest(unittest.TestCase):
    def test_direct_puzzle_mode_recovers_a_missed_entry_event(self):
        source = (WEB_DIR / "puzzle.js").read_text(encoding="utf-8")
        self.assertIn('if (el("puzzle-mode")?.hidden === false) queueMicrotask(enterPuzzle);', source)

    def test_composition_uses_a_same_round_playback_generation(self):
        source = (WEB_DIR / "puzzle.js").read_text(encoding="utf-8")
        self.assertIn("playback === compositionPlaybackGeneration", source)
        self.assertIn('el("puzzle-check").disabled = true;', source)

    def test_mapping_preview_filters_animation_to_the_source_atom(self):
        puzzle_source = (WEB_DIR / "puzzle.js").read_text(encoding="utf-8")
        view_source = (WEB_DIR / "three_view.js").read_text(encoding="utf-8")
        self.assertIn("view.setAnimationSourceAtoms([question.source_atom_index]);", puzzle_source)
        self.assertIn("animationPathForInstance(instance)", view_source)

    def test_mapping_question_names_and_draws_the_operation(self):
        source = (WEB_DIR / "puzzle.js").read_text(encoding="utf-8")
        self.assertIn("shortOperationLabel(currentQuestion.operation)", source)
        self.assertIn("loadSymmetryElements(Number(question.operation_index)", source)
        self.assertIn('kind.startsWith("improper_")', source)
        self.assertIn("view.viewAlongCurrentOperation()", source)

    def test_mapping_guess_ring_stays_at_the_clicked_destination(self):
        source = (WEB_DIR / "puzzle.js").read_text(encoding="utf-8")
        self.assertIn("const guess = atomStartMarker(mappingGuess);", source)
        self.assertIn("position: [...guess.position]", source)

    def test_mapping_rings_stay_visually_separate_when_concentric(self):
        # A correct guess ends with all three rings around the same site: the
        # source follows the atom in, the guess and the answer are pinned there.
        # If two bands touch they read as one thick ring, so require every gap to
        # be a visible fraction of the atom's own radius.
        view_source = (WEB_DIR / "three_view.js").read_text(encoding="utf-8")
        puzzle_source = (WEB_DIR / "puzzle.js").read_text(encoding="utf-8")
        outer_factor = _search(view_source, r"const outerRadius = radius \* ([\d.]+);")
        inner_factor = _search(view_source, r"RingGeometry\(outerRadius \* ([\d.]+), outerRadius")
        bands = {
            "guess": _search(puzzle_source, r"radius: guess\.radius \* ([\d.]+)"),
            "source": 1.0,  # the source ring is drawn at the atom's own radius
            "target": _search(puzzle_source, r"radius: target\.radius \* ([\d.]+)"),
        }
        radii = {
            name: (factor * outer_factor * inner_factor, factor * outer_factor)
            for name, factor in bands.items()
        }
        ordered = sorted(radii.items(), key=lambda item: item[1][0])
        for (inner_name, (_, inner_outer)), (outer_name, (outer_inner, _)) in zip(
            ordered, ordered[1:]
        ):
            gap = outer_inner - inner_outer
            self.assertGreater(
                gap,
                0.02,
                f"{inner_name} and {outer_name} rings are {gap:.4f} apart and read as one band",
            )

    def test_a_structure_with_no_questions_leaves_no_dead_view_along_button(self):
        # Pressing this button with no current question does nothing, so it must
        # not survive from the previous structure.  What guarantees that is the
        # order of two things: startStructure hides it before loading anything,
        # and beginRound — the only place it is shown again — is never reached on
        # the zero-question path.
        source = (WEB_DIR / "puzzle.js").read_text(encoding="utf-8")
        prologue = source.split("async function startStructure(", 1)[1].split("await getJson(", 1)[0]
        self.assertIn('el("puzzle-view-along").hidden = true;', prologue)
        self.assertEqual(
            source.count('viewAlong.hidden = !('), 1,
            "the button is shown in more than one place; the ordering above no longer holds",
        )
        empty_branch = source.split("if (!questions.length) {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("return;", empty_branch)
        self.assertNotIn("beginRound", empty_branch)

    def test_failed_checks_restore_round_controls(self):
        source = (WEB_DIR / "puzzle.js").read_text(encoding="utf-8")
        self.assertIn("compositionQuestionReady = true;", source)
        self.assertIn("mappingQuestionReady = true;", source)

    def test_mapping_rings_are_distinguishable_from_the_symmetry_element(self):
        # The mapping quiz draws the operation's axis next to the three rings.
        # A guess ring in the axis colour left the player reading a ring as part
        # of the axis, so keep every ring well away from it on the hue circle.
        # Both colours now come from the shared colors.js module (rather than
        # being hardcoded separately in puzzle.js and three_view.js), so this
        # reads that one source of truth instead of grepping two files.
        colors_source = (WEB_DIR / "colors.js").read_text(encoding="utf-8")
        axis_color = int(re.search(r"axis:\s*0x([0-9a-f]{6})", colors_source).group(1), 16)
        rings = {
            name: int(re.search(rf"{name}:\s*0x([0-9a-f]{{6}})", colors_source).group(1), 16)
            for name in ("source", "guess", "target")
        }
        for name, color in rings.items():
            separation = _hue_separation_deg(color, axis_color)
            self.assertGreater(
                separation, 40,
                f"the {name} ring is {separation:.0f}deg from the symmetry axis colour",
            )

    def test_only_the_visible_view_keeps_a_frame_loop(self):
        # Both views live for the whole session; the covered one used to keep
        # calling controls.update() every frame behind the overlay. The handle
        # guard is what stops a resume from starting a second chain.
        view_source = (WEB_DIR / "three_view.js").read_text(encoding="utf-8")
        puzzle_source = (WEB_DIR / "puzzle.js").read_text(encoding="utf-8")
        ui_source = (WEB_DIR / "browser_ui.js").read_text(encoding="utf-8")
        self.assertIn("if (!this.active) return;", view_source)
        self.assertIn("if (this.frameHandle !== null || !this.active) return;", view_source)
        self.assertEqual(
            view_source.count("requestAnimationFrame(this.animate)"), 1,
            "the frame loop is re-armed somewhere that bypasses requestFrame()",
        )
        self.assertIn('window.addEventListener("symmetry-exit-puzzle"', puzzle_source)
        self.assertIn('window.symmetryThreeView?.setActive(appMode !== "puzzle")', ui_source)

    def test_the_analysis_poll_stops_while_the_puzzle_is_open(self):
        source = (WEB_DIR / "browser_ui.js").read_text(encoding="utf-8")
        prologue = source.split("async function refreshState() {", 1)[1].split("try {", 1)[0]
        self.assertIn('document.body.classList.contains("in-puzzle")', prologue)

    def test_operation_details_signature_identifies_the_loaded_structure(self):
        # Two structures can share operation indices (benzene and methane both
        # have 0-23), so the guard needs the load identity, and the late-arriving
        # summaries, or the panel keeps stale text.
        source = (WEB_DIR / "browser_ui.js").read_text(encoding="utf-8")
        signature = source.split("function renderOperationDetails()", 1)[1].split("});", 1)[0]
        for key in ("reload_request_id", "json_path", "element_summary", "itc_like_summary"):
            self.assertIn(key, signature, f"{key} is missing from the details signature")

    def test_operation_list_signature_reacts_to_summaries_arriving(self):
        # element_summary, the axis/plane/center group headers and the per-row
        # direction hint (operationGroupKind/operationGroupLabel) all read
        # fields that are empty until summaries_ready flips true. Reproduced
        # live: loading a structure through the picker (not a CLI-preset
        # export) rendered the list once before summaries arrived, then never
        # redrew it -- the refresh that re-fetches operations on that flip
        # (see refreshState) calls renderOperations() again, but its signature
        # ignored summariesReady, so the second call saw an unchanged
        # signature and no-opped, leaving every hint and header missing for
        # the rest of the session.
        source = (WEB_DIR / "browser_ui.js").read_text(encoding="utf-8")
        signature = source.split("function operationListRenderSignature(sorted) {", 1)[1].split(
            "\n}", 1
        )[0]
        self.assertIn("summariesReady", signature)

    def test_puzzle_atom_clicks_cannot_fall_through_to_analysis_selection(self):
        puzzle_source = (WEB_DIR / "puzzle.js").read_text(encoding="utf-8")
        view_source = (WEB_DIR / "three_view.js").read_text(encoding="utf-8")
        self.assertIn("view.disableAtomSelection = true;", puzzle_source)
        self.assertIn("if (this.disableAtomSelection) return;", view_source)


if __name__ == "__main__":
    unittest.main()
