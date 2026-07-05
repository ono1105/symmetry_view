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


if __name__ == "__main__":
    unittest.main()
