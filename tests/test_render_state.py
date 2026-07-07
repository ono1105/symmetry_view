import unittest

from crystal_viewer.viewer.render_state import (
    PRESERVED_STATE_KEYS,
    apply_render_state_update,
    initial_render_state,
    pop_render_state_snapshot,
    preserved_render_state,
)


def minimal_payload() -> dict:
    return {
        "source_kind": "crystal",
        "render_data": {
            "metadata": {"mode": "crystal"},
            "atoms": [{"index": 0}],
            "operations": [{"index": 4}],
        },
    }


class RenderStateTest(unittest.TestCase):
    def test_cell_basis_preferences_have_one_shared_preservation_list(self):
        state = {key: f"value-{key}" for key in PRESERVED_STATE_KEYS}

        self.assertEqual(preserved_render_state(state), state)
        self.assertIn("animation_boundary_mode", PRESERVED_STATE_KEYS)
        self.assertIn("pause_at_breakpoints", PRESERVED_STATE_KEYS)
        self.assertIn("show_trajectories", PRESERVED_STATE_KEYS)

    def test_initial_render_state_preserves_view_preferences(self):
        state = initial_render_state(
            minimal_payload(),
            initial_operation=None,
            display_mode="source",
            preserved={
                "speed": 2.0,
                "projection_mode": "orthographic",
                "background_mode": "dark",
                "legend_visible": True,
                "cell_origin_mode": "corner",
                "improper_mode": "rotoreflection",
                "display_mode": "expanded_quarter",
                "include_boundary_images": True,
                "animation_boundary_mode": "wrap",
                "pause_at_breakpoints": True,
                "show_trajectories": True,
                "reload_request_id": 7,
            },
        )

        self.assertEqual(state["speed"], 2.0)
        self.assertEqual(state["projection_mode"], "orthographic")
        self.assertEqual(state["background_mode"], "dark")
        self.assertTrue(state["legend_visible"])
        self.assertEqual(state["cell_origin_mode"], "corner")
        self.assertEqual(state["improper_mode"], "rotoreflection")
        self.assertEqual(state["display_mode"], "expanded_quarter")
        self.assertTrue(state["include_boundary_images"])
        self.assertEqual(state["animation_boundary_mode"], "wrap")
        self.assertTrue(state["pause_at_breakpoints"])
        self.assertTrue(state["show_trajectories"])
        self.assertEqual(state["reload_request_id"], 7)

    def test_initial_render_state_defaults_to_dark_background(self):
        state = initial_render_state(minimal_payload(), initial_operation=None, display_mode="source")

        self.assertEqual(state["background_mode"], "dark")
        self.assertTrue(state["legend_visible"])  # legend is shown by default
        self.assertEqual(state["cell_origin_mode"], "center")
        self.assertEqual(state["animation_boundary_mode"], "continuous")
        self.assertFalse(state["pause_at_breakpoints"])
        self.assertFalse(state["show_trajectories"])
        self.assertFalse(state["include_boundary_images"])

    def test_apply_render_state_update_ignores_unknown_keys(self):
        state = initial_render_state(minimal_payload(), initial_operation=None, display_mode="source")

        apply_render_state_update(
            state,
            {
                "speed": 3.0,
                "background_mode": "dark",
                "legend_visible": True,
                "cell_origin_mode": "corner",
                "unknown": "ignored",
            },
        )

        self.assertEqual(state["speed"], 3.0)
        self.assertEqual(state["background_mode"], "dark")
        self.assertTrue(state["legend_visible"])
        self.assertEqual(state["cell_origin_mode"], "corner")
        self.assertNotIn("unknown", state)

    def test_pop_render_state_snapshot_consumes_one_shot_flags(self):
        state = initial_render_state(minimal_payload(), initial_operation=None, display_mode="source")
        state["reset"] = True
        state["clear_custom_check"] = True

        snapshot = pop_render_state_snapshot(state)

        self.assertTrue(snapshot.reset)
        self.assertTrue(snapshot.clear_custom_check)
        self.assertEqual(snapshot.animation_boundary_mode, "continuous")
        self.assertFalse(snapshot.pause_at_breakpoints)
        self.assertNotIn("reset", state)
        self.assertNotIn("clear_custom_check", state)


if __name__ == "__main__":
    unittest.main()
