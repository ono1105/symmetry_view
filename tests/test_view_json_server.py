import base64
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from crystal_viewer.json_export import EXPORT_SCHEMA_VERSION
from crystal_viewer.web.browser_ui import HTML
from crystal_viewer.viewer.animation_api import symmetry_elements_response
from crystal_viewer.viewer.display_atoms import display_atom_instances
from tools.view_json_server import (
    atom_motion_api_items,
    atom_render_style_items,
    build_argument_parser,
    cached_export_json_path,
    compose_operation_indices,
    compose_operation_sequence_items,
    example_catalog,
    display_atom_api_items,
    display_unit_cell_api_item,
    export_cell_setting_json_worker,
    find_operation_sequence_for_target,
    gif_bytes_from_data_urls,
    replace_shared_state_for_load,
    resolve_example_path,
    ReusableThreadingHTTPServer,
    update_view_coordinate_state,
)


class BrowserUiAssetsTest(unittest.TestCase):
    def test_server_defaults_to_web_only_and_pyvista_is_opt_in(self):
        parser = build_argument_parser()

        self.assertFalse(parser.parse_args([]).pyvista_enabled)
        self.assertEqual(parser.parse_args([]).port, 0)
        self.assertFalse(parser.parse_args(["--web-only"]).pyvista_enabled)
        self.assertTrue(parser.parse_args(["--with-pyvista"]).pyvista_enabled)

    def test_mode_flag_and_selection_skeleton(self):
        parser = build_argument_parser()
        self.assertIsNone(parser.parse_args([]).mode)
        self.assertEqual(parser.parse_args(["--mode", "puzzle"]).mode, "puzzle")
        self.assertEqual(parser.parse_args(["--mode", "analysis"]).mode, "analysis")
        for marker in (
            'id="mode-select"',
            'id="enter-analysis"',
            'id="enter-puzzle"',
            'id="puzzle-mode"',
            'id="analysis-back"',
            "__INITIAL_APP_MODE__",  # replaced with the mode at serve time
        ):
            self.assertIn(marker, HTML)

    def test_html_references_external_styles_and_scripts(self):
        self.assertIn('href="/static/browser_ui.css"', HTML)
        self.assertIn('src="/static/browser_ui.js"', HTML)
        self.assertIn('src="/static/three_loader.js"', HTML)
        self.assertIn('id="previous-frame"', HTML)
        self.assertIn('id="next-frame"', HTML)
        self.assertIn('id="animation-speed"', HTML)
        self.assertIn('id="pause-at-breakpoints"', HTML)
        self.assertIn('id="show-trajectories"', HTML)
        self.assertIn('id="fixed-atom-filter"', HTML)
        self.assertIn('data-atom-legend', HTML)
        self.assertIn('operation-fixed-filter advanced-only', HTML)
        self.assertNotIn('animation-action-row', HTML)
        self.assertIn('>Stepwise</span>', HTML)
        self.assertNotIn('id="continue-boundary"', HTML)
        self.assertIn('class="inline-checkbox advanced-only"', HTML)
        self.assertLess(HTML.index('id="play-toggle"'), HTML.index('id="reset"'))
        self.assertLess(HTML.index('id="reset"'), HTML.index('id="pause-at-breakpoints"'))
        self.assertNotIn('class="secondary speed-button', HTML)
        self.assertIn('id="save-png"', HTML)
        self.assertIn('id="save-gif"', HTML)
        self.assertNotIn('id="record-webm"', HTML)
        self.assertNotIn('id="export-debug-json"', HTML)
        self.assertNotIn('id="save-gif-3view"', HTML)
        self.assertNotIn('id="btn-load-existing-op"', HTML)
        self.assertNotIn("btn-animate-custom-result", Path("crystal_viewer/web/browser_ui.js").read_text(encoding="utf-8"))
        self.assertIn('id="btn-add-custom-operation"', HTML)
        self.assertIn('id="reset-atom-appearance"', HTML)
        self.assertIn('id="example-select-menu"', HTML)
        self.assertIn('id="cop-operation-menu"', HTML)
        self.assertIn('id="view-panel"', HTML)
        self.assertNotIn("Three.js 3D View", HTML)
        self.assertIn('class="panel advanced-only collapsible-panel selected-operation-panel"', HTML)
        self.assertLess(HTML.index("Create operation"), HTML.index("Operation sequence"))
        self.assertIn('<section class="panel advanced-only" id="custom-panel" hidden>', HTML)
        self.assertIn('id="mode-controls"', HTML)
        self.assertNotIn("__STRUCTURE_KIND_CONFIG__", HTML)
        self.assertNotIn("<style>", HTML)
        self.assertNotIn("<script>", HTML)

    def test_split_assets_exist(self):
        web_dir = Path("crystal_viewer/web")
        for name in (
            "browser_ui.html",
            "browser_ui.css",
            "browser_ui.js",
            "three_loader.js",
            "puzzle.js",
        ):
            with self.subTest(name=name):
                self.assertTrue((web_dir / name).is_file())

    def test_puzzle_body_skeleton_and_module(self):
        self.assertIn('src="/static/puzzle.js"', HTML)
        for marker in (
            'id="puzzle-picker"',
            'id="puzzle-view"',
            'id="puzzle-options"',
            'id="puzzle-check"',
            'id="puzzle-again"',
            'id="puzzle-other"',
            'id="puzzle-result"',
        ):
            self.assertIn(marker, HTML)

    def test_three_view_initializes_instance_colors(self):
        source = Path("crystal_viewer/web/three_view.js").read_text(encoding="utf-8")
        self.assertIn("mesh.setColorAt(instanceIndex, instance.baseColor)", source)
        self.assertIn("mesh.instanceColor.needsUpdate = true", source)

    def test_three_view_refreshes_custom_paths_and_records_through_breakpoints(self):
        source = Path("crystal_viewer/web/three_view.js").read_text(encoding="utf-8")
        self.assertIn("customAnimationChanged || pathOptionsChanged", source)
        self.assertIn("this.state.pause_at_breakpoints && !this.recording", source)
        self.assertIn("updateTrajectoryLines()", source)
        self.assertIn("new THREE.LineSegments(geometry, material)", source)
        self.assertIn("async recordGif()", source)
        self.assertNotIn("recordWebm", source)
        self.assertIn("viewAlongCartesianDirection", source)
        self.assertIn("setCameraCenter", source)
        self.assertIn("setBackgroundMode", source)
        self.assertIn("setLegendVisible", source)

    def test_empty_atom_selection_does_not_hide_operations(self):
        source = Path("crystal_viewer/web/browser_ui.js").read_text(encoding="utf-8")
        self.assertIn('String(state.scope).startsWith("selected")', source)
        self.assertIn("if (!selected.length) return true", source)
        self.assertIn("fixedAtomFilterEnabled = false", source)
        self.assertIn('.operation-fixed-filter").hidden = beginner', source)
        self.assertIn("sendCurrentCustomAnimation(true)", source)


class WebCameraStateTest(unittest.TestCase):
    def test_fractional_camera_inputs_are_converted_by_python(self):
        render_data = {
            "unit_cell": {"lattice": [[2.0, 0.0, 0.0], [0.5, 3.0, 0.0], [0.0, 0.0, 4.0]]},
            "atoms": [{"cart": [0.0, 0.0, 0.0]}],
        }
        state = {"display_mode": "source", "cell_origin_mode": "center"}

        update_view_coordinate_state(render_data, state, {
            "view_center_request_id": 1,
            "view_center_frac": [0.5, 0.5, 0.5],
            "view_direction_request_id": 2,
            "view_direction_frac": [1.0, 0.0, 0.0],
            "view_plane_request_id": 3,
            "view_plane_hkl": [1.0, 0.0, 0.0],
        })

        np.testing.assert_allclose(state["view_center_cart"], [1.25, 1.5, 2.0])
        np.testing.assert_allclose(state["view_direction_cart"], [1.0, 0.0, 0.0])
        self.assertAlmostEqual(np.linalg.norm(state["view_plane_normal_cart"]), 1.0)

    def test_http_server_reuses_address_and_does_not_wait_for_request_threads(self):
        self.assertTrue(ReusableThreadingHTTPServer.allow_reuse_address)
        self.assertTrue(ReusableThreadingHTTPServer.daemon_threads)
        self.assertFalse(ReusableThreadingHTTPServer.block_on_close)

    def test_browser_frames_are_encoded_as_animated_gif(self):
        frames = []
        for color in ((255, 0, 0), (0, 0, 255)):
            buffer = io.BytesIO()
            Image.new("RGB", (2, 2), color).save(buffer, format="PNG")
            frames.append("data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"))

        encoded = gif_bytes_from_data_urls(frames, 80)

        self.assertTrue(encoded.startswith(b"GIF89a"))
        image = Image.open(io.BytesIO(encoded))
        self.assertEqual(image.n_frames, 2)


class AtomRenderStyleItemsTest(unittest.TestCase):
    def test_provides_index_color_and_positive_radius_for_molecule(self):
        render_data = {
            "atoms": [
                {"index": 4, "element": "O", "atomic_number": 8, "cart": [0.0, 0.0, 0.0]},
            ],
            "unit_cell": None,
        }

        result = atom_render_style_items(render_data)

        self.assertEqual(result[0]["index"], 4)
        self.assertRegex(result[0]["color"], r"^#[0-9a-f]{6}$")
        self.assertGreater(result[0]["radius"], 0.0)

    def test_applies_browser_color_overrides(self):
        render_data = {
            "atoms": [
                {"index": 4, "element": "O", "atomic_number": 8, "cart": [0.0, 0.0, 0.0]},
            ],
            "unit_cell": None,
        }

        result = atom_render_style_items(render_data, atom_colors={"4": "#123456"})

        self.assertEqual(result[0]["color"], "#123456")

    def test_scales_crystal_radius_against_shortest_lattice_vector(self):
        render_data = {
            "atoms": [
                {"index": 0, "element": "Cs", "atomic_number": 55, "cart": [0.0, 0.0, 0.0]},
            ],
            "unit_cell": {
                "lattice": [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0]],
            },
        }

        result = atom_render_style_items(render_data)

        self.assertLessEqual(result[0]["radius"], 0.24 + 1e-12)


class DisplayRenderApiItemsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        cls.render_data = cls.payload["render_data"]

    def test_centered_display_atoms_use_centered_periodic_images(self):
        items = display_atom_api_items(
            self.render_data,
            display_mode="source",
            cell_origin_mode="center",
        )

        self.assertEqual(len(items), 8)
        for item in items:
            self.assertTrue(all(-2.81 - 1e-8 <= value < 2.81 + 1e-8 for value in item["cart"]))

    def test_boundary_atom_option_adds_opposite_cell_faces(self):
        regular = display_atom_api_items(
            self.render_data,
            display_mode="source",
            cell_origin_mode="center",
        )
        with_boundaries = display_atom_api_items(
            self.render_data,
            display_mode="source",
            cell_origin_mode="center",
            include_boundary_images=True,
        )

        self.assertEqual(len(regular), 8)
        self.assertEqual(len(with_boundaries), 27)
        self.assertEqual(sum(bool(item["is_primary_image"]) for item in with_boundaries), 8)

    def test_hidden_atoms_are_omitted(self):
        items = display_atom_api_items(
            self.render_data,
            display_mode="source",
            cell_origin_mode="center",
            atom_hidden={"0": True},
        )

        self.assertNotIn(0, {item["source_atom"] for item in items})

    def test_all_cell_ranges_match_shared_pyvista_display_instances(self):
        expected_counts = {
            "source": 8,
            "expanded_quarter": 27,
            "expanded_half": 64,
            "expanded_0_75": 125,
            "expanded_1_0": 216,
        }
        for origin in ("center", "corner"):
            for mode, expected_count in expected_counts.items():
                with self.subTest(origin=origin, mode=mode):
                    api_items = display_atom_api_items(
                        self.render_data,
                        display_mode=mode,
                        cell_origin_mode=origin,
                    )
                    pyvista_items = display_atom_instances(
                        self.render_data,
                        display_mode=mode,
                        cell_origin_mode=origin,
                    )
                    self.assertEqual(len(api_items), expected_count)
                    self.assertEqual(len(pyvista_items), expected_count)
                    np_api = sorted(tuple(round(value, 10) for value in item["cart"]) for item in api_items)
                    np_pyvista = sorted(
                        tuple(round(float(value), 10) for value in item["cart"])
                        for item in pyvista_items
                    )
                    self.assertEqual(np_api, np_pyvista)

    def test_centered_display_unit_cell_matches_pyvista_bounds(self):
        cell = display_unit_cell_api_item(
            self.render_data,
            display_mode="source",
            cell_origin_mode="center",
        )

        coordinates = [value for vertex in cell["vertices_cart"] for value in vertex]
        self.assertAlmostEqual(min(coordinates), -2.81)
        self.assertAlmostEqual(max(coordinates), 2.81)

    def test_display_unit_cell_does_not_follow_cell_range(self):
        source_cell = display_unit_cell_api_item(
            self.render_data,
            display_mode="source",
            cell_origin_mode="center",
        )

        for mode in ("expanded_quarter", "expanded_half", "expanded_0_75", "expanded_1_0"):
            with self.subTest(mode=mode):
                expanded_cell = display_unit_cell_api_item(
                    self.render_data,
                    display_mode=mode,
                    cell_origin_mode="center",
                )
                expanded_vertices = [
                    tuple(round(float(value), 10) for value in vertex)
                    for vertex in expanded_cell["vertices_cart"]
                ]
                source_vertices = [
                    tuple(round(float(value), 10) for value in vertex)
                    for vertex in source_cell["vertices_cart"]
                ]
                self.assertEqual(expanded_vertices, source_vertices)
                self.assertEqual(expanded_cell["edges"], source_cell["edges"])

    def test_op77_and_op88_elements_are_inside_centered_display_cell(self):
        cell = display_unit_cell_api_item(
            self.render_data,
            display_mode="source",
            cell_origin_mode="center",
        )
        vertices = cell["vertices_cart"]
        lower = [min(vertex[axis] for vertex in vertices) for axis in range(3)]
        upper = [max(vertex[axis] for vertex in vertices) for axis in range(3)]

        for operation_index in (77, 88):
            with self.subTest(operation_index=operation_index):
                elements = symmetry_elements_response(
                    self.render_data,
                    self.payload["atom_mappings"],
                    operation_index,
                    display_mode="source",
                    cell_origin_mode="center",
                )
                points = [
                    element["point_cart"]
                    for key in ("axes", "centers")
                    for element in elements[key]
                ]
                self.assertTrue(points)
                for point in points:
                    self.assertTrue(
                        all(lower[axis] - 1e-8 <= point[axis] <= upper[axis] + 1e-8 for axis in range(3))
                    )


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
                    "stages": [],
                }
            ],
        )

    def test_includes_compound_operation_stage_coordinates(self):
        render_data = {
            "atoms": [{"index": 0, "frac": [1.0, 0.0, 0.0], "cart": [1.0, 0.0, 0.0]}],
            "unit_cell": {"lattice": np.eye(3).tolist()},
        }
        mappings = {
            "mappings": [{
                "operation_index": 4,
                "entries": [{
                    "source_atom": 0,
                    "target_atom": 0,
                    "transformed_cart": [0.0, 1.0, 2.0],
                    "transformed_frac": [0.0, 1.0, 2.0],
                }],
            }],
        }
        path = {
            "type": "screw",
            "start": np.array([1.0, 0.0, 0.0]),
            "target": np.array([0.0, 1.0, 2.0]),
            "axis_point": np.zeros(3),
            "axis_direction": np.array([0.0, 0.0, 1.0]),
            "angle": np.pi / 2,
            "translation": np.array([0.0, 0.0, 2.0]),
            "phase_fraction": 0.75,
        }

        result = atom_motion_api_items(
            render_data,
            mappings,
            4,
            paths={0: path},
        )

        self.assertAlmostEqual(result[0]["stages"][0]["progress"], 0.75)
        np.testing.assert_allclose(result[0]["stages"][0]["cart"], [0.0, 1.0, 0.0], atol=1e-8)
        np.testing.assert_allclose(result[0]["stages"][0]["frac"], [0.0, 1.0, 0.0], atol=1e-8)

    def test_returns_empty_list_without_mapping(self):
        self.assertEqual(atom_motion_api_items({"atoms": []}, None, 1), [])


class LoadedStateReplacementTest(unittest.TestCase):
    def test_preserves_nonzero_load_request_id_for_async_summary_worker(self):
        shared_state = {"load_request_id": 12, "old": True}
        next_state = {"summaries_ready": False}

        replace_shared_state_for_load(shared_state, next_state, request_id=42)

        self.assertEqual(
            shared_state,
            {"summaries_ready": False, "load_request_id": 42},
        )


class ComposeOperationIndicesTest(unittest.TestCase):
    def test_composes_in_application_order_and_finds_matching_operation(self):
        c4 = [
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 1],
        ]
        render_data = {
            "unit_cell": {"lattice": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
            "atoms": [],
            "operations": [
                {"index": 0, "matrix_frac": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "translation_frac": [0, 0, 0]},
                {"index": 1, "matrix_frac": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "translation_frac": [0.25, 0, 0]},
                {"index": 2, "matrix_frac": c4, "translation_frac": [0, 0, 0]},
                {"index": 3, "matrix_frac": c4, "translation_frac": [0, 0.25, 0]},
            ],
        }

        result = compose_operation_indices(render_data, [1, 2], 0.01)

        self.assertTrue(result["is_symmetry"])
        self.assertEqual(result["matching_operation_index"], 3)
        self.assertEqual(result["operation_indices"], [1, 2])
        self.assertEqual(result["W_frac"], c4)
        self.assertEqual(result["t_frac"], [0.0, 0.25, 0.0])
        self.assertEqual(result["matrix_cart"], c4)
        self.assertEqual(result["translation_cart"], [0.0, 0.25, 0.0])


class FindOperationSequenceForTargetTest(unittest.TestCase):
    def test_finds_sequence_from_generators(self):
        c4 = [
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 1],
        ]
        c2 = [
            [-1, 0, 0],
            [0, -1, 0],
            [0, 0, 1],
        ]
        render_data = {
            "operations": [
                {"index": 0, "matrix_frac": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "translation_frac": [0, 0, 0]},
                {"index": 1, "matrix_frac": c4, "translation_frac": [0, 0, 0]},
                {"index": 2, "matrix_frac": c2, "translation_frac": [0, 0, 0]},
            ],
        }

        result = find_operation_sequence_for_target(render_data, 2, [1], 3)

        self.assertEqual(result["sequence"], [1, 1])
        self.assertTrue(result["found"])

    def test_reports_not_found_with_depth_limit(self):
        c4 = [
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 1],
        ]
        c2 = [
            [-1, 0, 0],
            [0, -1, 0],
            [0, 0, 1],
        ]
        render_data = {
            "operations": [
                {"index": 1, "matrix_frac": c4, "translation_frac": [0, 0, 0]},
                {"index": 2, "matrix_frac": c2, "translation_frac": [0, 0, 0]},
            ],
        }

        result = find_operation_sequence_for_target(render_data, 2, [1], 1)

        self.assertIsNone(result["sequence"])
        self.assertFalse(result["found"])

    def test_returns_error_for_missing_operation_index(self):
        render_data = {
            "unit_cell": {"lattice": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
            "atoms": [],
            "operations": [],
        }

        result = compose_operation_indices(render_data, [99], 0.01)

        self.assertEqual(result, {"error": "Operation index not found: 99"})

    def test_composes_real_halite_operations(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))

        result = compose_operation_indices(payload["render_data"], [1, 2], 1e-2)

        self.assertTrue(result["is_symmetry"])
        self.assertEqual(result["matching_operation_index"], 3)

    def test_composes_existing_and_custom_sequence_items(self):
        c4 = [
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 1],
        ]
        render_data = {
            "unit_cell": {"lattice": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
            "atoms": [],
            "operations": [
                {"index": 0, "matrix_frac": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "translation_frac": [0, 0, 0]},
                {"index": 2, "matrix_frac": c4, "translation_frac": [0, 0, 0]},
                {"index": 3, "matrix_frac": c4, "translation_frac": [0, 0.25, 0]},
            ],
        }

        result = compose_operation_sequence_items(
            render_data,
            [
                {"type": "custom", "label": "custom translation", "W_frac": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "t_frac": [0.25, 0, 0]},
                {"type": "operation", "index": 2},
            ],
            0.01,
        )

        self.assertTrue(result["is_symmetry"])
        self.assertEqual(result["matching_operation_index"], 3)
        self.assertEqual(result["sequence_labels"], ["custom translation", "op 2"])
        self.assertEqual(result["t_frac"], [0.0, 0.25, 0.0])


class CachedExportJsonPathTest(unittest.TestCase):
    def test_accepts_current_matching_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, output_path = self.write_cached_export(tmp, schema_version=EXPORT_SCHEMA_VERSION)

            cached = cached_export_json_path(input_path, output_path, mode="crystal")

            self.assertIsNotNone(cached)
            self.assertEqual(cached[0], output_path)

    def test_rejects_stale_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, output_path = self.write_cached_export(tmp, schema_version=EXPORT_SCHEMA_VERSION)
            os.utime(output_path, (input_path.stat().st_atime - 10, input_path.stat().st_mtime - 10))

            self.assertIsNone(cached_export_json_path(input_path, output_path, mode="crystal"))

    def test_rejects_old_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, output_path = self.write_cached_export(tmp, schema_version=EXPORT_SCHEMA_VERSION - 1)

            self.assertIsNone(cached_export_json_path(input_path, output_path, mode="crystal"))

    def test_rejects_source_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, output_path = self.write_cached_export(
                tmp,
                schema_version=EXPORT_SCHEMA_VERSION,
                source_file="/tmp/different.cif",
            )

            self.assertIsNone(cached_export_json_path(input_path, output_path, mode="crystal"))

    def write_cached_export(
        self,
        tmp: str,
        *,
        schema_version: int,
        source_file: str | None = None,
    ) -> tuple[Path, Path]:
        directory = Path(tmp)
        input_path = directory / "source.cif"
        output_path = directory / "source.json"
        input_path.write_text("data_source\n", encoding="utf-8")
        payload = {
            "schema_version": schema_version,
            "source_kind": "crystal",
            "render_data": {
                "metadata": {
                    "mode": "crystal",
                    "source_file": source_file or str(input_path),
                }
            },
            "atom_mappings": {"mappings": []},
        }
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        output_mtime = input_path.stat().st_mtime + 10
        os.utime(output_path, (output_mtime, output_mtime))
        return input_path, output_path


class CellSettingWorkerTest(unittest.TestCase):
    def test_worker_converts_batio3_to_conventional_cell(self):
        payload = json.loads(Path("exports/json/batio3.json").read_text(encoding="utf-8"))

        converted = export_cell_setting_json_worker(
            payload,
            cell_setting="conventional",
            tolerance_cart=1e-2,
            indent=2,
            timeout_sec=30,
            require_distinct=True,
        )

        render_data = converted["render_data"]
        self.assertEqual(render_data["metadata"]["display_cell_setting"], "conventional")
        self.assertEqual(len(render_data["atoms"]), 15)
        self.assertTrue(converted["atom_mappings"]["complete"])

    def test_worker_can_require_distinct_primitive_cell(self):
        payload = json.loads(Path("exports/json/agcl.json").read_text(encoding="utf-8"))

        with self.assertRaises(RuntimeError):
            export_cell_setting_json_worker(
                payload,
                cell_setting="primitive",
                tolerance_cart=1e-2,
                indent=2,
                timeout_sec=30,
                require_distinct=True,
            )

    def test_worker_can_require_distinct_bravais_cell(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))

        with self.assertRaises(RuntimeError):
            export_cell_setting_json_worker(
                payload,
                cell_setting="conventional",
                tolerance_cart=1e-2,
                indent=2,
                timeout_sec=30,
                require_distinct=True,
            )

    def test_worker_can_round_trip_halite_primitive_to_bravais(self):
        payload = json.loads(Path("exports/json/halite.json").read_text(encoding="utf-8"))
        primitive = export_cell_setting_json_worker(
            payload,
            cell_setting="primitive",
            tolerance_cart=1e-2,
            indent=2,
            timeout_sec=30,
            require_distinct=True,
        )

        bravais = export_cell_setting_json_worker(
            primitive,
            cell_setting="conventional",
            tolerance_cart=1e-2,
            indent=2,
            timeout_sec=30,
            require_distinct=True,
        )

        self.assertEqual(bravais["render_data"]["metadata"]["display_cell_setting"], "conventional")
        self.assertEqual(len(bravais["render_data"]["atoms"]), 8)

    def test_worker_can_round_trip_batio3_bravais_to_primitive(self):
        payload = json.loads(Path("exports/json/batio3.json").read_text(encoding="utf-8"))
        bravais = export_cell_setting_json_worker(
            payload,
            cell_setting="conventional",
            tolerance_cart=1e-2,
            indent=2,
            timeout_sec=30,
            require_distinct=True,
        )

        primitive = export_cell_setting_json_worker(
            bravais,
            cell_setting="primitive",
            tolerance_cart=1e-2,
            indent=2,
            timeout_sec=30,
            require_distinct=True,
        )

        self.assertEqual(primitive["render_data"]["metadata"]["display_cell_setting"], "primitive")
        self.assertEqual(len(primitive["render_data"]["atoms"]), 5)


class ExampleCatalogAndPathTest(unittest.TestCase):
    def test_example_catalog_uses_canonical_directories(self):
        catalog = example_catalog()

        self.assertEqual(len(catalog["crystal"]), 32)
        self.assertEqual(len(catalog["molecule"]), 11)
        self.assertTrue(
            all(item["path"].startswith("examples/cif/") for item in catalog["crystal"])
        )
        self.assertTrue(
            all(item["path"].startswith("examples/molecules/") for item in catalog["molecule"])
        )

    def test_resolve_example_path_accepts_catalog_crystal(self):
        path = resolve_example_path("crystal", "examples/cif/Halite.cif")

        self.assertEqual(path.name, "Halite.cif")

    def test_resolve_example_path_rejects_noncanonical_directory(self):
        with self.assertRaises(ValueError):
            resolve_example_path("crystal", "examples/molecules/water.xyz")

    def test_resolve_example_path_rejects_parent_escape(self):
        with self.assertRaises(ValueError):
            resolve_example_path("crystal", "examples/cif/../molecules/water.xyz")


if __name__ == "__main__":
    unittest.main()
