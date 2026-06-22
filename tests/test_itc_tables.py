import json
import unittest
from pathlib import Path

from crystal_viewer.itc_tables import itc_coordinate_summaries, load_itc_operation_data
from crystal_viewer.viewer.cell_settings import standardized_payload


class ItcTablesTest(unittest.TestCase):
    def test_table_contains_all_space_groups(self):
        data = load_itc_operation_data()

        self.assertEqual(len(data["space_groups"]), 230)
        self.assertEqual(data["space_groups"]["225"]["operation_count"], 192)

    def test_halite_matches_every_operation(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        render_data = payload["render_data"]

        matches = itc_coordinate_summaries(render_data)

        self.assertEqual(len(matches), len(render_data["operations"]))
        self.assertEqual(matches[0], "x, y, z")

    def test_cadmoselite_matches_every_operation(self):
        payload = json.loads(Path("exports/json/cadmoselite.json").read_text(encoding="utf-8"))
        render_data = payload["render_data"]

        matches = itc_coordinate_summaries(render_data)

        self.assertEqual(len(matches), len(render_data["operations"]))

    def test_batio3_native_rhombohedral_cell_does_not_fake_full_match(self):
        payload = json.loads(Path("exports/json/batio3.json").read_text(encoding="utf-8"))
        render_data = payload["render_data"]

        matches = itc_coordinate_summaries(render_data)

        self.assertLess(len(matches), len(render_data["operations"]))

    def test_batio3_conventional_cell_matches_every_operation(self):
        payload = json.loads(Path("exports/json/batio3.json").read_text(encoding="utf-8"))
        converted = standardized_payload(payload, "conventional", require_distinct=True)

        self.assertIsNotNone(converted)
        assert converted is not None
        render_data = converted["render_data"]
        matches = itc_coordinate_summaries(render_data)

        self.assertEqual(len(matches), len(render_data["operations"]))
        self.assertEqual(matches[9], "-y+2/3, -x+1/3, z+1/3")


if __name__ == "__main__":
    unittest.main()
