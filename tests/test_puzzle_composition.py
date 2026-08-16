import unittest

import numpy as np

from crystal_viewer.game.composition import (
    _compose_frac_keys,
    _crystal_keys,
    _product_index,
    check_answer,
    composition_questions,
    public_questions,
)
from crystal_viewer.viewer.operation_lookup import operation_by_index
from tests.support import load_render_data as _render_data


def _operation_kind(render_data: dict, index: int) -> str:
    operation = operation_by_index(render_data.get("operations", []), index)
    return str(operation.get("kind", "")) if operation else ""


class CompositionQuizTest(unittest.TestCase):
    def test_two_mirrors_compose_to_a_rotation(self):
        # Ammonia (C3v): composing its two σv planes is the classic "two mirrors
        # make a rotation" — here the C3 about the principal axis.
        render_data = _render_data("ammonia")
        found = False
        for question in composition_questions(render_data):
            kind_a = _operation_kind(render_data, question["operation_index_a"])
            kind_b = _operation_kind(render_data, question["operation_index_b"])
            answer = question["answers"][0]
            if kind_a == "mirror" and kind_b == "mirror" and answer["kind"] == "rotation":
                found = True
                self.assertEqual(answer["order"], 3)
        self.assertTrue(found, "no mirror∘mirror=rotation composition found for ammonia")

    def test_product_is_a_distinct_nameable_group_operation(self):
        render_data = _render_data("benzene")
        operations = render_data.get("operations", [])
        indices = {int(op["index"]) for op in operations}
        questions = composition_questions(render_data)
        self.assertTrue(questions)
        nameable = {"rotation", "mirror", "inversion", "rotoreflection", "rotoinversion"}
        for question in questions:
            product = question["product_index"]
            self.assertIn(product, indices)  # the product is a real group element
            # the combination is non-trivial: the product differs from both inputs
            self.assertNotIn(product, (question["operation_index_a"], question["operation_index_b"]))
            self.assertEqual(len(question["answers"]), 1)
            self.assertIn(question["answers"][0]["kind"], nameable)

    def test_molecule_composition_uses_cartesian(self):
        # Molecules have no lattice (matrix_frac is null); the Cartesian path must
        # still find products. Methane (Td) has S4, C3, C2, σd.
        methane = _render_data("methane")
        self.assertIsNone(methane.get("unit_cell"))
        self.assertTrue(composition_questions(methane))

    def test_crystal_composition_is_capped_but_covers_product_types(self):
        # Halite (Fm-3m) has thousands of composition pairs; the cap keeps the list
        # small while still covering every product type at least once.
        questions = composition_questions(_render_data("halite"))
        self.assertTrue(questions)
        self.assertLessEqual(len(questions), 80)
        product_kinds = {q["answers"][0]["kind"] for q in questions}
        self.assertIn("rotation", product_kinds)
        self.assertIn("rotoinversion", product_kinds)

    def test_cap_keeps_textbook_mirror_mirror_products(self):
        for name in ("sulfur_hexafluoride", "halite"):
            render_data = _render_data(name)
            operations = render_data.get("operations", [])
            pairs = [
                question
                for question in composition_questions(render_data)
                if _operation_kind(render_data, question["operation_index_a"]) == "mirror"
                and _operation_kind(render_data, question["operation_index_b"]) == "mirror"
                and question["answers"][0]["kind"] == "rotation"
            ]
            self.assertTrue(pairs, f"{name} lost mirror × mirror = rotation under the cap")
            # Cubic Oh has perpendicular, 60-degree and 45-degree mirror-plane
            # pairs, yielding C2, C3 and C4.  A pre-composition representative cap
            # used to silently discard the C3 case.
            self.assertEqual(
                {question["answers"][0]["order"] for question in pairs},
                {2, 3, 4},
                f"{name} lost a textbook mirror-pair rotation order",
            )

    def test_water_cartesian_products_resolve_to_unique_group_elements(self):
        render_data = _render_data("water")
        operations = render_data["operations"]
        # PointGroupAnalyzer's water matrices carry ~1.6e-3 residuals.  All six
        # non-identity ordered products must still resolve by nearest unique match.
        for first, second in ((0, 1), (1, 0), (0, 3), (3, 0), (1, 3), (3, 1)):
            with self.subTest(first=first, second=second):
                self.assertIsNotNone(
                    _product_index(
                        operations[first],
                        operations[second],
                        operations,
                        is_crystal=False,
                    )
                )

    def test_off_grid_translation_falls_back_instead_of_snapping(self):
        # 0.01 is not on the 1/24 grid, so the fast path must refuse it rather than
        # round it to 0 and hand back the identity at index 0.  The fallback scan
        # then has to find the true product at index 1.
        identity = {
            "index": 0,
            "matrix_frac": np.eye(3).tolist(),
            "translation_frac": [0.0, 0.0, 0.0],
        }
        shifted = {
            "index": 1,
            "matrix_frac": np.eye(3).tolist(),
            "translation_frac": [0.01, 0.0, 0.0],
        }
        operations = [identity, shifted]
        lookup, keys = _crystal_keys(operations)
        self.assertNotIn(1, keys)  # off the grid: no key, hence no fast path
        self.assertEqual(
            _product_index(
                identity,
                shifted,
                operations,
                is_crystal=True,
                crystal_lookup=lookup,
                crystal_keys=keys,
            ),
            1,
        )

    def test_composed_key_matches_the_product_of_the_operations(self):
        # The integer key composition stands in for W_B·W_A and W_B·t_A + t_B, so
        # it has to agree with those matrices exactly — including the wrap of a
        # translation past one lattice vector.
        a_w = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])  # 4-fold about c
        a_t = np.array([0.5, 0.0, 0.25])
        b_w = np.array([[-1, 0, 0], [0, 1, 0], [0, 0, -1]])  # 2-fold about b
        b_t = np.array([0.0, 0.5, 0.75])
        first = {"index": 0, "matrix_frac": a_w.tolist(), "translation_frac": a_t.tolist()}
        second = {"index": 1, "matrix_frac": b_w.tolist(), "translation_frac": b_t.tolist()}
        _, keys = _crystal_keys([first, second])
        composed_w, composed_t = _compose_frac_keys(keys[0], keys[1])
        np.testing.assert_array_equal(np.array(composed_w).reshape(3, 3), b_w @ a_w)
        np.testing.assert_allclose(
            np.array(composed_t) / 24.0, (b_w @ a_t + b_t) % 1.0, atol=1e-12
        )

    def test_repeated_calls_reuse_the_cached_question_list(self):
        # A single player action asks for the questions twice (public list, then
        # /check).  Recomputing ~19k ordered pairs for the second call is what made
        # halite pause for over a second per answer.
        render_data = _render_data("halite")
        first = composition_questions(render_data)
        self.assertIs(composition_questions(render_data), first)
        # A different structure must not be served the previous one's questions.
        other = composition_questions(_render_data("benzene"))
        self.assertIsNot(other, first)
        self.assertIs(composition_questions(render_data), composition_questions(render_data))

    def test_check_answer_accepts_product_and_rejects_others(self):
        render_data = _render_data("benzene")
        questions = composition_questions(render_data)
        rotation = next(q for q in questions if q["answers"][0]["kind"] == "rotation")
        qid = questions.index(rotation)
        answer = rotation["answers"][0]
        good = check_answer(render_data, qid, "rotation", answer["order"])
        self.assertTrue(good["correct"])
        self.assertEqual(good["product_index"], rotation["product_index"])
        self.assertIn("notation", good["answers"][0])
        self.assertFalse(check_answer(render_data, qid, "mirror", None)["correct"])
        self.assertFalse(check_answer(render_data, qid, "rotation", 5)["correct"])  # wrong fold

    def test_public_questions_hide_the_answer(self):
        render_data = _render_data("methane")
        public = public_questions(render_data)
        self.assertTrue(public)
        for question in public:
            self.assertIn("operation_index_a", question)
            self.assertIn("operation_index_b", question)
            self.assertIn("operation_a", question)
            self.assertIn("operation_b", question)
            self.assertIn("kind", question["operation_a"])
            self.assertIn("kind", question["operation_b"])
            self.assertIn("group", question)
            self.assertNotIn("answers", question)
            self.assertNotIn("product_index", question)
        # same product name -> same opaque group id
        groups = {question["group"] for question in public}
        self.assertTrue(groups)

    def test_no_composition_yields_empty_list(self):
        # CO2 (linear): its two moving operations compose to a motionless operation,
        # so there is no moving-product composition to ask.
        self.assertEqual(composition_questions(_render_data("carbon_dioxide")), [])

    def test_unknown_question_id(self):
        self.assertIsNone(check_answer(_render_data("methane"), 999, "rotation", 3))


if __name__ == "__main__":
    unittest.main()
