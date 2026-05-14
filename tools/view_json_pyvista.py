from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pyvista as pv


ELEMENT_COLORS = {
    "H": "#f4f4f4",
    "C": "#333333",
    "N": "#3050f8",
    "O": "#ff0d0d",
    "F": "#90e050",
    "P": "#ff8000",
    "S": "#ffff30",
    "Cl": "#1ff01f",
    "Na": "#ab5cf2",
    "Mg": "#8aff00",
    "Al": "#bfa6a6",
    "Si": "#f0c8a0",
    "K": "#8f40d4",
    "Ca": "#3dff00",
    "Fe": "#e06633",
    "Cu": "#c88033",
    "Zn": "#7d80b0",
    "Ga": "#c28f8f",
    "As": "#bd80e3",
    "Pd": "#8aa6c1",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal PyVista viewer for exported symmetry JSON.")
    parser.add_argument("json_path", type=Path)
    parser.add_argument("--operation", type=int, default=None, help="Show only symmetry elements for this operation.")
    parser.add_argument("--list-operations", action="store_true", help="Print operation list and exit.")
    parser.add_argument("--show-mapping", action="store_true", help="Print atom mapping for --operation.")
    parser.add_argument("--show-displacements", action="store_true", help="Draw source-to-target displacement lines.")
    parser.add_argument("--no-atoms", action="store_true")
    parser.add_argument("--no-cell", action="store_true")
    parser.add_argument("--no-elements", action="store_true")
    parser.add_argument("--screenshot", type=Path, default=None, help="Write a screenshot and exit.")
    parser.add_argument("--off-screen", action="store_true", help="Render off-screen. Useful with --screenshot.")
    args = parser.parse_args()

    payload = json.loads(args.json_path.read_text(encoding="utf-8"))
    render_data = payload["render_data"]
    atom_mappings = payload.get("atom_mappings")

    if args.list_operations:
        print_operations(render_data, atom_mappings)
        return 0

    if args.show_mapping:
        print_mapping(atom_mappings, args.operation)

    plotter = pv.Plotter(off_screen=args.off_screen or args.screenshot is not None)
    plotter.set_background("#101216")

    if not args.no_atoms:
        add_atoms(plotter, render_data)
    if not args.no_cell and render_data.get("unit_cell"):
        add_unit_cell(plotter, render_data["unit_cell"])
    if not args.no_elements:
        add_symmetry_elements(plotter, render_data, operation_index=args.operation)
    if args.show_displacements:
        add_displacements(plotter, render_data, atom_mappings, operation_index=args.operation)

    add_title(plotter, render_data, args.json_path, args.operation)
    plotter.add_axes()
    plotter.reset_camera()

    if args.screenshot is not None:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        plotter.show(screenshot=str(args.screenshot), auto_close=True)
        print(f"Wrote {args.screenshot}")
    else:
        plotter.show()

    return 0


def add_atoms(plotter: pv.Plotter, render_data: dict) -> None:
    bounds_span = scene_span(render_data)
    for atom in render_data["atoms"]:
        center = np.asarray(atom["cart"], dtype=float)
        radius = atom_radius(atom["atomic_number"], bounds_span)
        color = ELEMENT_COLORS.get(atom["element"], "#9aa5b1")
        sphere = pv.Sphere(
            radius=radius,
            center=center,
            theta_resolution=24,
            phi_resolution=16,
        )
        plotter.add_mesh(sphere, color=color, smooth_shading=True)


def add_unit_cell(plotter: pv.Plotter, unit_cell: dict) -> None:
    vertices = np.asarray(unit_cell["vertices_cart"], dtype=float)
    lines = []
    for start, end in unit_cell["edges"]:
        lines.extend([2, int(start), int(end)])
    mesh = pv.PolyData(vertices, lines=np.asarray(lines))
    plotter.add_mesh(mesh, color="#d6dde6", line_width=2)


def add_symmetry_elements(
    plotter: pv.Plotter,
    render_data: dict,
    *,
    operation_index: int | None,
) -> None:
    span = scene_span(render_data)
    axis_length = max(span * 0.75, 1.0)
    plane_scale = max(span * 0.28, 0.5)

    for axis in filter_by_operation(render_data["axes"], operation_index):
        point = np.asarray(axis["point_cart"], dtype=float)
        direction = normalize(np.asarray(axis["direction_cart"], dtype=float))
        line = pv.Line(point - axis_length * direction, point + axis_length * direction)
        plotter.add_mesh(line, color="#58d68d", line_width=6)

    for plane in filter_by_operation(render_data["planes"], operation_index):
        point = np.asarray(plane["point_cart"], dtype=float)
        basis1 = normalize(np.asarray(plane["basis1_cart"], dtype=float)) * plane_scale
        basis2 = normalize(np.asarray(plane["basis2_cart"], dtype=float)) * plane_scale
        points = np.array(
            [
                point - basis1 - basis2,
                point + basis1 - basis2,
                point + basis1 + basis2,
                point - basis1 + basis2,
            ]
        )
        faces = np.array([4, 0, 1, 2, 3])
        mesh = pv.PolyData(points, faces)
        plotter.add_mesh(
            mesh,
            color="#5dade2",
            opacity=0.35,
            show_edges=True,
            edge_color="#aed6f1",
        )

    for center in filter_by_operation(render_data["centers"], operation_index):
        point = np.asarray(center["point_cart"], dtype=float)
        sphere = pv.Sphere(radius=max(span * 0.035, 0.08), center=point)
        plotter.add_mesh(sphere, color="#ff5f57", smooth_shading=True)


def add_displacements(
    plotter: pv.Plotter,
    render_data: dict,
    atom_mappings: dict | None,
    *,
    operation_index: int | None,
) -> None:
    mapping = selected_mapping(atom_mappings, operation_index)
    if mapping is None:
        print("No atom mapping found. Use --operation with --show-displacements.")
        return

    atoms_by_index = {atom["index"]: atom for atom in render_data["atoms"]}
    span = scene_span(render_data)
    tube_radius = max(span * 0.004, 0.01)
    endpoint_radius = max(span * 0.015, 0.04)

    for entry in mapping["entries"]:
        source_atom = atoms_by_index.get(entry["source_atom"])
        if source_atom is None:
            continue
        start = np.asarray(source_atom["cart"], dtype=float)
        end = np.asarray(entry["transformed_cart"], dtype=float)
        if np.linalg.norm(end - start) < 1e-9:
            continue

        line = pv.Line(start, end)
        tube = line.tube(radius=tube_radius, n_sides=10)
        plotter.add_mesh(tube, color="#f4d03f", opacity=0.8)
        marker = pv.Sphere(radius=endpoint_radius, center=end, theta_resolution=16, phi_resolution=10)
        plotter.add_mesh(marker, color="#f7dc6f", opacity=0.85, smooth_shading=True)


def add_title(
    plotter: pv.Plotter,
    render_data: dict,
    json_path: Path,
    operation_index: int | None,
) -> None:
    metadata = render_data["metadata"]
    text = f"{metadata['formula']}  |  {metadata['symmetry_label']}  |  {metadata['mode']}"
    if operation_index is not None:
        operation = operation_by_index(render_data["operations"], operation_index)
        suffix = operation["label"] if operation else f"operation {operation_index}"
        text = f"{text}  |  {suffix}"
    text = f"{text}\n{json_path}"
    plotter.add_text(text, position="upper_left", font_size=10, color="#eef2f7")


def print_operations(render_data: dict, atom_mappings: dict | None) -> None:
    mapping_by_index = {}
    if atom_mappings is not None:
        mapping_by_index = {
            mapping["operation_index"]: mapping
            for mapping in atom_mappings.get("mappings", [])
        }

    print("=== Operations ===")
    for operation in render_data["operations"]:
        mapping = mapping_by_index.get(operation["index"])
        if mapping is None:
            status = "mapping=missing"
        else:
            status = f"mapping={'ok' if mapping['complete'] else 'incomplete'} max_dist={mapping['max_distance']:.3e}"
        print(
            f"{operation['index']:3d}: {operation['label']} "
            f"kind={operation['kind']} order={operation['order']} {status}"
        )


def print_mapping(atom_mappings: dict | None, operation_index: int | None) -> None:
    mapping = selected_mapping(atom_mappings, operation_index)
    if mapping is None:
        print("No atom mapping found. Use --operation with --show-mapping.")
        return

    print("=== Atom Mapping ===")
    print(
        f"Operation {mapping['operation_index']}: {mapping['operation_kind']}, "
        f"complete={mapping['complete']}, max_distance={mapping['max_distance']:.3e}"
    )
    print("atom_to_atom:", mapping["atom_to_atom"])
    for entry in mapping["entries"]:
        print(
            f"  {entry['source_atom']} -> {entry['target_atom']} "
            f"dist={entry['distance']:.3e} target={entry['transformed_cart']}"
        )


def selected_mapping(atom_mappings: dict | None, operation_index: int | None) -> dict | None:
    if atom_mappings is None or operation_index is None:
        return None
    for mapping in atom_mappings.get("mappings", []):
        if mapping["operation_index"] == operation_index:
            return mapping
    return None


def filter_by_operation(elements: list[dict], operation_index: int | None) -> list[dict]:
    if operation_index is None:
        return elements
    return [
        element
        for element in elements
        if operation_index in element.get("operation_indices", [])
    ]


def operation_by_index(operations: list[dict], operation_index: int) -> dict | None:
    for operation in operations:
        if operation["index"] == operation_index:
            return operation
    return None


def scene_span(render_data: dict) -> float:
    bounds_min = np.asarray(render_data["bounds_min"], dtype=float)
    bounds_max = np.asarray(render_data["bounds_max"], dtype=float)
    span = np.linalg.norm(bounds_max - bounds_min)
    return float(span if span > 1e-9 else 1.0)


def atom_radius(atomic_number: int, scene_span_value: float) -> float:
    scale = max(scene_span_value * 0.035, 0.12)
    if atomic_number <= 2:
        return scale * 0.75
    if atomic_number <= 10:
        return scale
    if atomic_number <= 18:
        return scale * 1.15
    return scale * 1.3


def normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm < 1e-12:
        return vector
    return vector / norm


if __name__ == "__main__":
    raise SystemExit(main())
