import json
import unittest
from pathlib import Path

from crystal_viewer.viewer.cell_settings import standardized_payload
from crystal_viewer.viewer.operation_labels import operation_notation_order, operation_summaries
import numpy as np

from crystal_viewer.viewer.animation_context import select_animation_context, shared_step_translation
from crystal_viewer.viewer.operation_lookup import selected_mapping
from crystal_viewer.viewer.symmetry_elements import display_symmetry_elements, glide_translation_cart


class OperationLabelsTest(unittest.TestCase):
    def test_rotoinversion_notation_order_comes_from_symbol(self):
        operation = {
            "kind": "rotoinversion_or_improper_6",
            "order": 6,
            "angle_deg": None,
            "symbol": "-3",
        }

        self.assertEqual(operation_notation_order(operation), 3)

    def test_halite_rotoinversion_summary_separates_notation_and_matrix_orders(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))

        summaries = operation_summaries(payload["render_data"], payload["atom_mappings"])
        bar_three = next(item for item in summaries if item["symbol"] == "-3")

        self.assertEqual(bar_three["order"], 6)
        self.assertEqual(bar_three["notation_order"], 3)

    def test_cadmoselite_glides_are_labeled_as_c_glides(self):
        payload = json.loads(Path("exports/json/cadmoselite.json").read_text(encoding="utf-8"))

        glide_symbols = glide_display_symbols(payload)

        self.assertEqual(glide_symbols, {"c"})

    def test_halite_glides_include_n_glides(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))

        glide_symbols = glide_display_symbols(payload)

        self.assertIn("n", glide_symbols)

    def test_batio3_r_lattice_glides_remain_generic_glides(self):
        payload = json.loads(Path("exports/json/batio3.json").read_text(encoding="utf-8"))
        converted = standardized_payload(payload, "conventional", require_distinct=True)

        self.assertIsNotNone(converted)
        assert converted is not None
        glide_symbols = glide_display_symbols(converted)

        self.assertEqual(glide_symbols, {"g"})

    def test_generic_batio3_glides_show_glide_vector_in_standard_summary(self):
        payload = json.loads(Path("exports/json/batio3.json").read_text(encoding="utf-8"))
        converted = standardized_payload(payload, "conventional", require_distinct=True)

        self.assertIsNotNone(converted)
        assert converted is not None
        summaries = operation_summaries(converted["render_data"], converted["atom_mappings"])
        glide = next(summary for summary in summaries if summary["display_symbol"] == "g")

        self.assertIn("glide", glide["element_summary"])
        self.assertIn("1/3", glide["element_summary"])

    def test_batio3_itc_like_summary_has_readable_plane_and_glide_vector(self):
        payload = json.loads(Path("exports/json/batio3.json").read_text(encoding="utf-8"))
        converted = standardized_payload(payload, "conventional", require_distinct=True)

        self.assertIsNotNone(converted)
        assert converted is not None
        summaries = operation_summaries(converted["render_data"], converted["atom_mappings"])
        glide = next(summary for summary in summaries if summary["index"] == 9)

        self.assertEqual(glide["itc_like_summary"], "g(1/6,-1/6,1/3) x+1/2, -x, z")

    def test_glide_direction_vector_uses_centered_periodic_image(self):
        payload = json.loads(Path("exports/json/cadmoselite.json").read_text(encoding="utf-8"))
        render_data = payload["render_data"]
        operation = next(operation for operation in render_data["operations"] if "glide" in operation["kind"])
        _, planes, _ = display_symmetry_elements(render_data, payload["atom_mappings"], operation["index"], None)

        vector = glide_translation_cart(render_data, operation, planes[0])

        self.assertIsNotNone(vector)
        assert vector is not None
        self.assertAlmostEqual(float(vector[0]), 0.0, places=8)
        self.assertAlmostEqual(float(vector[1]), 0.0, places=8)
        self.assertGreater(float(vector[2]), 0.0)

    def test_glide_direction_line_matches_animation_translation_direction(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        render_data = payload["render_data"]
        atom_mappings = payload["atom_mappings"]
        operation = render_data["operations"][75]
        mapping = selected_mapping(atom_mappings, operation["index"])
        atoms_by_index = {atom["index"]: atom for atom in render_data["atoms"]}
        _, planes, _ = display_symmetry_elements(render_data, atom_mappings, operation["index"], None)

        vector = glide_translation_cart(render_data, operation, planes[0], mapping=mapping)
        axis, plane, center, reference_entry, shared_shift, shared_angle = select_animation_context(
            render_data,
            operation,
            mapping,
            atoms_by_index,
            element_index=None,
            representative_atom=None,
        )
        translation = shared_step_translation(
            render_data,
            operation,
            atoms_by_index,
            reference_entry,
            axis,
            plane,
            shared_shift,
            shared_angle,
        )

        self.assertIsNotNone(vector)
        self.assertIsNotNone(translation)
        assert vector is not None and translation is not None
        cosine = float(np.dot(vector, translation) / (np.linalg.norm(vector) * np.linalg.norm(translation)))
        self.assertAlmostEqual(cosine, 1.0, places=8)


def glide_display_symbols(payload: dict) -> set[str]:
    return {
        summary["display_symbol"]
        for summary in operation_summaries(payload["render_data"], payload["atom_mappings"])
        if "glide" in str(summary["kind"])
    }


if __name__ == "__main__":
    unittest.main()
