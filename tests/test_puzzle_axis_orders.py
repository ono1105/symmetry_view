import json
import unittest
from pathlib import Path

from crystal_viewer.game.axis_orders import rotation_axis_questions


def _summary(name):
    payload = json.loads(Path(f"exports/json/{name}.json").read_text(encoding="utf-8"))
    questions = rotation_axis_questions(payload["render_data"])
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


if __name__ == "__main__":
    unittest.main()
