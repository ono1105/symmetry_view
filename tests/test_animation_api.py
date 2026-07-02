import json
import unittest
from pathlib import Path

import numpy as np

from crystal_viewer.viewer.animation_api import (
    ANIMATION_PATH_SCHEMA_VERSION,
    animation_path_response,
    serialize_animation_path,
    symmetry_elements_response,
)
from crystal_viewer.viewer.animation_path import evaluate_path


class SerializeAnimationPathTest(unittest.TestCase):
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
        self.assertEqual(result["playback_speed_multiplier"], 1.0)
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
