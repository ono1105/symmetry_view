from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import _bootstrap  # noqa: F401

import logging
import numpy as np

from crystal_viewer.export_pipeline import (
    DEFAULT_JSON_EXPORT_DIR,
    default_json_output_path,
    export_analysis_to_json,
)
from tools.view_json_pyvista import atom_color
from crystal_viewer.viewer.custom_operation import (
    build_custom_operation_frac,
    check_custom_operation,
    custom_operation_visuals,
)
from crystal_viewer.viewer.browser_ui import HTML
from crystal_viewer.viewer.operation_labels import atom_frac_label, operation_summaries
from crystal_viewer.viewer.pyvista_controller import BrowserControlledViewer

logging.getLogger("pyvista").setLevel(logging.ERROR)
logging.getLogger("vtkmodules").setLevel(logging.ERROR)


def make_handler(
    summaries_ref: list,
    atoms: list[dict],
    render_data: dict,
    shared_state: dict,
    state_lock: threading.Lock,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self.send_bytes(HTML.encode("utf-8"), content_type="text/html; charset=utf-8")
                return
            if path == "/api/operations":
                with state_lock:
                    ready = shared_state.get("summaries_ready", True)
                body = {
                    "operations": summaries_ref[0],
                    "summaries_ready": ready,
                }
                self.send_json(body)
                return
            if path == "/api/atoms":
                body = {
                    "atoms": [
                        {
                            "index": atom["index"],
                            "element": atom["element"],
                            "frac": atom.get("frac"),
                            "frac_label": atom_frac_label(atom),
                            "cart": atom.get("cart"),
                            "asymmetric_index": atom.get("asymmetric_index"),
                            "default_color": atom_color(atom),
                        }
                        for atom in atoms
                    ]
                }
                self.send_json(body)
                return
            if path == "/api/state":
                with state_lock:
                    body = dict(shared_state)
                self.send_json(body)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")

            if path == "/api/check_operation":
                unit_cell = render_data.get("unit_cell")
                if unit_cell is None:
                    self.send_json({"error": "No unit cell in render_data"})
                    return
                lattice = np.asarray(unit_cell["lattice"], dtype=float)
                op_type = str(payload.get("type", ""))
                params = payload.get("params", {})
                tolerance = float(payload.get("tolerance", 0.1))
                result = build_custom_operation_frac(op_type, params, lattice)
                if isinstance(result, str):
                    self.send_json({"error": result})
                    return
                W_frac, t_frac = result
                check_result = check_custom_operation(render_data, W_frac, t_frac, tolerance)
                visuals = custom_operation_visuals(op_type, params, lattice, W_frac, t_frac)
                # include the operation matrix so the browser can request animation
                check_result["W_frac"] = W_frac.tolist()
                check_result["t_frac"] = t_frac.tolist()
                check_result.update(visuals)
                # store result for PyVista highlight
                with state_lock:
                    shared_state["custom_op_result"] = check_result
                self.send_json(check_result)
                return

            if path != "/api/state":
                self.send_error(404)
                return

            allowed = {
                "operation_index",
                "playing",
                "reset",
                "selected_atoms",
                "element_colors",
                "atom_colors",
                "speed",
                "projection_mode",
                "display_mode",
                "active_mode",
                "scope",
                "view_request_id",
                "reset_view_request_id",
                "view_center_request_id",
                "view_center_frac",
                "camera_request_id",
                "camera_direction",
                "camera_angle",
                "gif_request_id",
                "gif_3view_request_id",
                "custom_op_check_id",
                "clear_custom_check",
                "custom_op_animate",
            }
            with state_lock:
                for key, value in payload.items():
                    if key in allowed:
                        shared_state[key] = value
                body = dict(shared_state)
            self.send_json(body)

        def send_json(self, body: dict) -> None:
            self.send_bytes(json.dumps(body).encode("utf-8"), content_type="application/json")

        def send_bytes(self, body: bytes, *, content_type: str) -> None:
            try:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                return

        def log_message(self, *args) -> None:
            return

    return Handler


def open_url(url: str) -> None:
    """Open URL in the default browser.  On WSL, webbrowser.open() often fails
    because there is no Linux browser; use cmd.exe instead to open Windows Edge."""
    import platform
    import subprocess
    if "microsoft" in platform.uname().release.lower():
        try:
            subprocess.run(
                ["cmd.exe", "/c", "start", "", url],
                check=False,
                capture_output=True,
            )
            return
        except FileNotFoundError:
            pass
    webbrowser.open(url)


def start_server(host: str, port: int, handler: type[BaseHTTPRequestHandler]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def operation_exists(operations: list[dict], operation_index: int) -> bool:
    return any(operation["index"] == operation_index for operation in operations)


def resolve_viewer_json_path(
    input_path: Path,
    *,
    json_output: Path | None,
    json_dir: Path,
    tolerance_cart: float,
    indent: int,
) -> Path:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    suffix = input_path.suffix.lower()
    if suffix == ".json":
        if json_output is not None:
            raise ValueError("--json-output can only be used when the input is a CIF file.")
        return input_path

    if suffix == ".cif":
        output_path = (
            json_output
            if json_output is not None
            else default_json_output_path(input_path, json_dir)
        )
        print(f"Analyzing CIF: {input_path}", flush=True)
        output_path = export_analysis_to_json(
            input_path,
            mode="crystal",
            output_path=output_path,
            tolerance_cart=tolerance_cart,
            indent=indent,
        )
        print(f"Wrote JSON: {output_path}", flush=True)
        return output_path

    raise ValueError(f"Unsupported input file type: {input_path.suffix}. Use .json or .cif.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Browser controls + PyVista view for exported symmetry JSON or CIF."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Exported JSON, or a CIF file to analyze and export first.",
    )
    parser.add_argument("--operation", type=int, default=None, help="Initial operation index.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5173)
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Where to write the generated JSON when input_path is a CIF file.",
    )
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=DEFAULT_JSON_EXPORT_DIR,
        help="Directory for generated JSON when input_path is a CIF file and --json-output is not set.",
    )
    parser.add_argument(
        "--tolerance-cart",
        type=float,
        default=1e-2,
        help="Atom mapping tolerance in Angstrom for CIF export.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation for generated CIF exports.",
    )
    parser.add_argument(
        "--expanded",
        action="store_true",
        help="Show quarter-cell periodic display clones. Slower, but useful for boundary checks.",
    )
    args = parser.parse_args()

    json_path = resolve_viewer_json_path(
        args.input_path,
        json_output=args.json_output,
        json_dir=args.json_dir,
        tolerance_cart=args.tolerance_cart,
        indent=args.indent,
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    render_data = payload["render_data"]
    operations = render_data["operations"]
    first_operation = operations[0]["index"] if operations else 0
    initial_operation = args.operation if args.operation is not None and operation_exists(operations, args.operation) else first_operation
    display_mode = "expanded_quarter" if args.expanded else "source"

    state_lock = threading.Lock()
    initial_selected_atoms = [atom["index"] for atom in render_data["atoms"]]
    shared_state = {
        "operation_index": initial_operation,
        "playing": False,
        "reset": False,
        "source_kind": payload.get("source_kind", render_data.get("metadata", {}).get("mode", "crystal")),
        "scope": "displayed",
        "selected_atoms": initial_selected_atoms,
        "element_colors": {},
        "atom_colors": {},
        "speed": 1.0,
        "projection_mode": "perspective",
        "display_mode": display_mode,
        "active_mode": "standard",
        "gif_status": "",
        "gif_request_id": None,
        "gif_3view_request_id": None,
        "view_center_request_id": None,
        "view_center_frac": None,
        "custom_op_check_id": None,
        "custom_op_result": None,
    }
    operation_summary_items, element_context_cache = operation_summaries(
        render_data,
        payload.get("atom_mappings"),
    )
    summaries_ref = [operation_summary_items]
    shared_state["summaries_ready"] = True

    handler = make_handler(
        summaries_ref,
        render_data["atoms"],
        render_data,
        shared_state,
        state_lock,
    )
    server = start_server(args.host, args.port, handler)
    url = f"http://{args.host}:{server.server_port}/"
    print(f"Control panel: {url}")
    if not args.no_browser:
        open_url(url)

    app = BrowserControlledViewer(
        json_path,
        display_mode=display_mode,
        initial_operation=initial_operation,
        scope=shared_state["scope"],
        shared_state=shared_state,
        state_lock=state_lock,
        element_context_cache=element_context_cache,
    )
    app.show()
    server.shutdown()
    server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
