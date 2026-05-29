import json
import unittest
from pathlib import Path

import numpy as np

from crystal_viewer.viewer.animation_context import animation_paths
from crystal_viewer.viewer.cell_settings import (
    standardized_payload,
    standardized_cell_render_data,
    hexagonal_conventional_render_data,
)
from crystal_viewer.viewer.operation_lookup import selected_mapping


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

    def test_non_r_lattice_does_not_use_hexagonal_r_wrapper(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))

        self.assertIsNone(hexagonal_conventional_render_data(payload["render_data"]))

    def test_face_centered_cubic_can_be_displayed_as_primitive(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        converted = standardized_cell_render_data(payload["render_data"], "primitive")

        self.assertIsNotNone(converted)
        assert converted is not None
        lattice = converted["metadata"]["display_lattice_parameters"]
        self.assertEqual(len(converted["atoms"]), 2)
        self.assertAlmostEqual(lattice["alpha"], 60.0, places=6)
        self.assertAlmostEqual(lattice["beta"], 60.0, places=6)
        self.assertAlmostEqual(lattice["gamma"], 60.0, places=6)
        self.assertEqual(converted["metadata"]["display_cell_setting"], "primitive")

    def test_body_centered_tetragonal_can_be_displayed_as_primitive(self):
        payload = json.loads(Path("exports/json/nbp.json").read_text(encoding="utf-8"))
        converted = standardized_cell_render_data(payload["render_data"], "primitive")

        self.assertIsNotNone(converted)
        assert converted is not None
        self.assertEqual(len(converted["atoms"]), 4)
        self.assertEqual(converted["metadata"]["display_cell_setting"], "primitive")

    def test_native_mode_marks_untransformed_copy(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        render_data = payload["render_data"]
        converted = standardized_cell_render_data(render_data, "native")

        self.assertIsNot(converted, render_data)
        assert converted is not None
        self.assertEqual(len(converted["atoms"]), len(render_data["atoms"]))
        self.assertEqual(converted["metadata"]["display_cell_setting"], "native")
        self.assertEqual(converted["metadata"]["display_atom_count"], len(render_data["atoms"]))
        self.assertIn("display_lattice_parameters", converted["metadata"])

    def test_standardized_payload_reanalyzes_operations_and_atom_mappings(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        converted = standardized_payload(payload, "primitive")

        self.assertIsNotNone(converted)
        assert converted is not None
        render_data = converted["render_data"]
        mappings = converted["atom_mappings"]
        self.assertEqual(len(render_data["atoms"]), 2)
        self.assertEqual(len(mappings["mappings"]), len(render_data["operations"]))
        self.assertEqual(render_data["metadata"]["display_cell_setting"], "primitive")
        self.assertTrue(mappings["complete"])

    def test_standardized_payload_can_require_distinct_primitive_cell(self):
        payload = json.loads(Path("exports/json/agcl.json").read_text(encoding="utf-8"))

        self.assertIsNone(standardized_payload(payload, "primitive", require_distinct=True))

    def test_standardized_payload_conventionalizes_rhombohedral_batio3(self):
        payload = json.loads(Path("exports/json/batio3.json").read_text(encoding="utf-8"))
        converted = standardized_payload(payload, "conventional", require_distinct=True)

        self.assertIsNotNone(converted)
        assert converted is not None
        render_data = converted["render_data"]
        lattice = render_data["metadata"]["lattice_parameters"]
        self.assertEqual(len(render_data["atoms"]), 15)
        self.assertAlmostEqual(lattice["gamma"], 120.0, places=6)
        self.assertEqual(render_data["metadata"]["display_cell_setting"], "conventional")
        self.assertTrue(converted["atom_mappings"]["complete"])

    def test_batio3_conventional_screw_animation_translation_follows_axis(self):
        payload = json.loads(Path("exports/json/batio3.json").read_text(encoding="utf-8"))
        converted = standardized_payload(payload, "conventional", require_distinct=True)

        self.assertIsNotNone(converted)
        assert converted is not None
        render_data = converted["render_data"]
        operation = render_data["operations"][7]
        mapping = selected_mapping(converted["atom_mappings"], operation["index"])
        self.assertIsNotNone(mapping)
        assert mapping is not None

        path = next(iter(animation_paths(render_data, operation, mapping, animation_scope="representative").values()))
        axis_direction = np.asarray(path["axis_direction"], dtype=float)
        translation = np.asarray(path["translation"], dtype=float)
        perpendicular = translation - float(np.dot(translation, axis_direction)) * axis_direction
        self.assertLess(np.linalg.norm(perpendicular), 1e-8)

    def test_standardized_payload_can_require_distinct_conventional_cell(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))

        self.assertIsNone(standardized_payload(payload, "conventional", require_distinct=True))


if __name__ == "__main__":
    unittest.main()
