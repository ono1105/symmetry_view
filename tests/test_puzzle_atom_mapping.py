import unittest

import numpy as np

from crystal_viewer.game.atom_mapping import (
    check_answer,
    mapping_questions,
    public_questions,
)
from tests.support import load_render_data as _render_data


def _atoms_by_index(render_data: dict) -> dict:
    return {
        int(atom["index"]): atom
        for atom in render_data.get("atoms", [])
        if atom.get("cart") is not None
    }


def _operation(render_data: dict, index: int) -> dict:
    return next(op for op in render_data["operations"] if int(op["index"]) == index)


class AtomMappingTest(unittest.TestCase):
    def test_target_is_the_geometric_image_of_the_source(self):
        render_data = _render_data("benzene")
        atoms = _atoms_by_index(render_data)
        questions = mapping_questions(render_data)
        self.assertTrue(questions)
        for question in questions:
            op = _operation(render_data, question["operation_index"])
            matrix = np.asarray(op["matrix_cart"], dtype=float)
            translation = np.asarray(op.get("translation_cart") or [0, 0, 0], dtype=float)
            source = np.asarray(atoms[question["source_atom_index"]]["cart"], dtype=float)
            target = np.asarray(atoms[question["target_atom_index"]]["cart"], dtype=float)
            image = matrix @ source + translation
            self.assertLess(float(np.linalg.norm(image - target)), 1e-2)

    def test_source_and_target_are_distinct_same_element(self):
        render_data = _render_data("methane")
        atoms = _atoms_by_index(render_data)
        for question in mapping_questions(render_data):
            self.assertNotEqual(question["source_atom_index"], question["target_atom_index"])
            self.assertEqual(
                atoms[question["source_atom_index"]]["element"],
                atoms[question["target_atom_index"]]["element"],
            )

    def test_fixed_central_atom_is_never_a_source(self):
        # Methane's carbon sits at the origin and every point operation fixes it,
        # so it can never be a "where does it go?" source.
        render_data = _render_data("methane")
        carbon = next(a for a in render_data["atoms"] if a.get("element") == "C")
        sources = {q["source_atom_index"] for q in mapping_questions(render_data)}
        self.assertNotIn(int(carbon["index"]), sources)

    def test_capped_benzene_questions_cover_carbon_and_hydrogen(self):
        render_data = _render_data("benzene")
        atoms = _atoms_by_index(render_data)
        source_elements = {
            atoms[question["source_atom_index"]]["element"]
            for question in mapping_questions(render_data)
        }
        self.assertEqual(source_elements, {"C", "H"})

    def test_check_answer_accepts_target_and_rejects_others(self):
        render_data = _render_data("benzene")
        questions = mapping_questions(render_data)
        result = check_answer(render_data, 0, questions[0]["target_atom_index"])
        self.assertTrue(result["correct"])
        self.assertEqual(result["target_atom_index"], questions[0]["target_atom_index"])
        self.assertFalse(check_answer(render_data, 0, questions[0]["source_atom_index"])["correct"])

    def test_public_questions_hide_the_target(self):
        render_data = _render_data("ammonia")
        public = public_questions(render_data)
        self.assertTrue(public)
        for question in public:
            self.assertIn("operation_index", question)
            self.assertIn("operation", question)
            self.assertIn("kind", question["operation"])
            self.assertIn("order", question["operation"])
            self.assertTrue(
                question["operation"].get("notation")
                or question["operation"].get("symbol")
            )
            self.assertIn("source_atom_index", question)
            self.assertIn("group", question)
            self.assertNotIn("target_atom_index", question)

    def test_published_operation_notation_matches_its_own_fold(self):
        # The mapping question puts the operation's name in the prompt, so the
        # name has to be the operation's, not its axis'.  Benzene's and BF3's
        # principal axis is labelled S6 but also carries S3 (= σh·C3); asking
        # "where does S6 send this atom?" about an S3 image is unanswerable.
        for name in ("benzene", "boron_trifluoride", "methane", "xenon_tetrafluoride"):
            improper = 0
            for question in public_questions(_render_data(name)):
                operation = question["operation"]
                if operation["kind"] not in ("rotoreflection", "rotoinversion"):
                    continue
                improper += 1
                expected = (
                    f"S{operation['order']}"
                    if operation["kind"] == "rotoreflection"
                    else f"-{operation['order']}"
                )
                with self.subTest(structure=name, operation=operation):
                    self.assertEqual(operation["notation"], expected)
                    self.assertEqual(operation["symbol"], expected)
            self.assertGreater(improper, 0, f"{name} published no improper operation")

    def test_benzene_publishes_s3_and_s6_as_separate_questions(self):
        # Both live on the same axis, so a label taken from the axis would merge
        # them into one indistinguishable prompt.
        notations = {
            question["operation"]["notation"]
            for question in public_questions(_render_data("benzene"))
        }
        self.assertIn("S3", notations)
        self.assertIn("S6", notations)

    def test_crystals_are_rejected_by_the_molecule_only_backend(self):
        # The UI picker currently offers molecules only, but the game layer must
        # enforce this scope because crystal images may be periodic copies that
        # are not represented by a unique displayed atom.
        render_data = _render_data("halite")
        self.assertIsNotNone(render_data.get("unit_cell"))
        self.assertEqual(mapping_questions(render_data), [])
        self.assertEqual(public_questions(render_data), [])
        self.assertIsNone(check_answer(render_data, 0, 0))

    def test_water_yields_questions(self):
        self.assertTrue(mapping_questions(_render_data("water")))

    def test_unknown_question_id(self):
        self.assertIsNone(check_answer(_render_data("water"), 999, 0))


if __name__ == "__main__":
    unittest.main()
