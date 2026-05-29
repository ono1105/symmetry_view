import json
import os
import tempfile
import unittest
from pathlib import Path

from crystal_viewer.json_export import EXPORT_SCHEMA_VERSION
from tools.view_json_server import (
    atom_motion_api_items,
    cached_export_json_path,
    example_catalog,
    export_cell_setting_json_worker,
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
