import json
import tempfile
import unittest
from pathlib import Path

from crystal_viewer.viewer.atom_style import load_atom_style_defaults


class AtomStyleDefaultsTest(unittest.TestCase):
    def test_loads_json_overrides_and_ignores_invalid_colors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "atom_defaults.json"
            path.write_text(
                json.dumps({
                    "default_atom_color": "#ABCDEF",
                    "element_colors": {
                        "C": "#112233",
                        "O": "not-a-color",
                    },
                    "atom_mesh_style": {
                        "ambient": 0.5,
                        "unknown": 1.0,
                    },
                    "highlight_radius_scale": 0.8,
                }),
                encoding="utf-8",
            )

            defaults = load_atom_style_defaults(path)

            self.assertEqual(defaults["default_atom_color"], "#abcdef")
            self.assertEqual(defaults["element_colors"]["C"], "#112233")
            self.assertEqual(defaults["element_colors"]["O"], "#ff0d0d")
            self.assertEqual(defaults["atom_mesh_style"]["ambient"], 0.5)
            self.assertNotIn("unknown", defaults["atom_mesh_style"])
            self.assertEqual(defaults["highlight_radius_scale"], 0.8)

    def test_missing_json_uses_builtin_defaults(self):
        defaults = load_atom_style_defaults(Path("/tmp/does-not-exist-atom-defaults.json"))

        self.assertEqual(defaults["default_atom_color"], "#9aa5b1")
        self.assertEqual(defaults["element_colors"]["C"], "#909090")


if __name__ == "__main__":
    unittest.main()
