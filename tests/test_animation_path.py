import unittest
from unittest.mock import Mock

import numpy as np

from crystal_viewer.viewer.animation import apply_boundary_mode, update_animated_atoms
from crystal_viewer.viewer.custom_animation import build_custom_animation_paths
from crystal_viewer.viewer.animation_path import (
    animation_path_length,
    evaluate_path,
    normalized_animation_duration_seconds,
    synchronize_compound_path_phases,
)
from crystal_viewer.viewer.pyvista_controller import BrowserControlledViewer


class AnimationPathTest(unittest.TestCase):
    def test_shared_custom_path_builder_supports_operation_and_sequence(self):
        viewer = sequence_test_viewer()
        rotation_request = {
            "atom_indices": [0],
            "W_frac": [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
            "t_frac": [0, 0, 0],
            "op_type": "rotation",
            "op_params": {"axis": [0, 0, 1], "angle": 90, "point": [0, 0, 0]},
        }
        sequence_request = {
            "atom_indices": [0],
            "sequence_items": [{"type": "operation", "index": 1}],
        }

        rotation = build_custom_animation_paths(viewer.render_data, None, rotation_request)
        sequence = build_custom_animation_paths(viewer.render_data, None, sequence_request)

        self.assertEqual(rotation[0]["type"], "rotation")
        self.assertEqual(sequence[0]["type"], "sequential")
        np.testing.assert_allclose(evaluate_path(rotation[0], 1.0), [0, 1, 0], atol=1e-8)
        np.testing.assert_allclose(evaluate_path(sequence[0], 1.0), [0, 1, 0], atol=1e-8)

    def test_custom_glide_sequence_exposes_translation_arrow(self):
        viewer = sequence_test_viewer()
        request = {
            "atom_indices": [0],
            "sequence_items": [{
                "type": "custom",
                "label": "custom glide",
                "W_frac": [[1, 0, 0], [0, 1, 0], [0, 0, -1]],
                "t_frac": [0.5, 0, 0],
                "op_type": "glide",
                "op_params": {"normal": [0, 0, 1], "point": [0, 0, 0], "glide": [0.5, 0, 0]},
            }],
        }

        path = build_custom_animation_paths(viewer.render_data, None, request)[0]

        np.testing.assert_allclose(path["segment_elements"][0]["glide_translation_cart"], [0.5, 0, 0])

    def test_normalized_duration_is_invariant_to_structure_scale(self):
        small = normalized_animation_duration_seconds(2.0, 4.0)
        large = normalized_animation_duration_seconds(20.0, 40.0)

        self.assertAlmostEqual(small, large)

    def test_normalized_duration_has_stationary_and_safety_limits(self):
        self.assertAlmostEqual(normalized_animation_duration_seconds(0.0, 4.0), 0.4)
        self.assertAlmostEqual(normalized_animation_duration_seconds(0.001, 100.0), 1.0)
        self.assertAlmostEqual(normalized_animation_duration_seconds(100.0, 1.0), 16.0 / 3.0)

    def test_compound_paths_share_phase_boundary_across_different_radii(self):
        paths = {
            0: {
                "type": "screw",
                "start": np.array([1.0, 0.0, 0.0]),
                "target": np.array([0.0, 1.0, 2.0]),
                "axis_point": np.zeros(3),
                "axis_direction": np.array([0.0, 0.0, 1.0]),
                "angle": np.pi / 2,
                "translation": np.array([0.0, 0.0, 2.0]),
            },
            1: {
                "type": "screw",
                "start": np.array([3.0, 0.0, 0.0]),
                "target": np.array([0.0, 3.0, 2.0]),
                "axis_point": np.zeros(3),
                "axis_direction": np.array([0.0, 0.0, 1.0]),
                "angle": np.pi / 2,
                "translation": np.array([0.0, 0.0, 2.0]),
            },
        }

        synchronize_compound_path_phases(paths)

        split = paths[0]["phase_fraction"]
        self.assertEqual(split, paths[1]["phase_fraction"])
        self.assertAlmostEqual(split, (3 * np.pi / 2) / (3 * np.pi / 2 + 2))
        np.testing.assert_allclose(evaluate_path(paths[0], split), [0.0, 1.0, 0.0], atol=1e-8)
        np.testing.assert_allclose(evaluate_path(paths[1], split), [0.0, 3.0, 0.0], atol=1e-8)

    def test_sequence_steps_share_boundaries_when_one_atom_is_stationary(self):
        def sequence(start):
            rotated = np.array([-start[1], start[0], start[2]], dtype=float)
            return {
                "type": "sequential",
                "segments": [
                    {
                        "type": "rotation",
                        "start": np.asarray(start, dtype=float),
                        "target": rotated,
                        "axis_point": np.zeros(3),
                        "axis_direction": np.array([0.0, 0.0, 1.0]),
                        "angle": np.pi / 2,
                    },
                    {
                        "type": "affine_linear",
                        "start": rotated,
                        "target": rotated + np.array([0.0, 0.0, 1.0]),
                        "matrix_cart": np.eye(3),
                        "translation_cart": np.array([0.0, 0.0, 1.0]),
                    },
                ],
            }

        paths = {0: sequence([0.0, 0.0, 0.0]), 1: sequence([2.0, 0.0, 0.0])}
        synchronize_compound_path_phases(paths)

        split = paths[0]["segment_weights"][0]
        self.assertEqual(paths[0]["segment_weights"], paths[1]["segment_weights"])
        np.testing.assert_allclose(evaluate_path(paths[0], split), [0.0, 0.0, 0.0], atol=1e-8)
        np.testing.assert_allclose(evaluate_path(paths[1], split), [0.0, 2.0, 0.0], atol=1e-8)

    def test_pyvista_sequence_elements_follow_segment_weights(self):
        viewer = BrowserControlledViewer.__new__(BrowserControlledViewer)
        viewer.paths = {
            0: {
                "type": "sequential",
                "segments": [{}, {}],
                "segment_weights": [0.8, 0.2],
                "segment_elements": [{"label": "first"}, {"label": "second"}],
            },
        }

        self.assertEqual(viewer.current_sequence_segment_elements(0.79), (0, {"label": "first"}))
        self.assertEqual(viewer.current_sequence_segment_elements(0.81), (1, {"label": "second"}))

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
        split = animation_path_length(path["segments"][0]) / animation_path_length(path)
        np.testing.assert_allclose(evaluate_path(path, split), [1.25, 0.0, 0.0])
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

        first_length = animation_path_length(path["segments"][0], start_override=start_override)
        split = first_length / animation_path_length(path, start_override=start_override)
        np.testing.assert_allclose(evaluate_path(path, split, start_override=start_override), [2.25, 0.0, 0.0])
        np.testing.assert_allclose(evaluate_path(path, 1.0, start_override=start_override), [0.0, 2.25, 0.0])

    def test_sequence_existing_rotation_uses_rotation_segment(self):
        viewer = sequence_test_viewer()

        paths = build_custom_animation_paths(
            viewer.render_data, viewer.atom_mappings,
            {"atom_indices": [0], "sequence_items": [{"type": "operation", "index": 1}]},
        )
        path = paths[0]

        self.assertEqual(path["type"], "sequential")
        self.assertEqual(path["segments"][0]["type"], "rotation")
        np.testing.assert_allclose(evaluate_path(path, 1.0), [0.0, 1.0, 0.0], atol=1e-8)

    def test_sequence_custom_rotation_uses_rotation_segment(self):
        viewer = sequence_test_viewer()

        paths = build_custom_animation_paths(
            viewer.render_data, viewer.atom_mappings,
            {"atom_indices": [0], "sequence_items": [
                {
                    "type": "custom",
                    "label": "custom rotation",
                    "W_frac": [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
                    "t_frac": [0, 0, 0],
                    "op_type": "rotation",
                    "op_params": {"axis": [0, 0, 1], "angle": 90, "point": [0, 0, 0]},
                }
            ]},
        )
        path = paths[0]

        self.assertEqual(path["segments"][0]["type"], "rotation")
        np.testing.assert_allclose(evaluate_path(path, 1.0), [0.0, 1.0, 0.0], atol=1e-8)

    def test_custom_matrix_animation_uses_linear_affine_segment(self):
        viewer = sequence_test_viewer()
        W = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)

        paths = build_custom_animation_paths(
            viewer.render_data, viewer.atom_mappings,
            {"atom_indices": [0], "W_frac": W, "t_frac": np.zeros(3),
             "op_type": "matrix", "op_params": {}},
        )

        self.assertEqual(paths[0]["type"], "affine_linear")
        np.testing.assert_allclose(evaluate_path(paths[0], 0.5), [0.5, 0.5, 0.0], atol=1e-8)
        np.testing.assert_allclose(evaluate_path(paths[0], 1.0), [0.0, 1.0, 0.0], atol=1e-8)

    def test_sequence_custom_matrix_uses_linear_affine_segment(self):
        viewer = sequence_test_viewer()

        paths = build_custom_animation_paths(
            viewer.render_data, viewer.atom_mappings,
            {"atom_indices": [0], "sequence_items": [
                {
                    "type": "custom",
                    "label": "matrix",
                    "W_frac": [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
                    "t_frac": [0, 0, 0],
                    "op_type": "matrix",
                    "op_params": {},
                }
            ]},
        )

        self.assertEqual(paths[0]["segments"][0]["type"], "affine_linear")
        np.testing.assert_allclose(evaluate_path(paths[0], 0.5), [0.5, 0.5, 0.0], atol=1e-8)

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
