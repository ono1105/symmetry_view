import unittest

from crystal_viewer.viewer.render_state import (
    apply_render_state_update,
    initial_render_state,
    pop_render_state_snapshot,
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
                "improper_mode": "rotoreflection",
                "display_mode": "expanded_quarter",
                "reload_request_id": 7,
            },
        )

        self.assertEqual(state["speed"], 2.0)
        self.assertEqual(state["projection_mode"], "orthographic")
        self.assertEqual(state["background_mode"], "dark")
        self.assertTrue(state["legend_visible"])
        self.assertEqual(state["improper_mode"], "rotoreflection")
        self.assertEqual(state["display_mode"], "expanded_quarter")
        self.assertEqual(state["reload_request_id"], 7)

    def test_initial_render_state_defaults_to_dark_background(self):
        state = initial_render_state(minimal_payload(), initial_operation=None, display_mode="source")

        self.assertEqual(state["background_mode"], "dark")
        self.assertFalse(state["legend_visible"])

    def test_apply_render_state_update_ignores_unknown_keys(self):
        state = initial_render_state(minimal_payload(), initial_operation=None, display_mode="source")

        apply_render_state_update(
            state,
            {"speed": 3.0, "background_mode": "dark", "legend_visible": True, "unknown": "ignored"},
        )

        self.assertEqual(state["speed"], 3.0)
        self.assertEqual(state["background_mode"], "dark")
        self.assertTrue(state["legend_visible"])
        self.assertNotIn("unknown", state)

    def test_pop_render_state_snapshot_consumes_one_shot_flags(self):
        state = initial_render_state(minimal_payload(), initial_operation=None, display_mode="source")
        state["reset"] = True
        state["clear_custom_check"] = True

        snapshot = pop_render_state_snapshot(state)

        self.assertTrue(snapshot.reset)
        self.assertTrue(snapshot.clear_custom_check)
        self.assertNotIn("reset", state)
        self.assertNotIn("clear_custom_check", state)


if __name__ == "__main__":
    unittest.main()
