import unittest

import numpy as np

from crystal_viewer.viewer.display_atoms import (
    display_atom_instances,
    display_point_cart,
    display_scene_center,
)


def render_data() -> dict:
    lattice = np.eye(3)
    return {
        "atoms": [
            {"index": 0, "element": "X", "atomic_number": 0, "frac": [0.75, 0.25, 0.25], "cart": [0.75, 0.25, 0.25]},
        ],
        "unit_cell": {"lattice": lattice.tolist()},
        "bounds_min": [0, 0, 0],
        "bounds_max": [1, 1, 1],
    }


class DisplayOriginTest(unittest.TestCase):
    def test_center_origin_wraps_unit_cell_around_zero(self):
        item = display_atom_instances(render_data(), display_mode="source", cell_origin_mode="center")[0]

        np.testing.assert_allclose(item["cart"], [-0.25, 0.25, 0.25])
        np.testing.assert_allclose(display_scene_center(render_data(), "source", "center"), [0, 0, 0])
        np.testing.assert_allclose(display_point_cart(render_data(), [0.75, 0.25, 0.25], "source", "center"), [-0.25, 0.25, 0.25])

    def test_corner_origin_keeps_unit_cell_from_zero_to_one(self):
        item = display_atom_instances(render_data(), display_mode="source", cell_origin_mode="corner")[0]

        np.testing.assert_allclose(item["cart"], [0.75, 0.25, 0.25])
        np.testing.assert_allclose(display_scene_center(render_data(), "source", "corner"), [0.5, 0.5, 0.5])
        np.testing.assert_allclose(display_point_cart(render_data(), [0.75, 0.25, 0.25], "source", "corner"), [0.75, 0.25, 0.25])


if __name__ == "__main__":
    unittest.main()
