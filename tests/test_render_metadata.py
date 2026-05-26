from __future__ import annotations

import unittest

import numpy as np

from crystal_viewer.render_data import (
    RenderOperationData,
    lattice_parameters_from_matrix,
    normalize_generator_symbol,
    operation_generators,
)


class RenderMetadataTest(unittest.TestCase):
    def test_lattice_parameters_from_matrix(self) -> None:
        params = lattice_parameters_from_matrix(np.diag([3.0, 4.0, 5.0]))

        self.assertEqual(params["a"], 3.0)
        self.assertEqual(params["b"], 4.0)
        self.assertEqual(params["c"], 5.0)
        self.assertAlmostEqual(params["alpha"], 90.0)
        self.assertAlmostEqual(params["beta"], 90.0)
        self.assertAlmostEqual(params["gamma"], 90.0)

    def test_generator_labels_do_not_expose_unknown_screw_symbol(self) -> None:
        operations = (
            op(0, np.eye(3), [0.0, 0.0, 0.0], "1", "identity", 1),
            op(1, c4(), [0.0, 0.0, 0.25], "4_?", "screw_4", 4),
            op(2, c4() @ c4(), [0.0, 0.0, 0.5], "2_1", "screw_2", 2),
            op(3, c4() @ c4() @ c4(), [0.0, 0.0, 0.75], "4_?", "screw_4", 4),
        )

        generators = operation_generators(operations, mode="space")

        self.assertEqual(generators, ("4_1",))
        self.assertFalse(any("?" in item for item in generators))

    def test_point_group_generator_labels_are_compact(self) -> None:
        operations = (
            op(0, np.eye(3), [0.0, 0.0, 0.0], "1", "identity", 1),
            op(1, c4(), [0.0, 0.0, 0.25], "4_?", "screw_4", 4),
            op(2, mirror_xy(), [0.0, 0.0, 0.0], "sigma", "mirror", 2),
        )

        generators = operation_generators(operations, mode="point")

        self.assertEqual(generators, ("C4", "σ"))

    def test_space_group_translation_generator_shows_vector(self) -> None:
        operations = (
            op(0, np.eye(3), [0.0, 0.0, 0.0], "1", "identity", 1),
            op(1, np.eye(3), [0.5, 0.5, 0.0], "translation", "pure_translation_or_centering_translation", 1),
        )

        generators = operation_generators(operations, mode="space")

        self.assertEqual(generators, ("t(1/2,1/2,0)",))

    def test_rotoinversion_generator_symbol_matches_compact_order(self) -> None:
        self.assertEqual(normalize_generator_symbol("-3"), "S6")
        self.assertEqual(normalize_generator_symbol("-4"), "S4")


def op(
    index: int,
    matrix: np.ndarray,
    translation: list[float],
    symbol: str,
    kind: str,
    order: int,
) -> RenderOperationData:
    return RenderOperationData(
        index=index,
        label=f"{index}: {symbol} {kind}",
        kind=kind,
        order=order,
        angle_deg=None,
        symbol=symbol,
        matrix_frac=np.asarray(matrix, dtype=float),
        translation_frac=np.asarray(translation, dtype=float),
    )


def c4() -> np.ndarray:
    return np.asarray(
        [
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 1],
        ],
        dtype=float,
    )


def mirror_xy() -> np.ndarray:
    return np.asarray(
        [
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, -1],
        ],
        dtype=float,
    )


if __name__ == "__main__":
    unittest.main()
