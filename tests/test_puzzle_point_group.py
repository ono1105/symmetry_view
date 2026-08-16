import unittest

from crystal_viewer.game.point_group import (
    _CRYSTAL_PROPS,
    _SCHOENFLIES,
    _distractors,
    check_answer,
    point_group_question,
    public_questions,
)
from tests.support import load_render_data as _render_data


class PointGroupTableTest(unittest.TestCase):
    """The distractor table is meant to reproduce textbook confusions on its own,
    from group order / principal fold / notational family alone -- not from a
    hand-listed table of pairs (docs/CLAUDE_HANDOFF.md warns against those)."""

    def test_same_order_different_mirror_placement_is_the_top_distractor(self):
        self.assertEqual(_distractors("D3h", _SCHOENFLIES)[0], "D3d")
        self.assertEqual(_distractors("D3d", _SCHOENFLIES)[0], "D3h")
        self.assertEqual(_distractors("C2v", _SCHOENFLIES)[0], "C2h")
        self.assertEqual(_distractors("C2h", _SCHOENFLIES)[0], "C2v")

    def test_cubic_groups_are_confusable(self):
        # Oh (SF6) and Td (methane) are the two cubic point groups the bundled
        # molecules actually use.
        self.assertIn("Td", _distractors("Oh", _SCHOENFLIES))
        # Not required the other way: T (chiral tetrahedral, no mirrors at all)
        # sits exactly as close to Td by order and matches its principal fold
        # exactly, so it legitimately outranks Oh in Td's own pool -- Th and T
        # are still both genuine cubic-family distractors for Td.
        self.assertEqual(
            {"Th", "T"} & set(_distractors("Td", _SCHOENFLIES)), {"Th", "T"}
        )

    def test_crystal_and_molecular_vocabularies_do_not_cross(self):
        # A crystal question must never offer a Schoenflies-only distractor
        # (and there is no Schoenflies table entry that looks like an HM symbol).
        for distractor in _distractors("m-3m", _CRYSTAL_PROPS):
            self.assertIn(distractor, _CRYSTAL_PROPS)
            self.assertNotIn(distractor, _SCHOENFLIES)


class PointGroupQuizTest(unittest.TestCase):
    def test_molecule_question_offers_four_choices_including_the_answer(self):
        render_data = _render_data("benzene")  # D6h
        question = point_group_question(render_data)
        self.assertEqual(question["correct"], "D6h")
        self.assertEqual(len(question["options"]), 4)
        self.assertIn("D6h", question["options"])

    def test_crystal_question_uses_hm_notation_not_schoenflies(self):
        render_data = _render_data("halite")  # m-3m
        question = point_group_question(render_data)
        self.assertEqual(question["correct"], "m-3m")
        for option in question["options"]:
            self.assertIn(option, _CRYSTAL_PROPS)

    def test_public_questions_hide_the_correct_answer(self):
        render_data = _render_data("water")  # C2v
        questions = public_questions(render_data)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["id"], 0)
        self.assertNotIn("correct", questions[0])
        self.assertEqual(len(questions[0]["options"]), 4)
        self.assertIn("C2v", questions[0]["options"])

    def test_check_answer_judges_molecule_and_crystal(self):
        render_data = _render_data("water")
        hit = check_answer(render_data, 0, "C2v")
        self.assertTrue(hit["correct"])
        self.assertEqual(hit["answer"], "C2v")
        miss = check_answer(render_data, 0, "C2h")
        self.assertFalse(miss["correct"])
        self.assertEqual(miss["answer"], "C2v")  # revealed on a miss too
        self.assertIsNone(check_answer(render_data, 1, "C2v"))

        crystal_data = _render_data("halite")
        self.assertTrue(check_answer(crystal_data, 0, "m-3m")["correct"])
        self.assertFalse(check_answer(crystal_data, 0, "m-3")["correct"])

    def test_no_symmetry_is_itself_an_answerable_point_group(self):
        # bromochlorofluoromethane (C1) is bundled to show what "no symmetry"
        # looks like; it has zero questions in the other four quizzes, but
        # naming its point group as C1 is a legitimate question on its own.
        render_data = _render_data("bromochlorofluoromethane")
        question = point_group_question(render_data)
        self.assertEqual(question["correct"], "C1")


if __name__ == "__main__":
    unittest.main()
