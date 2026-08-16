import math
import unittest

from crystal_viewer.game.axis_orders import (
    _improper_order,
    axis_questions,
    check_answer,
    public_questions,
    rotation_axis_questions,
)
from tests.support import load_render_data as _render_data


def _rotoreflection_operation(angle_deg):
    """An S operation about z: rotate by angle_deg, then reflect through z=0."""
    angle = math.radians(angle_deg)
    cos, sin = math.cos(angle), math.sin(angle)
    return {"matrix_cart": [[cos, -sin, 0.0], [sin, cos, 0.0], [0.0, 0.0, -1.0]]}


def _summary(name, kind="rotation"):
    questions = axis_questions(_render_data(name), kind)
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

    def test_improper_sn_axes(self):
        # C2v / C3v have no S_n axes.
        self.assertEqual(_summary("water", "improper"), [])
        self.assertEqual(_summary("ammonia", "improper"), [])
        # Td: three S4 axes (coincident with the C2 axes).
        self.assertEqual(_summary("methane", "improper"), [((4,), 3)])
        # D6h main axis carries both S6 (60 deg) and S3 (120 deg); their matrix
        # order is 6 for both, so this only comes out right by reading the
        # rotoreflection angle rather than the matrix period.
        self.assertEqual(_summary("benzene", "improper"), [((3, 6), 1)])

    def test_a_power_of_an_s10_axis_does_not_become_a_phantom_s3(self):
        # S10^3 turns by 108 deg, and 360/108 rounds to 3. Naming it S3 would put
        # a fold on the axis that is not there, so the index is only accepted
        # when 360/n reproduces the angle.
        self.assertIsNone(_improper_order(_rotoreflection_operation(108.0)))
        self.assertEqual(_improper_order(_rotoreflection_operation(120.0)), 3)
        self.assertEqual(_improper_order(_rotoreflection_operation(36.0)), 10)

    def test_public_and_check_support_improper(self):
        render_data = _render_data("methane")
        questions = public_questions(render_data, "improper")
        self.assertTrue(questions)
        self.assertNotIn("correct_orders", questions[0])
        hit = check_answer(render_data, 0, 4, "improper")
        self.assertTrue(hit["correct"])
        self.assertEqual(hit["answer"], 4)

    def test_public_questions_hide_the_correct_answer(self):
        questions = public_questions(_render_data("benzene"))
        self.assertEqual([q["id"] for q in questions], [0, 1, 2])
        for question in questions:
            self.assertNotIn("correct_orders", question)
            self.assertEqual(question["options"], [2, 3, 4, 6])

    def test_check_answer_judges_and_reveals(self):
        render_data = _render_data("benzene")
        # id 0 is benzene's principal axis: highest fold is 6.
        hit = check_answer(render_data, 0, 6)
        self.assertTrue(hit["correct"])
        self.assertEqual(hit["answer"], 6)
        self.assertIsNotNone(hit["reveal_operation"])  # the 6-fold rotation to play
        miss = check_answer(render_data, 0, 3)
        self.assertFalse(miss["correct"])
        self.assertEqual(miss["answer"], 6)  # revealed on a miss too
        self.assertIsNone(check_answer(render_data, 99, 2))


if __name__ == "__main__":
    unittest.main()
