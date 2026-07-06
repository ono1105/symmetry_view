import json
import unittest
from pathlib import Path

from crystal_viewer.game.axis_orders import (
    check_answer,
    public_questions,
    rotation_axis_questions,
)


def _render_data(name):
    return json.loads(Path(f"exports/json/{name}.json").read_text(encoding="utf-8"))["render_data"]


def _summary(name):
    questions = rotation_axis_questions(_render_data(name))
    return sorted((tuple(q["correct_orders"]), q["equivalent_count"]) for q in questions)


class AxisOrderPuzzleTest(unittest.TestCase):
    def test_water_single_c2(self):
        self.assertEqual(_summary("water"), [((2,), 1)])

    def test_ammonia_single_c3(self):
        self.assertEqual(_summary("ammonia"), [((3,), 1)])

    def test_benzene_main_axis_and_two_perpendicular_c2_classes(self):
        # D6h: the principal axis carries C6/C3/C2 -> {2,3,6}; the six
        # perpendicular C2 axes split into two symmetry-inequivalent classes
        # of three (through atoms vs through bonds).
        self.assertEqual(
            _summary("benzene"),
            [((2,), 3), ((2,), 3), ((2, 3, 6), 1)],
        )

    def test_methane_c3_and_c2_classes(self):
        # Td: four equivalent C3 axes, three C2 axes (coincident with S4).
        self.assertEqual(_summary("methane"), [((2,), 3), ((3,), 4)])

    def test_public_questions_hide_the_correct_answer(self):
        questions = public_questions(_render_data("benzene"))
        self.assertEqual([q["id"] for q in questions], [0, 1, 2])
        for question in questions:
            self.assertNotIn("correct_orders", question)
            self.assertEqual(question["options"], [2, 3, 4, 6])

    def test_check_answer_judges_and_reveals(self):
        render_data = _render_data("benzene")
        # id 0 is benzene's principal axis: correct set {2, 3, 6}.
        hit = check_answer(render_data, 0, [6, 3, 2])
        self.assertTrue(hit["correct"])
        self.assertEqual(hit["correct_orders"], [2, 3, 6])
        miss = check_answer(render_data, 0, [6])
        self.assertFalse(miss["correct"])
        self.assertEqual(miss["correct_orders"], [2, 3, 6])  # revealed on a miss too
        self.assertIsNone(check_answer(render_data, 99, [2]))


if __name__ == "__main__":
    unittest.main()
