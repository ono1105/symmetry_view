from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import tempfile
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

try:
    import _bootstrap  # noqa: F401
except ModuleNotFoundError:
    from tools import _bootstrap  # noqa: F401

import logging
import numpy as np

from crystal_viewer.export_pipeline import (
    DEFAULT_JSON_EXPORT_DIR,
    default_json_output_path,
    export_analysis_to_json,
    slug_from_path,
)
from crystal_viewer.source_kinds import (
    SOURCE_KIND_CRYSTAL,
    SOURCE_KIND_EMPTY,
    SOURCE_KIND_MOLECULE,
    normalize_source_kind,
)
from crystal_viewer.viewer.atom_style import atom_color
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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_CIF_DIR = Path(tempfile.gettempdir()) / "symmetry_view_cif_uploads"
UPLOAD_MOLECULE_DIR = Path(tempfile.gettempdir()) / "symmetry_view_molecule_uploads"
DEFAULT_BROWSER_IMPORT_JSON_DIR = DEFAULT_JSON_EXPORT_DIR / "imported"
EXAMPLE_DIRS = {
    SOURCE_KIND_CRYSTAL: PROJECT_ROOT / "examples/structures",
    SOURCE_KIND_MOLECULE: PROJECT_ROOT / "examples/molecules",
}
EXAMPLE_SUFFIXES = {
    SOURCE_KIND_CRYSTAL: ".cif",
    SOURCE_KIND_MOLECULE: ".xyz",
}
EXAMPLE_CATALOG_PATH = PROJECT_ROOT / "examples/example_catalog.json"
DEFAULT_STARTER_PATHS = (
    Path("exports/json/halite.json"),
    Path("exports/json/f2_pd.json"),
    Path("exports/json/jacobsite.json"),
)
EMPTY_VIEWER_JSON_PATH = Path(tempfile.gettempdir()) / "symmetry_view_empty.json"
DEBUG_IMPORT_TIMING = os.environ.get("CRYSTAL_VIEWER_DEBUG_IMPORT") == "1"
_EXAMPLE_CATALOG_CACHE: dict[str, list[dict]] | None = None


def debug_import_timing(label: str, start: float) -> None:
    if DEBUG_IMPORT_TIMING:
        print(f"[import] {label} {time.monotonic() - start:.3f}s", flush=True)


class ViewerSession:
    def __init__(self, json_path: Path, payload: dict) -> None:
        self.load(json_path, payload)

    def load(self, json_path: Path, payload: dict) -> None:
        self.json_path = json_path
        self.payload = payload
        self.render_data = payload["render_data"]
        self.atoms = self.render_data["atoms"]
        self.operations = self.render_data["operations"]
        self.operation_summary_items, self.element_context_cache = operation_summaries(
            self.render_data,
            payload.get("atom_mappings"),
        )

    def replace_from(self, other: "ViewerSession") -> None:
        self.json_path = other.json_path
        self.payload = other.payload
        self.render_data = other.render_data
        self.atoms = other.atoms
        self.operations = other.operations
        self.operation_summary_items = other.operation_summary_items
        self.element_context_cache = other.element_context_cache

    @property
    def source_kind(self) -> str:
        return normalize_source_kind(
            self.payload.get(
                "source_kind",
                self.render_data.get("metadata", {}).get("mode", SOURCE_KIND_CRYSTAL),
            )
        )


def initial_state_for_payload(
    payload: dict,
    *,
    initial_operation: int | None,
    display_mode: str,
    preserved: dict | None = None,
) -> dict:
    preserved = preserved or {}
    render_data = payload["render_data"]
    operations = render_data["operations"]
    first_operation = operations[0]["index"] if operations else 0
    selected_operation = (
        initial_operation
        if initial_operation is not None and operation_exists(operations, initial_operation)
        else first_operation
    )
    selected_atoms = [atom["index"] for atom in render_data["atoms"]]
    return {
        "operation_index": selected_operation,
        "playing": False,
        "reset": True,
        "source_kind": normalize_source_kind(
            payload.get(
                "source_kind",
                render_data.get("metadata", {}).get("mode", SOURCE_KIND_CRYSTAL),
            )
        ),
        "structure_loaded": bool(payload.get("structure_loaded", True)),
        "metadata": render_data.get("metadata", {}),
        "scope": "displayed",
        "selected_atoms": selected_atoms,
        "element_colors": {},
        "atom_colors": {},
        "speed": float(preserved.get("speed", 1.0)),
        "projection_mode": preserved.get("projection_mode", "perspective"),
        "improper_mode": preserved.get("improper_mode", "auto"),
        "display_mode": preserved.get("display_mode", display_mode),
        "active_mode": "standard",
        "gif_status": "",
        "gif_request_id": None,
        "gif_3view_request_id": None,
        "view_request_id": None,
        "reset_view_request_id": None,
        "view_center_request_id": None,
        "view_center_frac": None,
        "camera_request_id": None,
        "camera_direction": "",
        "camera_angle": 90.0,
        "custom_op_check_id": None,
        "custom_op_result": None,
        "custom_op_animate": None,
        "reload_request_id": preserved.get("reload_request_id"),
        "import_status": preserved.get("import_status", ""),
        "import_in_progress": False,
        "json_path": str(preserved.get("json_path", "")),
        "summaries_ready": True,
    }


def empty_viewer_payload() -> dict:
    return {
        "schema_version": 4,
        "source_kind": SOURCE_KIND_EMPTY,
        "structure_loaded": False,
        "render_data": {
            "metadata": {
                "mode": SOURCE_KIND_EMPTY,
                "source_file": "",
                "formula": "No structure",
                "symmetry_label": "",
                "operation_count": 1,
            },
            "atoms": [],
            "asymmetric_atoms": [],
            "operations": [
                {
                    "index": 0,
                    "label": "0: load a structure",
                    "kind": "identity",
                    "order": 1,
                    "angle_deg": 0.0,
                    "symbol": "load",
                    "matrix_frac": None,
                    "translation_frac": None,
                    "matrix_cart": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                    "translation_cart": [0.0, 0.0, 0.0],
                }
            ],
            "axes": [],
            "planes": [],
            "centers": [],
            "unit_cell": None,
            "bounds_min": [0.0, 0.0, 0.0],
            "bounds_max": [1.0, 1.0, 1.0],
        },
        "atom_mappings": {
            "mode": SOURCE_KIND_EMPTY,
            "complete": True,
            "incomplete_operation_indices": [],
            "mappings": [
                {
                    "mode": SOURCE_KIND_EMPTY,
                    "operation_index": 0,
                    "operation_kind": "identity",
                    "complete": True,
                    "atom_to_atom": [],
                    "max_distance": 0.0,
                    "unmatched_atoms": [],
                    "entries": [],
                }
            ],
        },
    }


def write_empty_viewer_json() -> Path:
    EMPTY_VIEWER_JSON_PATH.write_text(json.dumps(empty_viewer_payload(), indent=2), encoding="utf-8")
    return EMPTY_VIEWER_JSON_PATH


def atom_api_items(atoms: list[dict]) -> list[dict]:
    return [
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


def example_catalog() -> dict[str, list[dict]]:
    global _EXAMPLE_CATALOG_CACHE
    if _EXAMPLE_CATALOG_CACHE is not None:
        return _EXAMPLE_CATALOG_CACHE
    if EXAMPLE_CATALOG_PATH.exists():
        loaded = json.loads(EXAMPLE_CATALOG_PATH.read_text(encoding="utf-8"))
        _EXAMPLE_CATALOG_CACHE = normalize_example_catalog(loaded)
    else:
        _EXAMPLE_CATALOG_CACHE = filesystem_example_catalog()
    return _EXAMPLE_CATALOG_CACHE


def normalize_example_catalog(loaded: dict) -> dict[str, list[dict]]:
    catalog = {SOURCE_KIND_CRYSTAL: [], SOURCE_KIND_MOLECULE: []}
    for kind in (SOURCE_KIND_CRYSTAL, SOURCE_KIND_MOLECULE):
        for raw in loaded.get(kind, []):
            path = str(raw.get("path") or "")
            if not path:
                continue
            item = {
                "kind": kind,
                "name": str(raw.get("name") or Path(path).stem),
                "path": path,
                "formula": str(raw.get("formula") or ""),
                "symmetry": str(raw.get("symmetry") or ""),
            }
            if raw.get("error"):
                item["error"] = str(raw["error"])
            catalog[kind].append(item)
    return catalog


def filesystem_example_catalog() -> dict[str, list[dict]]:
    return {
        SOURCE_KIND_CRYSTAL: filesystem_example_items(SOURCE_KIND_CRYSTAL),
        SOURCE_KIND_MOLECULE: filesystem_example_items(SOURCE_KIND_MOLECULE),
    }


def filesystem_example_items(kind: str) -> list[dict]:
    directory = EXAMPLE_DIRS[kind]
    suffix = EXAMPLE_SUFFIXES[kind]
    items: list[dict] = []
    for path in sorted(directory.glob(f"*{suffix}")):
        items.append({
            "kind": kind,
            "name": path.stem,
            "path": str(path),
            "formula": "",
            "symmetry": "",
        })
    return items


def resolve_example_path(kind: str, requested_path: str) -> Path:
    kind = normalize_source_kind(kind)
    if kind not in EXAMPLE_DIRS:
        raise ValueError(f"unsupported example kind: {kind}")
    base = EXAMPLE_DIRS[kind].resolve()
    path = Path(requested_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if path.suffix.lower() != EXAMPLE_SUFFIXES[kind]:
        raise ValueError(f"example must be a {EXAMPLE_SUFFIXES[kind]} file")
    if path.parent != base:
        raise ValueError("example path is outside the allowed examples directory")
    if not path.exists():
        raise FileNotFoundError(f"example not found: {requested_path}")
    return path


def write_uploaded_text(filename: str, content: str, *, upload_dir: Path, suffix: str, label: str) -> Path:
    if not content.strip():
        raise ValueError(f"{label} content is empty.")
    if len(content.encode("utf-8")) > 20 * 1024 * 1024:
        raise ValueError(f"{label} upload is too large.")
    slug = slug_from_path(filename or "uploaded_structure")
    path = upload_dir / f"{slug}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_uploaded_cif(filename: str, content: str) -> Path:
    return write_uploaded_text(filename, content, upload_dir=UPLOAD_CIF_DIR, suffix=".cif", label="CIF")


def write_uploaded_molecule(filename: str, content: str) -> Path:
    return write_uploaded_text(filename, content, upload_dir=UPLOAD_MOLECULE_DIR, suffix=".xyz", label="Molecule")


def make_handler(
    session: ViewerSession,
    shared_state: dict,
    state_lock: threading.Lock,
    *,
    json_dir: Path,
    import_json_dir: Path,
    tolerance_cart: float,
    indent: int,
    default_display_mode: str,
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
                    operations = session.operation_summary_items
                body = {
                    "operations": operations,
                    "summaries_ready": ready,
                }
                self.send_json(body)
                return
            if path == "/api/atoms":
                with state_lock:
                    atoms = list(session.atoms)
                body = {"atoms": atom_api_items(atoms)}
                self.send_json(body)
                return
            if path == "/api/state":
                with state_lock:
                    body = dict(shared_state)
                self.send_json(body)
                return
            if path == "/api/examples":
                self.send_json(example_catalog())
                return
            self.send_error(404)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")

            if path == "/api/check_operation":
                with state_lock:
                    render_data = session.render_data
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

            if path == "/api/import_cif":
                self.handle_import_cif(payload)
                return

            if path == "/api/import_molecule":
                self.handle_import_molecule(payload)
                return

            if path == "/api/open_example":
                self.handle_open_example(payload)
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
                "improper_mode",
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
                "reload_request_id",
                "import_status",
            }
            with state_lock:
                for key, value in payload.items():
                    if key in allowed:
                        shared_state[key] = value
                body = dict(shared_state)
            self.send_json(body)

        def handle_open_example(self, payload: dict) -> None:
            started_at = time.monotonic()
            request_id = self.reserve_load_request(payload)
            kind = normalize_source_kind(str(payload.get("kind") or ""))
            requested_path = str(payload.get("path") or "")
            try:
                input_path = resolve_example_path(kind, requested_path)
                json_path = default_json_output_path(input_path, DEFAULT_JSON_EXPORT_DIR)
                json_path = export_analysis_to_json_worker_cached(
                    input_path,
                    mode=kind,
                    output_path=json_path,
                    tolerance_cart=tolerance_cart,
                    indent=indent,
                )
                debug_import_timing("example export/cache", started_at)
                new_payload = json.loads(json_path.read_text(encoding="utf-8"))
                debug_import_timing("example read-json", started_at)
                self.load_payload(json_path, new_payload, f"loaded example {input_path.name}", request_id=request_id)
                debug_import_timing("example response", started_at)
            except Exception as exc:
                with state_lock:
                    self.clear_import_if_current(request_id)
                    shared_state["import_status"] = f"example load failed: {exc}"
                    body = {"ok": False, "error": str(exc), "state": dict(shared_state)}
                self.send_json(body)

        def reserve_load_request(self, payload: dict) -> int:
            request_id = int(payload.get("request_id") or 0)
            with state_lock:
                shared_state["load_request_id"] = max(
                    int(shared_state.get("load_request_id") or 0),
                    request_id,
                )
                shared_state["import_in_progress"] = True
            return request_id

        def load_request_is_current(self, request_id: int) -> bool:
            return request_id == 0 or request_id == int(shared_state.get("load_request_id") or 0)

        def clear_import_if_current(self, request_id: int) -> None:
            if self.load_request_is_current(request_id):
                shared_state["import_in_progress"] = False

        def handle_import_cif(self, payload: dict) -> None:
            started_at = time.monotonic()
            request_id = self.reserve_load_request(payload)
            filename = str(payload.get("filename") or "uploaded_structure.cif")
            content = str(payload.get("content") or "")
            try:
                cif_path = write_uploaded_cif(filename, content)
                debug_import_timing("cif write", started_at)
                json_path = default_json_output_path(cif_path, import_json_dir)
                json_path = export_analysis_to_json_worker(
                    cif_path,
                    mode=SOURCE_KIND_CRYSTAL,
                    output_path=json_path,
                    tolerance_cart=tolerance_cart,
                    indent=indent,
                )
                debug_import_timing("cif export", started_at)
                new_payload = json.loads(json_path.read_text(encoding="utf-8"))
                debug_import_timing("cif read-json", started_at)
                self.load_payload(json_path, new_payload, f"loaded {filename} -> {json_path}", request_id=request_id)
                debug_import_timing("cif response", started_at)
            except Exception as exc:
                with state_lock:
                    self.clear_import_if_current(request_id)
                    shared_state["import_status"] = f"import failed: {exc}"
                    body = {"ok": False, "error": str(exc), "state": dict(shared_state)}
                self.send_json(body)

        def handle_import_molecule(self, payload: dict) -> None:
            started_at = time.monotonic()
            request_id = self.reserve_load_request(payload)
            filename = str(payload.get("filename") or "uploaded_molecule.xyz")
            content = str(payload.get("content") or "")
            try:
                molecule_path = write_uploaded_molecule(filename, content)
                debug_import_timing("molecule write", started_at)
                json_path = default_json_output_path(molecule_path, import_json_dir)
                json_path = export_analysis_to_json_worker(
                    molecule_path,
                    mode=SOURCE_KIND_MOLECULE,
                    output_path=json_path,
                    tolerance_cart=tolerance_cart,
                    indent=indent,
                )
                debug_import_timing("molecule export", started_at)
                new_payload = json.loads(json_path.read_text(encoding="utf-8"))
                debug_import_timing("molecule read-json", started_at)
                self.load_payload(json_path, new_payload, f"loaded {filename} -> {json_path}", request_id=request_id)
                debug_import_timing("molecule response", started_at)
            except Exception as exc:
                with state_lock:
                    self.clear_import_if_current(request_id)
                    shared_state["import_status"] = f"molecule import failed: {exc}"
                    body = {"ok": False, "error": str(exc), "state": dict(shared_state)}
                self.send_json(body)

        def load_payload(
            self,
            json_path: Path,
            new_payload: dict,
            import_status: str,
            *,
            request_id: int = 0,
        ) -> None:
            started_at = time.monotonic()
            new_session = ViewerSession(json_path, new_payload)
            debug_import_timing("session summaries", started_at)
            with state_lock:
                if not self.load_request_is_current(request_id):
                    body = {"ok": False, "stale": True, "state": dict(shared_state)}
                    self.send_json(body)
                    return
                preserved = {
                    "speed": shared_state.get("speed", 1.0),
                    "projection_mode": shared_state.get("projection_mode", "perspective"),
                    "improper_mode": shared_state.get("improper_mode", "auto"),
                    "display_mode": shared_state.get("display_mode", default_display_mode),
                    "reload_request_id": shared_state.get("reload_request_id"),
                }
                session.replace_from(new_session)
                next_state = initial_state_for_payload(
                    new_payload,
                    initial_operation=None,
                    display_mode=default_display_mode,
                    preserved=preserved,
                )
                next_state["reload_request_id"] = int(shared_state.get("reload_request_id") or 0) + 1
                next_state["structure_loaded"] = True
                next_state["import_in_progress"] = False
                next_state["import_status"] = import_status
                next_state["json_path"] = str(json_path)
                shared_state.clear()
                shared_state.update(next_state)
                body = {
                    "ok": True,
                    "json_path": str(json_path),
                    "operations": session.operation_summary_items,
                    "atoms": atom_api_items(session.atoms),
                    "state": dict(shared_state),
                }
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


def export_analysis_to_json_worker(
    input_path: Path,
    *,
    mode: str,
    output_path: Path,
    tolerance_cart: float,
    indent: int,
) -> Path:
    command = [
        sys.executable,
        str(Path(__file__).with_name("export_analysis_json.py")),
        str(input_path),
        "--mode",
        mode,
        "--output",
        str(output_path),
        "--tolerance-cart",
        str(tolerance_cart),
        "--indent",
        str(indent),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(message or f"export worker failed with exit code {result.returncode}")
    return output_path


def cached_export_json_path(
    input_path: Path,
    output_path: Path,
    *,
    mode: str,
) -> Path | None:
    if not output_path.exists():
        return None
    try:
        if output_path.stat().st_mtime < input_path.stat().st_mtime:
            return None
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    render_data = payload.get("render_data") or {}
    metadata = render_data.get("metadata") or {}
    source_kind = normalize_source_kind(
        payload.get("source_kind", metadata.get("mode", ""))
    )
    if source_kind != mode:
        return None
    if not cached_source_matches(metadata.get("source_file"), input_path):
        return None
    return output_path


def cached_source_matches(cached_source: object, input_path: Path) -> bool:
    if not cached_source:
        return False
    cached_path = Path(str(cached_source))
    if not cached_path.is_absolute():
        cached_path = PROJECT_ROOT / cached_path
    try:
        return cached_path.resolve() == input_path.resolve()
    except OSError:
        return str(cached_source) == str(input_path)


def export_analysis_to_json_worker_cached(
    input_path: Path,
    *,
    mode: str,
    output_path: Path,
    tolerance_cart: float,
    indent: int,
) -> Path:
    cached = cached_export_json_path(input_path, output_path, mode=mode)
    if cached is not None:
        return cached
    return export_analysis_to_json_worker(
        input_path,
        mode=mode,
        output_path=output_path,
        tolerance_cart=tolerance_cart,
        indent=indent,
    )


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
            raise ValueError("--json-output can only be used when the input is a CIF or XYZ file.")
        return input_path

    if suffix == ".cif":
        output_path = (
            json_output
            if json_output is not None
            else default_json_output_path(input_path, json_dir)
        )
        if json_output is None:
            cached = cached_export_json_path(input_path, output_path, mode=SOURCE_KIND_CRYSTAL)
            if cached is not None:
                print(f"Using cached JSON: {cached}", flush=True)
                return cached
        print(f"Analyzing CIF: {input_path}", flush=True)
        output_path = export_analysis_to_json(
            input_path,
            mode=SOURCE_KIND_CRYSTAL,
            output_path=output_path,
            tolerance_cart=tolerance_cart,
            indent=indent,
        )
        print(f"Wrote JSON: {output_path}", flush=True)
        return output_path

    if suffix == ".xyz":
        output_path = (
            json_output
            if json_output is not None
            else default_json_output_path(input_path, json_dir)
        )
        if json_output is None:
            cached = cached_export_json_path(input_path, output_path, mode=SOURCE_KIND_MOLECULE)
            if cached is not None:
                print(f"Using cached JSON: {cached}", flush=True)
                return cached
        print(f"Analyzing molecule: {input_path}", flush=True)
        output_path = export_analysis_to_json(
            input_path,
            mode=SOURCE_KIND_MOLECULE,
            output_path=output_path,
            tolerance_cart=tolerance_cart,
            indent=indent,
        )
        print(f"Wrote JSON: {output_path}", flush=True)
        return output_path

    raise ValueError(f"Unsupported input file type: {input_path.suffix}. Use .json, .cif, or .xyz.")


def default_starter_path() -> Path:
    for path in DEFAULT_STARTER_PATHS:
        if path.exists():
            return path
    raise FileNotFoundError(
        "No input_path was provided and no starter JSON was found. "
        "Provide a JSON/CIF path, or create exports/json/halite.json."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Browser controls + PyVista view for exported symmetry JSON, CIF, or XYZ."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        nargs="?",
        help="Exported JSON, or a CIF/XYZ file to analyze and export first.",
    )
    parser.add_argument("--operation", type=int, default=None, help="Initial operation index.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5173)
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Where to write the generated JSON when input_path is a CIF or XYZ file.",
    )
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=DEFAULT_JSON_EXPORT_DIR,
        help="Directory for generated JSON when input_path is a CIF or XYZ file and --json-output is not set.",
    )
    parser.add_argument(
        "--import-json-dir",
        type=Path,
        default=DEFAULT_BROWSER_IMPORT_JSON_DIR,
        help="Directory for JSON generated by browser Open CIF/Open XYZ imports.",
    )
    parser.add_argument(
        "--tolerance-cart",
        type=float,
        default=1e-2,
        help="Atom mapping tolerance in Angstrom for generated CIF/XYZ exports.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation for generated CIF/XYZ exports.",
    )
    parser.add_argument(
        "--expanded",
        action="store_true",
        help="Show quarter-cell periodic display clones. Slower, but useful for boundary checks.",
    )
    args = parser.parse_args()

    input_path = args.input_path if args.input_path is not None else write_empty_viewer_json()
    json_path = resolve_viewer_json_path(
        input_path,
        json_output=args.json_output,
        json_dir=args.json_dir,
        tolerance_cart=args.tolerance_cart,
        indent=args.indent,
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    display_mode = "expanded_quarter" if args.expanded else "source"
    session = ViewerSession(json_path, payload)

    state_lock = threading.Lock()
    shared_state = initial_state_for_payload(
        payload,
        initial_operation=args.operation,
        display_mode=display_mode,
    )
    shared_state["reset"] = False
    shared_state["reload_request_id"] = 0
    shared_state["json_path"] = str(json_path)

    handler = make_handler(
        session,
        shared_state,
        state_lock,
        json_dir=args.json_dir,
        import_json_dir=args.import_json_dir,
        tolerance_cart=args.tolerance_cart,
        indent=args.indent,
        default_display_mode=display_mode,
    )
    example_catalog()
    app = BrowserControlledViewer(
        json_path,
        display_mode=display_mode,
        initial_operation=shared_state["operation_index"],
        scope=shared_state["scope"],
        shared_state=shared_state,
        state_lock=state_lock,
        element_context_cache=session.element_context_cache,
        viewer_session=session,
    )
    server = start_server(args.host, args.port, handler)
    url = f"http://{args.host}:{server.server_port}/"
    print(f"Control panel: {url}")
    if not args.no_browser:
        open_url(url)

    app.show()
    server.shutdown()
    server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
