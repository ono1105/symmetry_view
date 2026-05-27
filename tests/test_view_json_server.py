import json
import os
import tempfile
import unittest
from pathlib import Path

from crystal_viewer.json_export import EXPORT_SCHEMA_VERSION
from tools.view_json_server import atom_motion_api_items, cached_export_json_path


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


if __name__ == "__main__":
    unittest.main()
