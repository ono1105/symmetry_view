import json
import os
import tempfile
import unittest
from pathlib import Path

from crystal_viewer.json_export import EXPORT_SCHEMA_VERSION
from tools.view_json_server import (
    atom_motion_api_items,
    cached_export_json_path,
    compose_operation_indices,
    compose_operation_sequence_items,
    example_catalog,
    export_cell_setting_json_worker,
    find_operation_sequence_for_target,
    replace_shared_state_for_load,
    resolve_example_path,
)


class AtomMotionApiItemsTest(unittest.TestCase):
    def test_returns_source_and_target_coordinates_for_selected_operation(self):
        render_data = {
            "atoms": [
                {"index": 0, "frac": [0.0, 0.0, 0.0], "cart": [0.0, 0.0, 0.0]},
                {"index": 1, "frac": [0.5, 0.5, 0.5], "cart": [1.0, 1.0, 1.0]},
            ]
        }
        atom_mappings = {
            "mappings": [
                {"operation_index": 0, "entries": []},
                {
                    "operation_index": 1,
                    "entries": [
                        {
                            "source_atom": 0,
                            "target_atom": 1,
                            "distance": 0.0,
                            "transformed_cart": [1.0, 1.0, 1.0],
                            "transformed_frac": [0.5, 0.5, 0.5],
                            "wrapped_frac": [0.5, 0.5, 0.5],
                            "animation_frac": [0.5, 0.5, 0.5],
                        }
                    ],
                },
            ]
        }

        self.assertEqual(
            atom_motion_api_items(render_data, atom_mappings, 1),
            [
                {
                    "source_atom": 0,
                    "target_atom": 1,
                    "start_frac": [0.0, 0.0, 0.0],
                    "start_cart": [0.0, 0.0, 0.0],
                    "target_frac": [0.5, 0.5, 0.5],
                    "target_cart": [1.0, 1.0, 1.0],
                    "wrapped_frac": [0.5, 0.5, 0.5],
                    "animation_frac": [0.5, 0.5, 0.5],
                    "distance": 0.0,
                }
            ],
        )

    def test_returns_empty_list_without_mapping(self):
        self.assertEqual(atom_motion_api_items({"atoms": []}, None, 1), [])


class LoadedStateReplacementTest(unittest.TestCase):
    def test_preserves_nonzero_load_request_id_for_async_summary_worker(self):
        shared_state = {"load_request_id": 12, "old": True}
        next_state = {"summaries_ready": False}

        replace_shared_state_for_load(shared_state, next_state, request_id=42)

        self.assertEqual(
            shared_state,
            {"summaries_ready": False, "load_request_id": 42},
        )


class ComposeOperationIndicesTest(unittest.TestCase):
    def test_composes_in_application_order_and_finds_matching_operation(self):
        c4 = [
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 1],
        ]
        render_data = {
            "unit_cell": {"lattice": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
            "atoms": [],
            "operations": [
                {"index": 0, "matrix_frac": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "translation_frac": [0, 0, 0]},
                {"index": 1, "matrix_frac": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "translation_frac": [0.25, 0, 0]},
                {"index": 2, "matrix_frac": c4, "translation_frac": [0, 0, 0]},
                {"index": 3, "matrix_frac": c4, "translation_frac": [0, 0.25, 0]},
            ],
        }

        result = compose_operation_indices(render_data, [1, 2], 0.01)

        self.assertTrue(result["is_symmetry"])
        self.assertEqual(result["matching_operation_index"], 3)
        self.assertEqual(result["operation_indices"], [1, 2])
        self.assertEqual(result["W_frac"], c4)
        self.assertEqual(result["t_frac"], [0.0, 0.25, 0.0])


class FindOperationSequenceForTargetTest(unittest.TestCase):
    def test_finds_sequence_from_generators(self):
        c4 = [
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 1],
        ]
        c2 = [
            [-1, 0, 0],
            [0, -1, 0],
            [0, 0, 1],
        ]
        render_data = {
            "operations": [
                {"index": 0, "matrix_frac": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "translation_frac": [0, 0, 0]},
                {"index": 1, "matrix_frac": c4, "translation_frac": [0, 0, 0]},
                {"index": 2, "matrix_frac": c2, "translation_frac": [0, 0, 0]},
            ],
        }

        result = find_operation_sequence_for_target(render_data, 2, [1], 3)

        self.assertEqual(result["sequence"], [1, 1])
        self.assertTrue(result["found"])

    def test_reports_not_found_with_depth_limit(self):
        c4 = [
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 1],
        ]
        c2 = [
            [-1, 0, 0],
            [0, -1, 0],
            [0, 0, 1],
        ]
        render_data = {
            "operations": [
                {"index": 1, "matrix_frac": c4, "translation_frac": [0, 0, 0]},
                {"index": 2, "matrix_frac": c2, "translation_frac": [0, 0, 0]},
            ],
        }

        result = find_operation_sequence_for_target(render_data, 2, [1], 1)

        self.assertIsNone(result["sequence"])
        self.assertFalse(result["found"])

    def test_returns_error_for_missing_operation_index(self):
        render_data = {
            "unit_cell": {"lattice": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
            "atoms": [],
            "operations": [],
        }

        result = compose_operation_indices(render_data, [99], 0.01)

        self.assertEqual(result, {"error": "Operation index not found: 99"})

    def test_composes_real_halite_operations(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))

        result = compose_operation_indices(payload["render_data"], [1, 2], 1e-2)

        self.assertTrue(result["is_symmetry"])
        self.assertEqual(result["matching_operation_index"], 3)

    def test_composes_existing_and_custom_sequence_items(self):
        c4 = [
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 1],
        ]
        render_data = {
            "unit_cell": {"lattice": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
            "atoms": [],
            "operations": [
                {"index": 0, "matrix_frac": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "translation_frac": [0, 0, 0]},
                {"index": 2, "matrix_frac": c4, "translation_frac": [0, 0, 0]},
                {"index": 3, "matrix_frac": c4, "translation_frac": [0, 0.25, 0]},
            ],
        }

        result = compose_operation_sequence_items(
            render_data,
            [
                {"type": "custom", "label": "custom translation", "W_frac": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "t_frac": [0.25, 0, 0]},
                {"type": "operation", "index": 2},
            ],
            0.01,
        )

        self.assertTrue(result["is_symmetry"])
        self.assertEqual(result["matching_operation_index"], 3)
        self.assertEqual(result["sequence_labels"], ["custom translation", "op 2"])
        self.assertEqual(result["t_frac"], [0.0, 0.25, 0.0])


class CachedExportJsonPathTest(unittest.TestCase):
    def test_accepts_current_matching_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, output_path = self.write_cached_export(tmp, schema_version=EXPORT_SCHEMA_VERSION)

            cached = cached_export_json_path(input_path, output_path, mode="crystal")

            self.assertIsNotNone(cached)
            self.assertEqual(cached[0], output_path)

    def test_rejects_stale_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, output_path = self.write_cached_export(tmp, schema_version=EXPORT_SCHEMA_VERSION)
            os.utime(output_path, (input_path.stat().st_atime - 10, input_path.stat().st_mtime - 10))

            self.assertIsNone(cached_export_json_path(input_path, output_path, mode="crystal"))

    def test_rejects_old_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, output_path = self.write_cached_export(tmp, schema_version=EXPORT_SCHEMA_VERSION - 1)

            self.assertIsNone(cached_export_json_path(input_path, output_path, mode="crystal"))

    def test_rejects_source_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, output_path = self.write_cached_export(
                tmp,
                schema_version=EXPORT_SCHEMA_VERSION,
                source_file="/tmp/different.cif",
            )

            self.assertIsNone(cached_export_json_path(input_path, output_path, mode="crystal"))

    def write_cached_export(
        self,
        tmp: str,
        *,
        schema_version: int,
        source_file: str | None = None,
    ) -> tuple[Path, Path]:
        directory = Path(tmp)
        input_path = directory / "source.cif"
        output_path = directory / "source.json"
        input_path.write_text("data_source\n", encoding="utf-8")
        payload = {
            "schema_version": schema_version,
            "source_kind": "crystal",
            "render_data": {
                "metadata": {
                    "mode": "crystal",
                    "source_file": source_file or str(input_path),
                }
            },
            "atom_mappings": {"mappings": []},
        }
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        output_mtime = input_path.stat().st_mtime + 10
        os.utime(output_path, (output_mtime, output_mtime))
        return input_path, output_path


class CellSettingWorkerTest(unittest.TestCase):
    def test_worker_converts_batio3_to_conventional_cell(self):
        payload = json.loads(Path("exports/json/batio3.json").read_text(encoding="utf-8"))

        converted = export_cell_setting_json_worker(
            payload,
            cell_setting="conventional",
            tolerance_cart=1e-2,
            indent=2,
            timeout_sec=30,
            require_distinct=True,
        )

        render_data = converted["render_data"]
        self.assertEqual(render_data["metadata"]["display_cell_setting"], "conventional")
        self.assertEqual(len(render_data["atoms"]), 15)
        self.assertTrue(converted["atom_mappings"]["complete"])

    def test_worker_can_require_distinct_primitive_cell(self):
        payload = json.loads(Path("exports/json/agcl.json").read_text(encoding="utf-8"))

        with self.assertRaises(RuntimeError):
            export_cell_setting_json_worker(
                payload,
                cell_setting="primitive",
                tolerance_cart=1e-2,
                indent=2,
                timeout_sec=30,
                require_distinct=True,
            )

    def test_worker_can_require_distinct_bravais_cell(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))

        with self.assertRaises(RuntimeError):
            export_cell_setting_json_worker(
                payload,
                cell_setting="conventional",
                tolerance_cart=1e-2,
                indent=2,
                timeout_sec=30,
                require_distinct=True,
            )

    def test_worker_can_round_trip_halite_primitive_to_bravais(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        primitive = export_cell_setting_json_worker(
            payload,
            cell_setting="primitive",
            tolerance_cart=1e-2,
            indent=2,
            timeout_sec=30,
            require_distinct=True,
        )

        bravais = export_cell_setting_json_worker(
            primitive,
            cell_setting="conventional",
            tolerance_cart=1e-2,
            indent=2,
            timeout_sec=30,
            require_distinct=True,
        )

        self.assertEqual(bravais["render_data"]["metadata"]["display_cell_setting"], "conventional")
        self.assertEqual(len(bravais["render_data"]["atoms"]), 8)

    def test_worker_can_round_trip_batio3_bravais_to_primitive(self):
        payload = json.loads(Path("exports/json/batio3.json").read_text(encoding="utf-8"))
        bravais = export_cell_setting_json_worker(
            payload,
            cell_setting="conventional",
            tolerance_cart=1e-2,
            indent=2,
            timeout_sec=30,
            require_distinct=True,
        )

        primitive = export_cell_setting_json_worker(
            bravais,
            cell_setting="primitive",
            tolerance_cart=1e-2,
            indent=2,
            timeout_sec=30,
            require_distinct=True,
        )

        self.assertEqual(primitive["render_data"]["metadata"]["display_cell_setting"], "primitive")
        self.assertEqual(len(primitive["render_data"]["atoms"]), 5)


class ExampleCatalogAndPathTest(unittest.TestCase):
    def test_example_catalog_uses_canonical_directories(self):
        catalog = example_catalog()

        self.assertEqual(len(catalog["crystal"]), 32)
        self.assertEqual(len(catalog["molecule"]), 11)
        self.assertTrue(
            all(item["path"].startswith("examples/cif/") for item in catalog["crystal"])
        )
        self.assertTrue(
            all(item["path"].startswith("examples/molecules/") for item in catalog["molecule"])
        )

    def test_resolve_example_path_accepts_catalog_crystal(self):
        path = resolve_example_path("crystal", "examples/cif/Halite.cif")

        self.assertEqual(path.name, "Halite.cif")

    def test_resolve_example_path_rejects_noncanonical_directory(self):
        with self.assertRaises(ValueError):
            resolve_example_path("crystal", "examples/molecules/water.xyz")

    def test_resolve_example_path_rejects_parent_escape(self):
        with self.assertRaises(ValueError):
            resolve_example_path("crystal", "examples/cif/../molecules/water.xyz")


if __name__ == "__main__":
    unittest.main()
