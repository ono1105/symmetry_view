"""The example catalog must agree with the exports it was generated from.

The catalog is a build artifact of tools/regenerate_example_assets.py, but it is
tracked in git and the browser trusts it: the structure picker decides what to
offer from `puzzle_counts`, and shows `display_formula` to the player.  A stale
catalog would therefore offer unplayable structures, or hide playable ones,
without anything else failing.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from crystal_viewer.export_pipeline import default_json_output_path
from crystal_viewer.game.catalog import (
    PUZZLE_COUNT_KEYS,
    beyond_quiz_vocabulary,
    puzzle_counts,
)
from crystal_viewer.source_kinds import SOURCE_KIND_CRYSTAL, SOURCE_KIND_MOLECULE
from tools.view_json_server import resolve_example_path


CATALOG_PATH = Path("examples/example_catalog.json")
EXPORT_DIR = Path("exports/json")


def _catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _entries() -> list[dict]:
    catalog = _catalog()
    return [*catalog[SOURCE_KIND_CRYSTAL], *catalog[SOURCE_KIND_MOLECULE]]


class ExampleCatalogTest(unittest.TestCase):
    def test_every_entry_points_at_an_openable_example(self):
        for entry in _entries():
            with self.subTest(entry["name"]):
                path = resolve_example_path(entry["kind"], entry["path"])
                self.assertTrue(path.exists())

    def test_names_are_unique_within_a_kind(self):
        catalog = _catalog()
        for kind in (SOURCE_KIND_CRYSTAL, SOURCE_KIND_MOLECULE):
            names = [entry["name"] for entry in catalog[kind]]
            self.assertCountEqual(names, set(names), f"duplicate {kind} name")

    def test_entry_count_matches_the_example_directories(self):
        catalog = _catalog()
        self.assertEqual(
            len(catalog[SOURCE_KIND_CRYSTAL]), len(list(Path("examples/cif").glob("*.cif")))
        )
        self.assertEqual(
            len(catalog[SOURCE_KIND_MOLECULE]),
            len(list(Path("examples/molecules").glob("*.xyz"))),
        )

    def test_puzzle_counts_match_the_exports(self):
        for entry in _entries():
            with self.subTest(entry["name"]):
                export = default_json_output_path(Path(entry["path"]), EXPORT_DIR)
                render_data = json.loads(export.read_text(encoding="utf-8"))["render_data"]
                self.assertEqual(entry["puzzle_counts"], puzzle_counts(render_data))

    def test_display_formula_is_the_molecular_formula_not_the_reduced_one(self):
        molecules = {entry["name"]: entry for entry in _catalog()[SOURCE_KIND_MOLECULE]}
        self.assertEqual(molecules["benzene"]["display_formula"], "C6H6")
        self.assertEqual(molecules["benzene"]["formula"], "HC")
        self.assertEqual(molecules["ammonia"]["display_formula"], "NH3")

    def test_beyond_quiz_vocabulary_matches_the_exports(self):
        for entry in _entries():
            with self.subTest(entry["name"]):
                export = default_json_output_path(Path(entry["path"]), EXPORT_DIR)
                render_data = json.loads(export.read_text(encoding="utf-8"))["render_data"]
                self.assertEqual(
                    entry["beyond_quiz_vocabulary"], beyond_quiz_vocabulary(render_data)
                )

    def test_linear_molecules_stay_quizzable(self):
        # C∞v / D∞h carry an infinite rotation axis, which the ∞ option does
        # answer. Treating "not a 2/3/4/6 fold" as unnameable would withdraw
        # CO2 and HCl from the quizzes they are the best examples for.
        molecules = {entry["name"]: entry for entry in _catalog()[SOURCE_KIND_MOLECULE]}
        for name in ("carbon_dioxide", "hydrogen_chloride"):
            with self.subTest(name):
                self.assertFalse(molecules[name]["beyond_quiz_vocabulary"])

    def test_the_icosahedral_clusters_are_the_analysis_only_ones(self):
        # They are withheld despite having questions: 71 identify, 40
        # composition, 30 mapping. Offering those would ask only about the C2
        # and C3 axes of an object whose point is its 5-fold ones.
        analysis_only = {
            entry["name"] for entry in _entries() if entry["beyond_quiz_vocabulary"]
        }
        self.assertEqual(analysis_only, {"al12w_icosahedron", "mackay_icosahedron"})
        for entry in _entries():
            if entry["name"] in analysis_only:
                self.assertGreater(entry["puzzle_counts"]["operation_normal"], 0)

    def test_only_asymmetric_examples_have_nothing_in_the_other_four_quizzes(self):
        # A structure with zero questions in the four operation-based quizzes
        # is correct only for a structure whose only operation is the identity
        # (point group 1 / C1 — bundled to show what "no symmetry" looks
        # like), and a bug for anything else. Note this is not the only reason
        # a structure can be withheld; see beyond_quiz_vocabulary.
        #
        # The point-group quiz is excluded from this check on purpose: it
        # always has exactly one question (the structure's own point group),
        # so a C1 structure is legitimately playable there — "this has no
        # symmetry" is itself a valid answer — even with nothing to ask in the
        # other four.
        other_keys = [key for key in PUZZLE_COUNT_KEYS if key != "point_group"]
        for entry in _entries():
            if any(entry["puzzle_counts"][key] for key in other_keys):
                continue
            with self.subTest(entry["name"]):
                self.assertIn(entry["point_group"], ("1", "C1"))
                self.assertEqual(entry["puzzle_counts"]["point_group"], 1)


if __name__ == "__main__":
    unittest.main()
