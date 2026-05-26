import unittest

from tools.view_json_server import atom_motion_api_items


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


if __name__ == "__main__":
    unittest.main()
