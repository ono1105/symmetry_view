import json
import unittest
from pathlib import Path

from crystal_viewer.viewer.cell_settings import hexagonal_conventional_render_data


class CellSettingsTest(unittest.TestCase):
    def test_batio3_rhombohedral_can_be_displayed_as_hexagonal_conventional(self):
        payload = json.loads(Path("exports/json/batio3.json").read_text(encoding="utf-8"))
        converted = hexagonal_conventional_render_data(payload["render_data"])

        self.assertIsNotNone(converted)
        assert converted is not None
        lattice = converted["metadata"]["display_lattice_parameters"]
        self.assertAlmostEqual(lattice["a"], lattice["b"], places=6)
        self.assertAlmostEqual(lattice["alpha"], 90.0, places=6)
        self.assertAlmostEqual(lattice["beta"], 90.0, places=6)
        self.assertAlmostEqual(lattice["gamma"], 120.0, places=6)
        self.assertEqual(len(converted["atoms"]), 15)
        self.assertEqual(converted["metadata"]["display_cell_setting"], "hexagonal_conventional")

    def test_non_r_lattice_returns_none(self):
        render_data = {
            "metadata": {"mode": "crystal"},
            "atoms": [
                {"index": 0, "element": "Na", "frac": [0.0, 0.0, 0.0]},
                {"index": 1, "element": "Cl", "frac": [0.5, 0.5, 0.5]},
            ],
            "unit_cell": {
                "lattice": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "vertices_cart": [],
                "edges": [],
            },
        }

        self.assertIsNone(hexagonal_conventional_render_data(render_data))


if __name__ == "__main__":
    unittest.main()
