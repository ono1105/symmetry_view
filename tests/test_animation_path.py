import unittest
from unittest.mock import Mock

import numpy as np

from crystal_viewer.viewer.animation import apply_boundary_mode, update_animated_atoms
from crystal_viewer.viewer.animation_path import evaluate_path
from crystal_viewer.viewer.pyvista_controller import BrowserControlledViewer


class AnimationPathTest(unittest.TestCase):
    def test_start_marker_is_visible_only_while_playing(self):
        viewer = BrowserControlledViewer.__new__(BrowserControlledViewer)
        marker = Mock()
        viewer.animated_atoms = [
            {
                "atom": {"index": 0},
                "marker_actor": marker,
                "is_primary_image": True,
            }
        ]
        viewer.paths = {0: {"type": "linear"}}
        viewer.playing = False
        viewer.frame_position = 0.0

        viewer.update_start_markers()
        marker.SetVisibility.assert_called_with(False)

        viewer.playing = True
        viewer.update_start_markers()
        marker.SetVisibility.assert_called_with(True)

        viewer.playing = False
        viewer.frame_position = 20.0
        viewer.update_start_markers()
        marker.SetVisibility.assert_called_with(True)

        viewer.frame_position = 0.0
        viewer.update_start_markers()
        marker.SetVisibility.assert_called_with(False)

    def test_sequential_affine_path_applies_steps_in_order(self):
        c4 = np.array(
            [
                [0, -1, 0],
                [1, 0, 0],
                [0, 0, 1],
            ],
            dtype=float,
        )
        path = {
            "type": "sequential",
            "segments": [
                {
                    "type": "affine_linear",
                    "start": np.array([1.0, 0.0, 0.0]),
                    "target": np.array([1.25, 0.0, 0.0]),
                    "matrix_cart": np.eye(3),
                    "translation_cart": np.array([0.25, 0.0, 0.0]),
                },
                {
                    "type": "affine_linear",
                    "start": np.array([1.25, 0.0, 0.0]),
                    "target": np.array([0.0, 1.25, 0.0]),
                    "matrix_cart": c4,
                    "translation_cart": np.zeros(3),
                },
            ],
        }

        np.testing.assert_allclose(evaluate_path(path, 0.0), [1.0, 0.0, 0.0])
        np.testing.assert_allclose(evaluate_path(path, 0.5), [1.25, 0.0, 0.0])
        np.testing.assert_allclose(evaluate_path(path, 1.0), [0.0, 1.25, 0.0])

    def test_sequential_affine_path_transforms_display_copy_offsets(self):
        c4 = np.array(
            [
                [0, -1, 0],
                [1, 0, 0],
                [0, 0, 1],
            ],
            dtype=float,
        )
        path = {
            "type": "sequential",
            "segments": [
                {
                    "type": "affine_linear",
                    "start": np.array([1.0, 0.0, 0.0]),
                    "target": np.array([1.25, 0.0, 0.0]),
                    "matrix_cart": np.eye(3),
                    "translation_cart": np.array([0.25, 0.0, 0.0]),
                },
                {
                    "type": "affine_linear",
                    "start": np.array([1.25, 0.0, 0.0]),
                    "target": np.array([0.0, 1.25, 0.0]),
                    "matrix_cart": c4,
                    "translation_cart": np.zeros(3),
                },
            ],
        }

        start_override = np.array([2.0, 0.0, 0.0])

        np.testing.assert_allclose(evaluate_path(path, 0.5, start_override=start_override), [2.25, 0.0, 0.0])
        np.testing.assert_allclose(evaluate_path(path, 1.0, start_override=start_override), [0.0, 2.25, 0.0])

    def test_sequence_existing_rotation_uses_rotation_segment(self):
        viewer = sequence_test_viewer()

        paths = viewer.build_custom_sequence_animation_paths([0], [{"type": "operation", "index": 1}])
        path = paths[0]

        self.assertEqual(path["type"], "sequential")
        self.assertEqual(path["segments"][0]["type"], "rotation")
        np.testing.assert_allclose(evaluate_path(path, 1.0), [0.0, 1.0, 0.0], atol=1e-8)

    def test_sequence_custom_rotation_uses_rotation_segment(self):
        viewer = sequence_test_viewer()

        paths = viewer.build_custom_sequence_animation_paths(
            [0],
            [
                {
                    "type": "custom",
                    "label": "custom rotation",
                    "W_frac": [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
                    "t_frac": [0, 0, 0],
                    "op_type": "rotation",
                    "op_params": {"axis": [0, 0, 1], "angle": 90, "point": [0, 0, 0]},
                }
            ],
        )
        path = paths[0]

        self.assertEqual(path["segments"][0]["type"], "rotation")
        np.testing.assert_allclose(evaluate_path(path, 1.0), [0.0, 1.0, 0.0], atol=1e-8)

    def test_custom_matrix_animation_uses_linear_affine_segment(self):
        viewer = sequence_test_viewer()
        W = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)

        paths = viewer.build_custom_animation_paths(
            [0],
            W,
            np.zeros(3),
            op_type="matrix",
            op_params={},
        )

        self.assertEqual(paths[0]["type"], "affine_linear")
        np.testing.assert_allclose(evaluate_path(paths[0], 0.5), [0.5, 0.5, 0.0], atol=1e-8)
        np.testing.assert_allclose(evaluate_path(paths[0], 1.0), [0.0, 1.0, 0.0], atol=1e-8)

    def test_sequence_custom_matrix_uses_linear_affine_segment(self):
        viewer = sequence_test_viewer()

        paths = viewer.build_custom_sequence_animation_paths(
            [0],
            [
                {
                    "type": "custom",
                    "label": "matrix",
                    "W_frac": [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
                    "t_frac": [0, 0, 0],
                    "op_type": "matrix",
                    "op_params": {},
                }
            ],
        )

        self.assertEqual(paths[0]["segments"][0]["type"], "affine_linear")
        np.testing.assert_allclose(evaluate_path(paths[0], 0.5), [0.5, 0.5, 0.0], atol=1e-8)

    def test_sequence_speed_multiplier_slows_down_with_segment_count(self):
        viewer = sequence_test_viewer()
        paths = {
            0: {
                "type": "sequential",
                "segments": [
                    {"type": "linear"},
                    {"type": "rotation"},
                    {"type": "mirror"},
                ],
            }
        }

        self.assertAlmostEqual(viewer.custom_sequence_speed_multiplier(paths), 1.0 / 3.0)

    def test_apply_boundary_mode_wraps_to_centered_cell(self):
        render_data = {"unit_cell": {"lattice": np.eye(3).tolist()}}

        wrapped = apply_boundary_mode(np.array([0.75, -0.75, 0.1]), render_data, "wrap", "center")

        np.testing.assert_allclose(wrapped, [-0.25, 0.25, 0.1])

    def test_apply_boundary_mode_center_boundary_matches_display_cell(self):
        render_data = {"unit_cell": {"lattice": np.eye(3).tolist()}}

        wrapped = apply_boundary_mode(np.array([0.5, -0.5, 0.0]), render_data, "wrap", "center")

        np.testing.assert_allclose(wrapped, [-0.5, -0.5, 0.0])

    def test_apply_boundary_mode_wraps_to_corner_cell(self):
        render_data = {"unit_cell": {"lattice": np.eye(3).tolist()}}

        wrapped = apply_boundary_mode(np.array([1.25, -0.25, 0.1]), render_data, "wrap", "corner")

        np.testing.assert_allclose(wrapped, [0.25, 0.75, 0.1])

    def test_wrap_boundary_only_applies_to_atoms_with_active_paths(self):
        atom = {"index": 0, "cart": [1.25, 0.0, 0.0]}
        animated_atoms = [
            {
                "atom": atom,
                "display_shift_cart": np.zeros(3),
                "is_primary_image": False,
            }
        ]
        paths = {
            0: {
                "type": "linear",
                "start": np.array([1.25, 0.0, 0.0]),
                "target": np.array([1.75, 0.0, 0.0]),
                "unit_cell_only": True,
            }
        }

        update_animated_atoms(
            animated_atoms,
            paths,
            1.0,
            render_data={"unit_cell": {"lattice": np.eye(3).tolist()}},
            boundary_mode="wrap",
            cell_origin_mode="corner",
        )

        np.testing.assert_allclose(animated_atoms[0]["current_cart"], [1.25, 0.0, 0.0])


def sequence_test_viewer() -> BrowserControlledViewer:
    c4 = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
    viewer = BrowserControlledViewer.__new__(BrowserControlledViewer)
    viewer.render_data = {
        "metadata": {"mode": "crystal"},
        "unit_cell": {"lattice": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        "atoms": [{"index": 0, "atomic_number": 11, "element": "Na", "cart": [1, 0, 0], "frac": [1, 0, 0]}],
        "operations": [
            {"index": 0, "kind": "identity", "matrix_frac": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "translation_frac": [0, 0, 0], "matrix_cart": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "translation_cart": [0, 0, 0]},
            {"index": 1, "kind": "rotation_4", "angle_deg": 90, "matrix_frac": c4, "translation_frac": [0, 0, 0], "matrix_cart": c4, "translation_cart": [0, 0, 0]},
        ],
        "axes": [{"point_cart": [0, 0, 0], "direction_cart": [0, 0, 1], "operation_indices": [1]}],
        "planes": [],
        "centers": [],
    }
    viewer.operations = viewer.render_data["operations"]
    viewer.atom_mappings = None
    viewer.animated_atoms = [{"atom": viewer.render_data["atoms"][0], "display_shift_cart": np.zeros(3), "is_primary_image": True}]
    viewer.improper_mode = "auto"
    viewer.display_mode = "source"
    viewer.cell_origin_mode = "center"
    return viewer


if __name__ == "__main__":
    unittest.main()
