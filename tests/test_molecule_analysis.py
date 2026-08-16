from collections import Counter
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


class IcosahedralClusterTest(unittest.TestCase):
    """Five-fold symmetry is read correctly, checked outside the generator.

    A finite cluster may have the 5-fold axes a periodic lattice cannot, and the
    molecule path takes the fold from the matrix period rather than assuming the
    crystallographic restriction. That is what lets the viewer show the building
    block of an icosahedral quasicrystal at all — the crystal path could not,
    since it needs a lattice.
    """

    def test_cluster_analyses_as_ih_with_five_fold_axes(self):
        result = analyze_molecule_file(Path("examples/molecules/al12w_icosahedron.xyz"))

        self.assertEqual(result.point_group.symbol, "Ih")
        self.assertEqual(len(result.operations), 120)
        kinds = Counter(operation.kind for operation in result.operations)
        self.assertEqual(kinds["rotation_5"], 24)  # 6 axes, C5 C5^2 C5^3 C5^4 each
        self.assertEqual(kinds["improper_10"], 24)
        self.assertEqual(kinds["rotation_3"], 20)
        self.assertEqual(kinds["inversion"], 1)

    def test_five_fold_operations_carry_order_five(self):
        result = analyze_molecule_file(Path("examples/molecules/al12w_icosahedron.xyz"))

        orders = {op.order for op in result.operations if op.kind == "rotation_5"}
        self.assertEqual(orders, {5})


if __name__ == "__main__":
    unittest.main()
