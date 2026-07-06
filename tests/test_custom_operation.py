import json
import unittest
from pathlib import Path

import numpy as np

from crystal_viewer.viewer.custom_operation import check_custom_operation


class ExistingOperationCustomCheckTest(unittest.TestCase):
    def test_all_halite_operations_pass_when_loaded_as_custom_matrices(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        render_data = payload["render_data"]

        for operation in render_data["operations"]:
            with self.subTest(operation=operation["index"]):
                result = check_custom_operation(
                    render_data,
                    np.asarray(operation["matrix_frac"], dtype=float),
                    np.asarray(operation["translation_frac"], dtype=float),
                    tolerance_cart=0.1,
                )
                self.assertTrue(result["is_symmetry"], result)

    def test_check_result_includes_coordinates_for_matched_and_unmatched_atoms(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        render_data = payload["render_data"]
        identity = np.eye(3)

        matched = check_custom_operation(render_data, identity, np.zeros(3), tolerance_cart=0.1)
        unmatched = check_custom_operation(render_data, identity, np.array([0.123, 0.0, 0.0]), tolerance_cart=0.1)

        self.assertTrue(matched["mapped"])
        self.assertIn("source_frac", matched["mapped"][0])
        self.assertIn("transformed_frac", matched["mapped"][0])
        self.assertIn("target_frac", matched["mapped"][0])
        self.assertFalse(unmatched["is_symmetry"])
        self.assertIn("source_frac", unmatched["unmapped"][0])
        self.assertIn("transformed_frac", unmatched["unmapped"][0])
        self.assertIn("nearest_frac", unmatched["unmapped"][0])

    def test_scaling_matrix_is_reported_as_non_symmetry_but_remains_animatable(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        result = check_custom_operation(
            payload["render_data"],
            np.diag([1.2, 1.0, 1.0]),
            np.zeros(3),
            tolerance_cart=0.1,
        )

        self.assertNotIn("error", result)
        self.assertFalse(result["is_symmetry"])
        self.assertIn("does not preserve", result["matrix_issue"])


if __name__ == "__main__":
    unittest.main()
