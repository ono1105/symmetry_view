import json
import unittest
from pathlib import Path

import numpy as np

from crystal_viewer.game.operation_identify import (
    TRANSLATION_SHIFT_OPTIONS,
    check_answer,
    identify_questions,
    public_questions,
)

EXPORT_DIR = Path("exports/json")


def _render_data(name: str) -> dict:
    payload = json.loads((EXPORT_DIR / f"{name}.json").read_text())
    return payload.get("render_data", payload)


def _answer_sets(name: str, difficulty: str = "normal"):
    return [
        frozenset((a["kind"], a["order"]) for a in q["answers"])
        for q in identify_questions(_render_data(name), difficulty)
    ]


def _all_answers(name: str, difficulty: str = "normal"):
    return {answer for question in _answer_sets(name, difficulty) for answer in question}


def _first_unambiguous(name: str, kind: str, order):
    render_data = _render_data(name)
    questions = identify_questions(render_data)
    for index, question in enumerate(questions):
        answers = question["answers"]
        if len(answers) == 1 and answers[0]["kind"] == kind and answers[0]["order"] == order:
            return render_data, index
    raise AssertionError(f"no unambiguous {kind}/{order} question in {name}")


class OperationIdentifyTest(unittest.TestCase):
    def test_only_basic_moving_operations_are_asked(self):
        # Water (C2v): the C2 and the perpendicular mirror. The in-plane mirror
        # moves nothing; identity/improper are not basic answers.
        self.assertEqual(_all_answers("water"), {("mirror", None), ("rotation", 2)})

    def test_motionless_operations_are_dropped(self):
        render_data = _render_data("water")
        atoms = np.array([a["cart"] for a in render_data["atoms"]])
        for question in identify_questions(render_data):
            op = render_data["operations"][question["operation_index"]]
            m = np.asarray(op["matrix_cart"], dtype=float)
            t = np.asarray(op.get("translation_cart") or [0, 0, 0], dtype=float)
            self.assertGreater(np.linalg.norm((atoms @ m.T) + t - atoms, axis=1).max(), 1e-2)

    def test_coincident_operations_merge_and_accept_either_answer(self):
        # CO2: the inversion and the perpendicular mirror move both O atoms the
        # same straight way -> one question, both 反転 and 鏡映 correct (never empty).
        co2 = _render_data("carbon_dioxide")
        questions = identify_questions(co2)
        self.assertTrue(questions)  # must not be left with zero questions
        merged = next(q for q in questions if len(q["answers"]) > 1)
        kinds = {a["kind"] for a in merged["answers"]}
        self.assertEqual(kinds, {"inversion", "mirror"})
        qid = questions.index(merged)
        self.assertTrue(check_answer(co2, qid, "inversion")["correct"])
        self.assertTrue(check_answer(co2, qid, "mirror")["correct"])
        self.assertFalse(check_answer(co2, qid, "rotation", 2)["correct"])

    def test_planar_molecule_merges_rotation_and_rotoreflection(self):
        # Benzene is planar, so σh does nothing to the atoms: Cn and Sn about the
        # main axis coincide and are asked as one question accepting either name.
        self.assertIn(frozenset({("rotation", 6), ("rotoreflection", 6)}), _answer_sets("benzene"))

    def test_rotoreflection_is_asked_for_non_planar_molecule(self):
        # Methane (Td) has S4 but no C4, so the rotoreflection is unambiguous.
        render_data, qid = _first_unambiguous("methane", "rotoreflection", 4)
        self.assertTrue(check_answer(render_data, qid, "rotoreflection", 4)["correct"])
        self.assertFalse(check_answer(render_data, qid, "rotoreflection", 3)["correct"])
        self.assertFalse(check_answer(render_data, qid, "rotation", 4)["correct"])

    def test_rotoinversion_is_asked_for_crystal(self):
        rotoinversions = {order for kind, order in _all_answers("halite") if kind == "rotoinversion"}
        self.assertTrue(rotoinversions)
        self.assertTrue(rotoinversions.issubset({3, 4, 6}))

    def test_hard_mode_asks_only_translation_operations(self):
        answers = _all_answers("halite", "hard")
        self.assertTrue(answers)
        self.assertEqual({kind for kind, _ in answers}, {"screw", "glide"})
        render_data = _render_data("halite")
        questions = identify_questions(render_data, "hard")
        screw = next(i for i, q in enumerate(questions) if q["answers"][0]["kind"] == "screw")
        answer = questions[screw]["answers"][0]
        wrong_shift = next(shift for shift in TRANSLATION_SHIFT_OPTIONS if shift != answer["shift"])
        self.assertIn(answer["shift"], TRANSLATION_SHIFT_OPTIONS)
        self.assertIn("symbol", answer)
        self.assertIn("notation", answer)
        self.assertTrue(
            check_answer(
                render_data,
                screw,
                "screw",
                answer["order"],
                "hard",
                selected_shift=answer["shift"],
            )["correct"]
        )
        self.assertFalse(
            check_answer(
                render_data,
                screw,
                "screw",
                answer["order"],
                "hard",
                selected_shift=wrong_shift,
            )["correct"]
        )
        self.assertFalse(check_answer(render_data, screw, "glide", None, "hard")["correct"])

    def test_hard_mode_glide_requires_translation_component(self):
        render_data = _render_data("halite")
        questions = identify_questions(render_data, "hard")
        glide = next(i for i, q in enumerate(questions) if q["answers"][0]["kind"] == "glide")
        answer = questions[glide]["answers"][0]
        self.assertIn(answer["shift"], TRANSLATION_SHIFT_OPTIONS)
        self.assertIn("symbol", answer)
        self.assertIn("notation", answer)
        self.assertTrue(
            check_answer(
                render_data,
                glide,
                "glide",
                None,
                "hard",
                selected_shift=answer["shift"],
            )["correct"]
        )
        self.assertFalse(check_answer(render_data, glide, "glide", None, "hard")["correct"])

    def test_hard_mode_empty_for_molecule(self):
        # Molecules have no screw/glide, so the hard operation quiz is crystal-only.
        self.assertEqual(identify_questions(_render_data("water"), "hard"), [])

    def test_all_mode_combines_point_and_translation_operations_for_crystal(self):
        answers = _all_answers("halite", "all")
        self.assertIn(("rotation", 4), answers)
        self.assertIn(("rotoinversion", 3), answers)
        self.assertIn(("screw", 4), answers)
        self.assertIn(("glide", None), answers)

    def test_check_rotation_requires_kind_and_order(self):
        render_data, qid = _first_unambiguous("methane", "rotation", 3)
        self.assertTrue(check_answer(render_data, qid, "rotation", 3)["correct"])
        self.assertFalse(check_answer(render_data, qid, "rotation", 2)["correct"])  # wrong fold
        self.assertFalse(check_answer(render_data, qid, "mirror", None)["correct"])  # wrong kind

    def test_check_mirror_ignores_order(self):
        render_data = _render_data("water")
        questions = identify_questions(render_data)
        qid = next(
            i
            for i, q in enumerate(questions)
            if len(q["answers"]) == 1
            and q["answers"][0]["kind"] == "mirror"
            and q["answers"][0]["order"] is None
        )
        self.assertTrue(check_answer(render_data, qid, "mirror")["correct"])

    def test_public_questions_hide_the_answer(self):
        questions = public_questions(_render_data("water"))
        self.assertEqual([q["id"] for q in questions], [0, 1])
        for question in questions:
            self.assertIn("operation_index", question)
            self.assertNotIn("answers", question)
            self.assertNotIn("symbol", question)
            self.assertNotIn("notation", question)
            self.assertNotIn("shift", question)

    def test_unknown_question_id(self):
        self.assertIsNone(check_answer(_render_data("water"), 99, "mirror"))


if __name__ == "__main__":
    unittest.main()
