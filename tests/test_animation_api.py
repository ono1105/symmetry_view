import json
import unittest
from pathlib import Path

import numpy as np

from crystal_viewer.viewer.animation_api import (
    ANIMATION_PATH_SCHEMA_VERSION,
    animation_boundary_context,
    animation_path_response,
    custom_animation_path_response,
    serialize_animation_path,
    symmetry_elements_response,
)
from crystal_viewer.viewer.animation import apply_boundary_context
from tests.support import load_export
from crystal_viewer.viewer.animation_path import animation_path_length, evaluate_path


class SerializeAnimationPathTest(unittest.TestCase):
    def test_animation_path_length_uses_cartesian_travel_distance(self):
        path = {
            "type": "translation",
            "start": np.array([0.0, 0.0, 0.0]),
            "target": np.array([3.0, 4.0, 0.0]),
        }
        self.assertAlmostEqual(animation_path_length(path), 5.0)

    def test_animation_path_length_uses_exact_rotation_arc(self):
        path = {
            "type": "rotation",
            "start": np.array([2.0, 0.0, 0.0]),
            "target": np.array([0.0, 2.0, 0.0]),
            "axis_point": np.zeros(3),
            "axis_direction": np.array([0.0, 0.0, 1.0]),
            "angle": np.pi / 2,
        }
        self.assertAlmostEqual(animation_path_length(path), np.pi)

    def test_compound_path_allocates_time_by_phase_length(self):
        path = {
            "type": "screw",
            "start": np.array([1.0, 0.0, 0.0]),
            "target": np.array([0.0, 1.0, 2.0]),
            "axis_point": np.zeros(3),
            "axis_direction": np.array([0.0, 0.0, 1.0]),
            "angle": np.pi / 2,
            "translation": np.array([0.0, 0.0, 2.0]),
        }
        split = (np.pi / 2) / (np.pi / 2 + 2.0)
        np.testing.assert_allclose(evaluate_path(path, split), [0.0, 1.0, 0.0], atol=1e-8)

    def test_converts_numpy_values_and_radians_recursively(self):
        path = {
            "type": "sequential",
            "segments": [
                {
                    "type": "rotation",
                    "start": np.array([1.0, 0.0, 0.0]),
                    "target": np.array([0.0, 1.0, 0.0]),
                    "axis_point": np.zeros(3),
                    "axis_direction": np.array([0.0, 0.0, 1.0]),
                    "angle": np.pi / 2.0,
                }
            ],
        }

        result = serialize_animation_path(path)

        segment = result["segments"][0]
        self.assertNotIn("angle", segment)
        self.assertAlmostEqual(segment["angle_deg"], 90.0)
        self.assertEqual(segment["start"], [1.0, 0.0, 0.0])
        self.assertEqual(segment["axis_direction"], [0.0, 0.0, 1.0])


class AnimationPathResponseTest(unittest.TestCase):
    def test_non_symmetry_custom_transform_can_still_be_animated(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        response = custom_animation_path_response(
            payload["render_data"],
            payload["atom_mappings"],
            {
                "atom_indices": [2],
                "animate_id": 99,
                "W_frac": np.diag([1.2, 1.0, 1.0]).tolist(),
                "t_frac": [0.0, 0.0, 0.0],
                "op_type": "matrix",
                "op_params": {},
            },
        )

        self.assertEqual(response["animate_id"], 99)
        self.assertEqual(len(response["paths"]), 1)
        self.assertEqual(response["paths"][0]["path"]["type"], "affine_linear")
        self.assertGreater(response["maximum_travel_distance"], 0.0)

    def test_custom_rotation_and_sequence_publish_cartesian_paths(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        common = {
            "atom_indices": [0, 1],
            "unit_cell_only": False,
        }
        rotation = custom_animation_path_response(
            payload["render_data"],
            payload["atom_mappings"],
            {
                **common,
                "animate_id": 101,
                "W_frac": [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
                "t_frac": [0, 0, 0],
                "op_type": "rotation",
                "op_params": {"axis": [0, 0, 1], "angle": 90, "point": [0, 0, 0]},
            },
        )
        sequence = custom_animation_path_response(
            payload["render_data"],
            payload["atom_mappings"],
            {**common, "animate_id": 102, "sequence_items": [
                {"type": "operation", "index": 1},
                {"type": "operation", "index": 1},
            ]},
        )

        self.assertEqual(rotation["animate_id"], 101)
        self.assertEqual(len(rotation["paths"]), 2)
        self.assertEqual(rotation["paths"][0]["path"]["type"], "rotation")
        self.assertIn("angle_deg", rotation["paths"][0]["path"])
        self.assertEqual(sequence["animate_id"], 102)
        self.assertEqual(len(sequence["paths"][0]["path"]["segments"]), 2)
        self.assertGreater(sequence["animation_duration_seconds"], 0)

    def test_sio2_screw_paths_publish_one_shared_phase_boundary(self):
        payload = load_export("sio2")

        result = animation_path_response(
            payload["render_data"],
            payload["atom_mappings"],
            6,
            scope="displayed",
        )

        fractions = {round(item["path"]["phase_fraction"], 12) for item in result["paths"]}
        self.assertEqual(len(fractions), 1)

    def test_builds_versioned_cartesian_response(self):
        render_data = {
            "metadata": {"mode": "molecule"},
            "atoms": [
                {"index": 0, "cart": [1.0, 0.0, 0.0]},
                {"index": 1, "cart": [0.0, 1.0, 0.0]},
            ],
            "operations": [
                {
                    "index": 3,
                    "kind": "rotation_4",
                    "order": 4,
                    "angle_deg": 90.0,
                    "matrix_cart": [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
                    "translation_cart": [0.0, 0.0, 0.0],
                }
            ],
            "axes": [
                {
                    "point_cart": [0.0, 0.0, 0.0],
                    "direction_cart": [0.0, 0.0, 1.0],
                    "operation_indices": [3],
                }
            ],
            "planes": [],
            "centers": [],
            "unit_cell": None,
        }
        mappings = {
            "mappings": [
                {
                    "operation_index": 3,
                    "entries": [
                        {
                            "source_atom": 0,
                            "target_atom": 1,
                            "transformed_cart": [0.0, 1.0, 0.0],
                        }
                    ],
                }
            ]
        }

        result = animation_path_response(render_data, mappings, 3, scope="displayed")

        self.assertEqual(result["schema_version"], ANIMATION_PATH_SCHEMA_VERSION)
        self.assertEqual(result["source_kind"], "molecule")
        self.assertEqual(result["coordinate_space"], "cartesian")
        self.assertEqual(result["periodic_image_policy"], "not_applicable")
        self.assertEqual(result["operation_index"], 3)
        self.assertGreater(result["maximum_travel_distance"], 0.0)
        self.assertGreaterEqual(result["animation_duration_seconds"], 1.0)
        self.assertEqual(result["boundary"], {"mode": "continuous"})
        self.assertEqual(result["paths"][0]["source_atom"], 0)
        self.assertEqual(result["paths"][0]["target_atom"], 1)
        self.assertAlmostEqual(result["paths"][0]["path"]["angle_deg"], 90.0)
        self.assertNotIn("angle", result["paths"][0]["path"])

    def test_crystal_periodic_images_transform_with_source(self):
        render_data = {
            "metadata": {"mode": "crystal"},
            "atoms": [{"index": 0, "cart": [0.0, 0.0, 0.0]}],
            "operations": [
                {
                    "index": 0,
                    "kind": "identity",
                    "matrix_cart": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                    "translation_cart": [0.0, 0.0, 0.0],
                }
            ],
            "axes": [],
            "planes": [],
            "centers": [],
            "unit_cell": {"lattice": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]},
        }
        mappings = {
            "mappings": [
                {
                    "operation_index": 0,
                    "entries": [
                        {
                            "source_atom": 0,
                            "target_atom": 0,
                            "transformed_frac": [0.0, 0.0, 0.0],
                            "transformed_cart": [0.0, 0.0, 0.0],
                        }
                    ],
                }
            ]
        }

        result = animation_path_response(render_data, mappings, 0)

        self.assertEqual(result["source_kind"], "crystal")
        self.assertEqual(result["periodic_image_policy"], "transform_with_source")

    def test_wrap_context_is_cartesian_and_python_generated(self):
        render_data = {
            "unit_cell": {"lattice": [[2.0, 0.0, 0.0], [1.0, 2.0, 0.0], [0.0, 0.0, 3.0]]}
        }

        result = animation_boundary_context(
            render_data,
            animation_boundary_mode="wrap",
            cell_origin_mode="corner",
        )

        self.assertEqual(result["mode"], "wrap")
        self.assertEqual(result["coordinate_space"], "cartesian")
        self.assertEqual(result["cell_origin_mode"], "corner")
        np.testing.assert_allclose(
            np.asarray(result["cart_to_cell"]) @ np.asarray(result["cell_to_cart"]),
            np.eye(3),
            atol=1e-12,
        )

    def test_molecule_cannot_enable_periodic_wrap(self):
        self.assertEqual(
            animation_boundary_context(
                {"unit_cell": None},
                animation_boundary_mode="wrap",
                cell_origin_mode="center",
            ),
            {"mode": "continuous"},
        )

    def test_displayed_and_unit_cell_scopes_encode_periodic_copy_policy(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        displayed = animation_path_response(
            payload["render_data"], payload["atom_mappings"], 2, scope="displayed"
        )
        unit_cell = animation_path_response(
            payload["render_data"], payload["atom_mappings"], 2, scope="unit_cell"
        )

        self.assertTrue(displayed["paths"])
        self.assertTrue(unit_cell["paths"])
        self.assertTrue(all(not item["path"].get("unit_cell_only") for item in displayed["paths"]))
        self.assertTrue(all(item["path"].get("unit_cell_only") is True for item in unit_cell["paths"]))

    def test_selected_displayed_scope_moves_periodic_copies_of_selected_sources(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        result = animation_path_response(
            payload["render_data"],
            payload["atom_mappings"],
            2,
            scope="selected_displayed",
            selected_atoms=(3,),
            display_mode="expanded_half",
        )

        self.assertEqual([item["source_atom"] for item in result["paths"]], [3])
        self.assertTrue(all(not item["path"].get("unit_cell_only") for item in result["paths"]))

    def test_rejects_unknown_operation(self):
        with self.assertRaisesRegex(ValueError, "Operation index not found"):
            animation_path_response(
                {"operations": [], "atoms": []},
                {"mappings": []},
                99,
            )


class AnimationPathGoldenTest(unittest.TestCase):
    def test_python_reference_matches_public_schema_golden_samples(self):
        fixture_path = Path(__file__).parent / "fixtures" / "animation_path_golden.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        self.assertEqual(fixture["schema_version"], ANIMATION_PATH_SCHEMA_VERSION)
        self.assertEqual(fixture["coordinate_space"], "cartesian")
        for case in fixture["cases"]:
            path = public_path_to_internal(case["path"])
            for sample in case["samples"]:
                with self.subTest(case=case["name"], s=sample["s"]):
                    np.testing.assert_allclose(
                        evaluate_path(path, sample["s"]),
                        sample["position"],
                        atol=1e-6,
                    )

    def test_python_wrap_matches_boundary_golden_samples(self):
        fixture_path = Path(__file__).parent / "fixtures" / "boundary_wrap_golden.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        self.assertEqual(fixture["coordinate_space"], "cartesian")
        for case in fixture["cases"]:
            context = case["context"]
            python_context = (
                np.asarray(context["cell_to_cart"], dtype=float),
                np.asarray(context["cart_to_cell"], dtype=float),
                context["cell_origin_mode"],
            )
            for sample in case["samples"]:
                with self.subTest(case=case["name"], position=sample["position"]):
                    np.testing.assert_allclose(
                        apply_boundary_context(np.asarray(sample["position"]), python_context),
                        sample["wrapped"],
                        atol=1e-6,
                    )


class SymmetryElementsResponseTest(unittest.TestCase):
    def test_uses_python_selected_inversion_center(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))

        result = symmetry_elements_response(
            payload["render_data"],
            payload["atom_mappings"],
            1,
        )

        self.assertEqual(result["coordinate_space"], "cartesian")
        self.assertEqual(result["operation_index"], 1)
        self.assertEqual(result["axes"], [])
        self.assertEqual(result["planes"], [])
        self.assertEqual(result["centers"], [{"point_cart": [0.0, 0.0, 0.0]}])
        self.assertEqual(result["focus_point_cart"], [0.0, 0.0, 0.0])

    def test_supplies_three_view_camera_basis(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        result = symmetry_elements_response(
            payload["render_data"],
            payload["atom_mappings"],
            2,
            display_mode="source",
            cell_origin_mode="center",
        )

        self.assertEqual(len(result["view_direction_cart"]), 3)
        self.assertEqual(len(result["focus_point_cart"]), 3)
        self.assertAlmostEqual(np.linalg.norm(result["view_direction_cart"]), 1.0)

    def test_displayed_elements_match_animation_path_geometry(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        render_data = payload["render_data"]
        mappings = payload["atom_mappings"]
        cases = (
            (187, "plane_point", "planes"),
            (2, "axis_point", "axes"),
            (1, "center", "centers"),
            (3, "axis_point", "axes"),
            (53, "plane_point", "planes"),
            (56, "axis_point", "axes"),
        )

        for operation_index, path_key, element_key in cases:
            with self.subTest(operation_index=operation_index):
                animation = animation_path_response(
                    render_data,
                    mappings,
                    operation_index,
                    display_mode="source",
                    cell_origin_mode="center",
                )
                elements = symmetry_elements_response(
                    render_data,
                    mappings,
                    operation_index,
                    display_mode="source",
                    cell_origin_mode="center",
                )
                path = next(item["path"] for item in animation["paths"] if path_key in item["path"])
                element_point = elements[element_key][0]["point_cart"]
                np.testing.assert_allclose(path[path_key], element_point, atol=1e-8)

    def test_halite_op187_atoms_on_displayed_mirror_plane_do_not_move(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        animation = animation_path_response(
            payload["render_data"],
            payload["atom_mappings"],
            187,
            display_mode="source",
            cell_origin_mode="center",
        )

        stationary_on_plane = []
        for item in animation["paths"]:
            path = public_path_to_internal(item["path"])
            start = np.asarray(path["start"], dtype=float)
            point = np.asarray(path["plane_point"], dtype=float)
            normal = np.asarray(path["plane_normal"], dtype=float)
            if abs(float(np.dot(start - point, normal))) < 1e-8:
                stationary_on_plane.append(item["source_atom"])
                np.testing.assert_allclose(evaluate_path(path, 1.0), start, atol=1e-8)

        self.assertEqual(stationary_on_plane, [2, 7])

    def test_halite_rotoinversion_duration_uses_displayed_instance_paths(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        distances = {}
        for operation_index in (131, 147):
            animation = animation_path_response(
                payload["render_data"],
                payload["atom_mappings"],
                operation_index,
                display_mode="source",
                cell_origin_mode="center",
            )
            distances[operation_index] = animation["maximum_travel_distance"]

        self.assertAlmostEqual(distances[131], 16.2987639176, places=6)
        self.assertAlmostEqual(distances[147], 23.9645641000, places=6)

    def test_all_halite_displayed_elements_match_their_animation_paths(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        render_data = payload["render_data"]
        mappings = payload["atom_mappings"]
        checked = 0

        for operation in render_data["operations"]:
            operation_index = operation["index"]
            animation = animation_path_response(render_data, mappings, operation_index)
            elements = symmetry_elements_response(render_data, mappings, operation_index)
            paths = [item["path"] for item in animation["paths"]]
            for element_key, path_key in (
                ("axes", "axis_point"),
                ("planes", "plane_point"),
                ("centers", "center"),
            ):
                candidates = [path[path_key] for path in paths if path_key in path]
                if not elements[element_key] or not candidates:
                    continue
                with self.subTest(operation_index=operation_index, element=element_key):
                    np.testing.assert_allclose(
                        candidates[0],
                        elements[element_key][0]["point_cart"],
                        atol=1e-8,
                    )
                checked += 1

        self.assertEqual(checked, 244)

    def test_glide_arrow_uses_the_same_translation_as_animation(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        animation = animation_path_response(
            payload["render_data"],
            payload["atom_mappings"],
            53,
        )
        elements = symmetry_elements_response(
            payload["render_data"],
            payload["atom_mappings"],
            53,
        )

        translations = [
            item["path"]["translation"]
            for item in animation["paths"]
            if item["path"]["type"] == "glide"
        ]
        self.assertTrue(translations)
        for translation in translations:
            np.testing.assert_allclose(
                elements["glide_translation_cart"],
                translation,
                atol=1e-8,
            )


def public_path_to_internal(path):
    result = dict(path)
    for key in (
        "start",
        "target",
        "axis_point",
        "axis_direction",
        "translation",
        "plane_point",
        "plane_normal",
        "center",
        "translation_cart",
        "matrix_cart",
    ):
        if key in result:
            result[key] = np.asarray(result[key], dtype=float)
    if "angle_deg" in result:
        result["angle"] = np.deg2rad(result.pop("angle_deg"))
    if "segments" in result:
        result["segments"] = [public_path_to_internal(segment) for segment in result["segments"]]
    return result


if __name__ == "__main__":
    unittest.main()
