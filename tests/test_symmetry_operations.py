import unittest

import numpy as np

from crystal_viewer.analysis_models import SymmetryOperationInfo
from crystal_viewer.symmetry_operations import (
    compose_affine_operations,
    compose_operation_sequence,
    find_matching_operation_index,
    find_operation_sequence_bfs,
    normalize_translation,
    operations_equivalent,
)


class SymmetryOperationsTest(unittest.TestCase):
    def test_compose_applies_first_then_second(self):
        c4 = np.array(
            [
                [0, -1, 0],
                [1, 0, 0],
                [0, 0, 1],
            ]
        )
        translation = np.eye(3), np.array([0.25, 0.0, 0.0])

        result = compose_affine_operations((c4, np.zeros(3)), translation)

        np.testing.assert_array_equal(result.W, c4)
        np.testing.assert_allclose(result.t, [0.25, 0.0, 0.0])

    def test_compose_rotates_first_translation_by_second_operation(self):
        c4 = np.array(
            [
                [0, -1, 0],
                [1, 0, 0],
                [0, 0, 1],
            ]
        )
        translation = np.eye(3), np.array([0.25, 0.0, 0.0])

        result = compose_affine_operations(translation, (c4, np.zeros(3)))

        np.testing.assert_array_equal(result.W, c4)
        np.testing.assert_allclose(result.t, [0.0, 0.25, 0.0])

    def test_compose_normalizes_translation_modulo_one(self):
        first = np.eye(3), np.array([0.75, -0.25, 0.0])
        second = np.eye(3), np.array([0.5, 0.5, 1.0])

        result = compose_affine_operations(first, second)

        np.testing.assert_allclose(result.t, [0.25, 0.25, 0.0])

    def test_compose_operation_sequence_uses_application_order(self):
        c4 = np.array(
            [
                [0, -1, 0],
                [1, 0, 0],
                [0, 0, 1],
            ]
        )
        sequence = [
            (np.eye(3), np.array([0.25, 0.0, 0.0])),
            (c4, np.zeros(3)),
            (np.eye(3), np.array([0.0, 0.0, 0.5])),
        ]

        result = compose_operation_sequence(sequence)

        np.testing.assert_array_equal(result.W, c4)
        np.testing.assert_allclose(result.t, [0.0, 0.25, 0.5])

    def test_operations_equivalent_compares_translation_modulo_lattice(self):
        left = np.eye(3), np.array([1.25, -0.5, 0.0])
        right = np.eye(3), np.array([0.25, 0.5, 1.0])

        self.assertTrue(operations_equivalent(left, right))

    def test_find_matching_operation_index_accepts_exported_dicts(self):
        operations = [
            {"index": 0, "matrix_frac": np.eye(3).tolist(), "translation_frac": [0.0, 0.0, 0.0]},
            {"index": 7, "matrix_frac": np.eye(3).tolist(), "translation_frac": [0.25, 0.5, 0.0]},
        ]

        index = find_matching_operation_index(np.eye(3), np.array([1.25, -0.5, 0.0]), operations)

        self.assertEqual(index, 7)

    def test_find_matching_operation_index_accepts_analysis_model_operations(self):
        operation = SymmetryOperationInfo(
            index=3,
            W=np.eye(3, dtype=int),
            t=np.array([0.0, 0.0, 0.5]),
            kind="pure_translation_or_centering_translation",
            order=1,
            det=1,
            trace=3,
            angle_deg=0.0,
            international_symbol="translation",
        )

        index = find_matching_operation_index(np.eye(3), np.array([0.0, 0.0, -0.5]), [operation])

        self.assertEqual(index, 3)

    def test_normalize_translation_snaps_values_near_integer_boundaries(self):
        normalized = normalize_translation(np.array([1.0 + 1e-10, -1e-10, 0.5]))

        np.testing.assert_allclose(normalized, [0.0, 0.0, 0.5])

    def test_find_operation_sequence_bfs_finds_short_generator_path(self):
        c4 = np.array(
            [
                [0, -1, 0],
                [1, 0, 0],
                [0, 0, 1],
            ]
        )
        c2 = c4 @ c4
        operations = [
            {"index": 0, "matrix_frac": np.eye(3), "translation_frac": [0, 0, 0]},
            {"index": 1, "matrix_frac": c4, "translation_frac": [0, 0, 0]},
            {"index": 2, "matrix_frac": c2, "translation_frac": [0, 0, 0]},
            {"index": 3, "matrix_frac": c4 @ c2, "translation_frac": [0, 0, 0]},
        ]

        sequence = find_operation_sequence_bfs(
            operations[2],
            [operations[1]],
            operations,
            max_depth=3,
        )

        self.assertEqual(sequence, (1, 1))

    def test_find_operation_sequence_bfs_respects_max_depth(self):
        c4 = np.array(
            [
                [0, -1, 0],
                [1, 0, 0],
                [0, 0, 1],
            ]
        )
        operations = [
            {"index": 0, "matrix_frac": np.eye(3), "translation_frac": [0, 0, 0]},
            {"index": 1, "matrix_frac": c4, "translation_frac": [0, 0, 0]},
            {"index": 2, "matrix_frac": c4 @ c4, "translation_frac": [0, 0, 0]},
        ]

        sequence = find_operation_sequence_bfs(
            operations[2],
            [operations[1]],
            operations,
            max_depth=1,
        )

        self.assertIsNone(sequence)


if __name__ == "__main__":
    unittest.main()
