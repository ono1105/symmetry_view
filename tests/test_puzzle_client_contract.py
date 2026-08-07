import re
import unittest
from pathlib import Path


WEB_DIR = Path("crystal_viewer/web")


def _search(source: str, pattern: str) -> float:
    match = re.search(pattern, source)
    assert match is not None, f"pattern not found in the client source: {pattern}"
    return float(match.group(1))


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

    def test_a_structure_with_no_questions_hides_the_view_along_button(self):
        # The zero-question path returns before beginRound(), which is what
        # normally decides this button's visibility; without an explicit hide the
        # button survives from the previous structure and does nothing when
        # pressed (currentQuestion is null).
        source = (WEB_DIR / "puzzle.js").read_text(encoding="utf-8")
        empty_branch = source.split("if (!questions.length) {", 1)[1].split("\n  }", 1)[0]
        self.assertIn('el("puzzle-view-along").hidden = true;', empty_branch)

    def test_failed_checks_restore_round_controls(self):
        source = (WEB_DIR / "puzzle.js").read_text(encoding="utf-8")
        self.assertIn("compositionQuestionReady = true;", source)
        self.assertIn("mappingQuestionReady = true;", source)

    def test_puzzle_atom_clicks_cannot_fall_through_to_analysis_selection(self):
        puzzle_source = (WEB_DIR / "puzzle.js").read_text(encoding="utf-8")
        view_source = (WEB_DIR / "three_view.js").read_text(encoding="utf-8")
        self.assertIn("view.disableAtomSelection = true;", puzzle_source)
        self.assertIn("if (this.disableAtomSelection) return;", view_source)


if __name__ == "__main__":
    unittest.main()
