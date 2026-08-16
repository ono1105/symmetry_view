import json
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from crystal_viewer.game.atom_mapping import mapping_questions
from crystal_viewer.game.composition import composition_questions
from crystal_viewer.viewer.render_state import initial_render_state
from crystal_viewer.viewer.session import ViewerSession
from tools.view_json_server import make_handler, start_server


EXPORT_DIR = Path("exports/json")

IMPROPER_NOTATION = {"rotoreflection": "S{order}", "rotoinversion": "-{order}"}


class ServedStructure:
    """One export served over HTTP, so tests exercise the real request path."""

    def __init__(self, name: str) -> None:
        self.json_path = EXPORT_DIR / f"{name}.json"
        self.payload = json.loads(self.json_path.read_text(encoding="utf-8"))
        self.session = ViewerSession(self.json_path, self.payload, summarize_operations=False)
        handler = make_handler(
            self.session,
            initial_render_state(self.payload, initial_operation=None, display_mode="source"),
            threading.Lock(),
            json_dir=EXPORT_DIR,
            import_json_dir=EXPORT_DIR,
            tolerance_cart=1e-3,
            indent=2,
            analysis_timeout_sec=5.0,
            default_display_mode="source",
            initial_app_mode="puzzle",
        )
        self.server = start_server("127.0.0.1", 0, handler)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    @property
    def render_data(self) -> dict:
        return self.session.render_data

    def get_json(self, path):
        with urlopen(self.base_url + path, timeout=10) as response:
            return json.loads(response.read())

    def post_json(self, path, payload):
        request = Request(
            self.base_url + path,
            method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload).encode("utf-8"),
        )
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read())


class PuzzleServerApiTest(unittest.TestCase):
    # methane exercises the plain molecule contract; benzene adds an axis that
    # carries improper operations of two different folds (S6 and S3), which is
    # where a published label can disagree with the answer it is asked about;
    # halite is the crystal case, where the mapping quiz must publish nothing.
    STRUCTURES = ("methane", "benzene", "halite")

    @classmethod
    def setUpClass(cls):
        cls.served = {name: ServedStructure(name) for name in cls.STRUCTURES}

    @classmethod
    def tearDownClass(cls):
        for served in cls.served.values():
            served.close()

    def test_composition_routes_hide_then_reveal_the_product(self):
        for name in ("methane", "benzene"):
            with self.subTest(structure=name):
                served = self.served[name]
                public = served.get_json("/api/puzzle/composition")
                self.assertEqual(public["source_kind"], "molecule")
                self.assertTrue(public["questions"])
                question = public["questions"][0]
                self.assertNotIn("answers", question)
                self.assertNotIn("product_index", question)

                private = composition_questions(served.render_data)[question["id"]]
                answer = private["answers"][0]
                checked = served.post_json(
                    "/api/puzzle/composition/check",
                    {
                        "question_id": question["id"],
                        "kind": answer["kind"],
                        "order": answer["order"],
                    },
                )
                self.assertTrue(checked["correct"])
                self.assertEqual(checked["product_index"], private["product_index"])

    def test_mapping_routes_name_the_operation_but_hide_the_target(self):
        for name in ("methane", "benzene"):
            with self.subTest(structure=name):
                served = self.served[name]
                public = served.get_json("/api/puzzle/mapping")
                self.assertEqual(public["source_kind"], "molecule")
                self.assertTrue(public["questions"])
                question = public["questions"][0]
                self.assertIn("operation", question)
                self.assertNotIn("target_atom_index", question)

                private = mapping_questions(served.render_data)[question["id"]]
                checked = served.post_json(
                    "/api/puzzle/mapping/check",
                    {
                        "question_id": question["id"],
                        "selected_atom_index": private["target_atom_index"],
                    },
                )
                self.assertTrue(checked["correct"])
                self.assertEqual(checked["target_atom_index"], private["target_atom_index"])

    def test_point_group_routes_hide_then_reveal_the_answer(self):
        for name in ("methane", "benzene", "halite"):
            with self.subTest(structure=name):
                served = self.served[name]
                public = served.get_json("/api/puzzle/point_group")
                self.assertTrue(public["questions"])
                question = public["questions"][0]
                self.assertNotIn("correct", question)
                self.assertNotIn("answer", question)

                correct = served.render_data["metadata"]["point_group_label"]
                self.assertIn(correct, question["options"])
                checked = served.post_json(
                    "/api/puzzle/point_group/check",
                    {"question_id": question["id"], "selected": correct},
                )
                self.assertTrue(checked["correct"])
                self.assertEqual(checked["answer"], correct)

    def test_crystals_publish_no_mapping_questions(self):
        served = self.served["halite"]
        public = served.get_json("/api/puzzle/mapping")
        self.assertEqual(public["source_kind"], "crystal")
        # An atom's image under a crystal operation can be a periodic copy outside
        # the drawn cell, so the quiz has no unambiguous target to click.
        self.assertEqual(public["questions"], [])
        with self.assertRaises(HTTPError) as raised:
            served.post_json(
                "/api/puzzle/mapping/check",
                {"question_id": 0, "selected_atom_index": 0},
            )
        self.assertEqual(raised.exception.code, 404)

    def test_crystal_composition_routes_hide_then_reveal_the_product(self):
        served = self.served["halite"]
        public = served.get_json("/api/puzzle/composition")
        self.assertEqual(public["source_kind"], "crystal")
        self.assertTrue(public["questions"])
        question = public["questions"][0]
        self.assertNotIn("answers", question)
        self.assertNotIn("product_index", question)

        private = composition_questions(served.render_data)[question["id"]]
        answer = private["answers"][0]
        checked = served.post_json(
            "/api/puzzle/composition/check",
            {"question_id": question["id"], "kind": answer["kind"], "order": answer["order"]},
        )
        self.assertTrue(checked["correct"])
        self.assertEqual(checked["product_index"], private["product_index"])

    def test_published_improper_labels_match_the_fold_they_ask_about(self):
        # The display symbol names the symmetry element, and benzene's principal
        # axis is labelled S6 while also carrying S3.  A question that shows "S6"
        # must never be answered by the image of S3, so every published label has
        # to agree with the fold in the same payload.
        checked_any = False
        for name in ("methane", "benzene"):
            served = self.served[name]
            labelled = [
                question["operation"]
                for question in served.get_json("/api/puzzle/mapping")["questions"]
            ]
            for question in served.get_json("/api/puzzle/composition")["questions"]:
                labelled.extend([question["operation_a"], question["operation_b"]])
            for question in served.get_json("/api/puzzle/operations")["questions"]:
                question_id = question["id"]
                labelled.extend(
                    served.post_json(
                        "/api/puzzle/operations/check",
                        {"question_id": question_id, "kind": "rotation", "order": 2},
                    )["answers"]
                )
            for answer in labelled:
                template = IMPROPER_NOTATION.get(answer["kind"])
                if template is None:
                    continue
                expected = template.format(order=answer["order"])
                with self.subTest(structure=name, notation=answer.get("notation")):
                    self.assertEqual(answer["notation"], expected)
                    self.assertEqual(answer["symbol"], expected)
                checked_any = True
        self.assertTrue(checked_any, "no improper operation was published to check")


if __name__ == "__main__":
    unittest.main()
