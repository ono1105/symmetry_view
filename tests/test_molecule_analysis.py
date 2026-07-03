import unittest
from pathlib import Path

import numpy as np

from crystal_viewer.atom_mapping import atom_mappings_from_molecule
from crystal_viewer.json_export import to_jsonable
from crystal_viewer.molecule_analysis import analyze_molecule_file
from crystal_viewer.render_data import render_data_from_molecule
from crystal_viewer.viewer.animation_context import animation_paths
from crystal_viewer.viewer.animation_path import evaluate_path


class MolecularMirrorAnimationTest(unittest.TestCase):
    def test_water_mirror_paths_end_at_affine_operation_targets(self):
        result = analyze_molecule_file(Path("examples/molecules/water.xyz"))
        render_data = to_jsonable(render_data_from_molecule(result))
        mappings = to_jsonable(atom_mappings_from_molecule(result))

        for operation in render_data["operations"]:
            if operation["kind"] != "mirror":
                continue
            with self.subTest(operation=operation["index"]):
                matrix = np.asarray(operation["matrix_cart"], dtype=float)
                np.testing.assert_allclose(matrix @ matrix, np.eye(3), atol=1e-10)
                np.testing.assert_allclose(matrix, matrix.T, atol=1e-10)
                mapping = next(
                    item for item in mappings["mappings"]
                    if item["operation_index"] == operation["index"]
                )
                paths = animation_paths(render_data, operation, mapping, animation_scope="all")
                for entry in mapping["entries"]:
                    endpoint = evaluate_path(paths[entry["source_atom"]], 1.0)
                    np.testing.assert_allclose(endpoint, entry["transformed_cart"], atol=1e-8)

    def test_linear_point_groups_use_standard_schoenflies_symbols(self):
        carbon_dioxide = analyze_molecule_file(Path("examples/molecules/carbon_dioxide.xyz"))
        hydrogen_chloride = analyze_molecule_file(Path("examples/molecules/hydrogen_chloride.xyz"))

        self.assertEqual(carbon_dioxide.point_group.symbol, "D∞h")
        self.assertEqual(hydrogen_chloride.point_group.symbol, "C∞v")


if __name__ == "__main__":
    unittest.main()
