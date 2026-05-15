from __future__ import annotations

import argparse
import json
import time
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

_PERIODIC_SHIFTS = np.array(
    [(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)],
    dtype=float,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal PyVista viewer for exported symmetry JSON.")
    parser.add_argument("json_path", type=Path)
    parser.add_argument("--operation", type=int, default=None, help="Show only symmetry elements for this operation.")
    parser.add_argument("--list-operations", action="store_true", help="Print operation list and exit.")
    parser.add_argument("--show-mapping", action="store_true", help="Print atom mapping for --operation.")
    parser.add_argument("--show-displacements", action="store_true", help="Draw source-to-target displacement lines.")
    parser.add_argument("--animate", action="store_true", help="Animate atoms for --operation.")
    parser.add_argument("--animation-frames", type=int, default=48, help="Number of animation frames.")
    parser.add_argument("--animation-fps", type=float, default=10.0, help="Animation frames per second.")
    parser.add_argument("--animation-output", type=Path, default=None, help="Write animation to a GIF file.")
    parser.add_argument(
        "--element-index",
        type=int,
        default=None,
        help="Use one symmetry element by its index within axes/planes/centers.",
    )
    parser.add_argument("--list-elements", action="store_true", help="Print symmetry elements for --operation and exit.")
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
    if args.list_elements:
        print_elements(render_data, args.operation)
        return 0

    if args.show_mapping:
        print_mapping(atom_mappings, args.operation)

    if args.animate and args.operation is None:
        parser.error("--animate requires --operation")
    if args.element_index is not None:
        if args.operation is None:
            parser.error("--element-index requires --operation")
        if not has_element_index(render_data, args.operation, args.element_index):
            parser.error(f"--element-index {args.element_index} is not available for operation {args.operation}")

    plotter = pv.Plotter(
        off_screen=args.off_screen
        or args.screenshot is not None
        or args.animation_output is not None
    )
    plotter.set_background("#101216")

    animated_atoms = None
    if args.animate and not args.no_atoms:
        animated_atoms = add_animated_atoms(plotter, render_data)
    elif not args.no_atoms:
        add_atoms(plotter, render_data)
    if not args.no_cell and render_data.get("unit_cell"):
        add_unit_cell(plotter, render_data["unit_cell"])
    if not args.no_elements:
        add_symmetry_elements(
            plotter,
            render_data,
            operation_index=args.operation,
            element_index=args.element_index,
        )
    if args.show_displacements:
        add_displacements(plotter, render_data, atom_mappings, operation_index=args.operation)

    add_title(plotter, render_data, args.json_path, args.operation)
    plotter.add_axes()
    plotter.reset_camera()

    if args.animate:
        run_animation(
            plotter,
            render_data,
            atom_mappings,
            operation_index=args.operation,
            animated_atoms=animated_atoms,
            frame_count=args.animation_frames,
            fps=args.animation_fps,
            output_path=args.animation_output,
            element_index=args.element_index,
        )
    elif args.screenshot is not None:
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


def add_animated_atoms(plotter: pv.Plotter, render_data: dict) -> list[dict]:
    animated = []
    bounds_span = scene_span(render_data)
    for atom in render_data["atoms"]:
        center = np.asarray(atom["cart"], dtype=float)
        radius = atom_radius(atom["atomic_number"], bounds_span)
        color = ELEMENT_COLORS.get(atom["element"], "#9aa5b1")
        base = pv.Sphere(
            radius=radius,
            center=(0.0, 0.0, 0.0),
            theta_resolution=16,
            phi_resolution=10,
        )
        mesh = base.copy()
        mesh.points = base.points + center
        plotter.add_mesh(mesh, color=color, smooth_shading=True)
        animated.append({"atom": atom, "base_points": base.points.copy(), "mesh": mesh})
    return animated


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
    element_index: int | None = None,
) -> None:
    span = scene_span(render_data)
    axis_length = max(span * 0.75, 1.0)
    plane_scale = max(span * 0.28, 0.5)

    for axis in selected_elements(render_data["axes"], operation_index, element_index):
        point = np.asarray(axis["point_cart"], dtype=float)
        direction = normalize(np.asarray(axis["direction_cart"], dtype=float))
        line = pv.Line(point - axis_length * direction, point + axis_length * direction)
        plotter.add_mesh(line, color="#58d68d", line_width=6)

    for plane in selected_elements(render_data["planes"], operation_index, element_index):
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

    for center in selected_elements(render_data["centers"], operation_index, element_index):
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


def run_animation(
    plotter: pv.Plotter,
    render_data: dict,
    atom_mappings: dict | None,
    *,
    operation_index: int | None,
    animated_atoms: list[dict] | None,
    frame_count: int,
    fps: float,
    output_path: Path | None,
    element_index: int | None,
) -> None:
    if animated_atoms is None:
        print("Animation skipped because atoms are hidden.")
        return
    operation = operation_by_index(render_data["operations"], operation_index)
    mapping = selected_mapping(atom_mappings, operation_index)
    if operation is None or mapping is None:
        print("Animation requires a valid --operation with atom mapping.")
        return

    frames = max(frame_count, 2)
    paths = animation_paths(render_data, operation, mapping, element_index=element_index)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plotter.open_gif(str(output_path), fps=max(float(fps), 1.0))
        plotter.show(auto_close=False, interactive_update=True)
        for frame in range(frames):
            update_animated_atoms(animated_atoms, paths, frame / (frames - 1))
            plotter.write_frame()
        plotter.close()
        print(f"Wrote {output_path}")
        return

    plotter.show(auto_close=False, interactive_update=True)
    delay = 1.0 / max(float(fps), 1.0)
    for frame in range(frames):
        update_animated_atoms(animated_atoms, paths, frame / (frames - 1))
        plotter.update()
        time.sleep(delay)
    plotter.show()


def update_animated_atoms(animated_atoms: list[dict], paths: dict[int, dict], s: float) -> None:
    for item in animated_atoms:
        atom = item["atom"]
        path = paths.get(atom["index"])
        center = np.asarray(atom["cart"], dtype=float) if path is None else evaluate_path(path, s)
        item["mesh"].points = item["base_points"] + center


def animation_paths(
    render_data: dict,
    operation: dict,
    mapping: dict,
    *,
    element_index: int | None = None,
) -> dict[int, dict]:
    atoms_by_index = {atom["index"]: atom for atom in render_data["atoms"]}
    axes = selected_elements(render_data["axes"], operation["index"], element_index)
    planes = selected_elements(render_data["planes"], operation["index"], element_index)
    centers = selected_elements(render_data["centers"], operation["index"], element_index)
    axis = axes[0] if axes else None
    plane = planes[0] if planes else None
    center = centers[0] if centers else None

    paths = {}
    for entry in mapping["entries"]:
        atom = atoms_by_index.get(entry["source_atom"])
        if atom is None:
            continue
        start = np.asarray(atom["cart"], dtype=float)
        target = animation_target(render_data, start, entry, operation, axis, plane, center)
        paths[entry["source_atom"]] = build_operation_path(
            start,
            target,
            operation,
            axis=axis,
            plane=plane,
            center=center,
        )
    return paths


def animation_target(
    render_data: dict,
    start: np.ndarray,
    entry: dict,
    operation: dict,
    axis: dict | None,
    plane: dict | None,
    center: dict | None,
) -> np.ndarray:
    default_target = np.asarray(entry["transformed_cart"], dtype=float)
    candidates = periodic_target_candidates(render_data, entry)
    if len(candidates) == 1:
        return candidates[0]

    kind = str(operation["kind"])
    if kind.startswith(("rotation", "screw")) and axis is not None and operation.get("angle_deg") is not None:
        axis_point = np.asarray(axis["point_cart"], dtype=float)
        axis_direction = normalize(np.asarray(axis["direction_cart"], dtype=float))
        angle = signed_angle_to_target(start, default_target, axis_point, axis_direction, operation["angle_deg"])
        rotated = rotate_about_axis(start, axis_point, axis_direction, angle)
        return best_axis_consistent_target(candidates, rotated, axis_direction)
    if "glide" in kind or kind == "mirror":
        if plane is None:
            return default_target
        plane_point = np.asarray(plane["point_cart"], dtype=float)
        plane_normal = normalize(np.asarray(plane["normal_cart"], dtype=float))
        mirrored = reflect_point(start, plane_point, plane_normal)
        return best_plane_consistent_target(candidates, mirrored, plane_normal)
    if kind == "inversion" and center is not None:
        center_point = np.asarray(center["point_cart"], dtype=float)
        inverted = 2.0 * center_point - start
        return candidates[np.argmin(np.linalg.norm(candidates - inverted, axis=1))]
    return default_target


def periodic_target_candidates(render_data: dict, entry: dict) -> np.ndarray:
    frac = entry.get("transformed_frac")
    unit_cell = render_data.get("unit_cell")
    if frac is None or unit_cell is None:
        return np.asarray([entry["transformed_cart"]], dtype=float)
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac = np.asarray(frac, dtype=float)
    return (frac + _PERIODIC_SHIFTS) @ lattice


def best_axis_consistent_target(candidates: np.ndarray, rotated: np.ndarray, axis_direction: np.ndarray) -> np.ndarray:
    residuals = candidates - rotated
    parallel = np.outer(residuals @ axis_direction, axis_direction)
    perpendicular = residuals - parallel
    scores = np.linalg.norm(perpendicular, axis=1) + 1e-6 * np.linalg.norm(residuals, axis=1)
    return candidates[np.argmin(scores)]


def best_plane_consistent_target(candidates: np.ndarray, mirrored: np.ndarray, plane_normal: np.ndarray) -> np.ndarray:
    residuals = candidates - mirrored
    normal_distance = np.abs(residuals @ plane_normal)
    scores = normal_distance + 1e-6 * np.linalg.norm(residuals, axis=1)
    return candidates[np.argmin(scores)]


def build_operation_path(
    start: np.ndarray,
    target: np.ndarray,
    operation: dict,
    *,
    axis: dict | None,
    plane: dict | None,
    center: dict | None,
) -> dict:
    kind = str(operation["kind"])
    if np.linalg.norm(target - start) < 1e-10:
        return translation_path(start, target)
    if kind.startswith("screw"):
        return screw_path(start, target, operation, axis)
    if "glide" in kind:
        return glide_path(start, target, plane)
    if "rotoinversion" in kind or "rotoreflection" in kind or "improper" in kind:
        return improper_path(start, target, operation, axis, plane, center)
    if kind.startswith("rotation"):
        return rotation_path(start, target, operation, axis)
    if kind == "mirror":
        return mirror_path(start, target, plane)
    if kind == "inversion":
        return inversion_path(start, target, center)
    return translation_path(start, target)


def rotation_path(start: np.ndarray, target: np.ndarray, operation: dict, axis: dict | None) -> dict:
    if axis is None or operation.get("angle_deg") is None:
        return translation_path(start, target)
    axis_point = np.asarray(axis["point_cart"], dtype=float)
    axis_direction = normalize(np.asarray(axis["direction_cart"], dtype=float))
    angle = signed_angle_to_target(start, target, axis_point, axis_direction, operation["angle_deg"])
    rotated = rotate_about_axis(start, axis_point, axis_direction, angle)
    return {
        "type": "rotation",
        "start": start,
        "target": target,
        "axis_point": axis_point,
        "axis_direction": axis_direction,
        "angle": angle,
        "residual": target - rotated,
    }


def screw_path(start: np.ndarray, target: np.ndarray, operation: dict, axis: dict | None) -> dict:
    rotated_path = rotation_path(start, target, operation, axis)
    if rotated_path["type"] != "rotation":
        return translation_path(start, target)
    rotated_end = rotate_about_axis(
        start,
        rotated_path["axis_point"],
        rotated_path["axis_direction"],
        rotated_path["angle"],
    )
    return {
        "type": "sequential",
        "segments": (
            {**rotated_path, "target": rotated_end, "residual": np.zeros(3)},
            translation_path(rotated_end, target),
        ),
    }


def mirror_path(start: np.ndarray, target: np.ndarray, plane: dict | None) -> dict:
    if plane is None:
        return translation_path(start, target)
    point = np.asarray(plane["point_cart"], dtype=float)
    normal = normalize(np.asarray(plane["normal_cart"], dtype=float))
    mirrored = reflect_point(start, point, normal)
    return {
        "type": "mirror",
        "start": start,
        "target": target,
        "plane_point": point,
        "plane_normal": normal,
        "residual": target - mirrored,
    }


def glide_path(start: np.ndarray, target: np.ndarray, plane: dict | None) -> dict:
    mirrored_path = mirror_path(start, target, plane)
    if mirrored_path["type"] != "mirror":
        return translation_path(start, target)
    mirrored_end = reflect_point(start, mirrored_path["plane_point"], mirrored_path["plane_normal"])
    return {
        "type": "sequential",
        "segments": (
            {**mirrored_path, "target": mirrored_end, "residual": np.zeros(3)},
            translation_path(mirrored_end, target),
        ),
    }


def inversion_path(start: np.ndarray, target: np.ndarray, center: dict | None) -> dict:
    center_point = None if center is None else np.asarray(center["point_cart"], dtype=float)
    if center_point is None:
        return translation_path(start, target)
    inverted = 2.0 * center_point - start
    return {
        "type": "inversion",
        "start": start,
        "target": target,
        "center": center_point,
        "residual": target - inverted,
    }


def improper_path(
    start: np.ndarray,
    target: np.ndarray,
    operation: dict,
    axis: dict | None,
    plane: dict | None,
    center: dict | None,
) -> dict:
    rotated = rotation_path(start, target, operation, axis)
    if rotated["type"] != "rotation":
        if "rotoinversion" in str(operation["kind"]):
            return inversion_path(start, target, center)
        return mirror_path(start, target, plane)
    rotated_end = rotate_about_axis(start, rotated["axis_point"], rotated["axis_direction"], rotated["angle"])
    if "rotoinversion" in str(operation["kind"]):
        second = inversion_path(rotated_end, target, center)
    else:
        second = mirror_path(rotated_end, target, plane)
    return {
        "type": "sequential",
        "segments": ({**rotated, "target": rotated_end, "residual": np.zeros(3)}, second),
    }


def translation_path(start: np.ndarray, target: np.ndarray) -> dict:
    return {"type": "linear", "start": start, "target": target}


def evaluate_path(path: dict, s: float) -> np.ndarray:
    s = float(np.clip(s, 0.0, 1.0))
    path_type = path["type"]
    if path_type == "sequential":
        segments = path["segments"]
        segment_count = len(segments)
        index = min(int(s * segment_count), segment_count - 1)
        local_s = (s - index / segment_count) * segment_count
        return evaluate_path(segments[index], local_s)
    if path_type == "rotation":
        rotated = rotate_about_axis(
            path["start"],
            path["axis_point"],
            path["axis_direction"],
            path["angle"] * s,
        )
        return rotated + path["residual"] * s
    if path_type == "mirror":
        mirrored = reflect_point(path["start"], path["plane_point"], path["plane_normal"])
        return interpolate(path["start"], mirrored, s) + path["residual"] * s
    if path_type == "inversion":
        inverted = 2.0 * path["center"] - path["start"]
        return interpolate(path["start"], inverted, s) + path["residual"] * s
    return interpolate(path["start"], path["target"], s)


def interpolate(start: np.ndarray, target: np.ndarray, s: float) -> np.ndarray:
    return (1.0 - s) * start + s * target


def rotate_about_axis(
    point: np.ndarray,
    axis_point: np.ndarray,
    axis_direction: np.ndarray,
    angle_rad: float,
) -> np.ndarray:
    direction = normalize(axis_direction)
    relative = point - axis_point
    cos_a = np.cos(angle_rad)
    sin_a = np.sin(angle_rad)
    rotated = (
        relative * cos_a
        + np.cross(direction, relative) * sin_a
        + direction * np.dot(direction, relative) * (1.0 - cos_a)
    )
    return axis_point + rotated


def signed_angle_to_target(
    start: np.ndarray,
    target: np.ndarray,
    axis_point: np.ndarray,
    axis_direction: np.ndarray,
    angle_deg: float,
) -> float:
    angle = np.deg2rad(float(angle_deg))
    plus = rotate_about_axis(start, axis_point, axis_direction, angle)
    minus = rotate_about_axis(start, axis_point, axis_direction, -angle)
    return angle if np.linalg.norm(target - plus) <= np.linalg.norm(target - minus) else -angle


def reflect_point(point: np.ndarray, plane_point: np.ndarray, plane_normal: np.ndarray) -> np.ndarray:
    normal = normalize(plane_normal)
    return point - 2.0 * np.dot(point - plane_point, normal) * normal


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
            f"kind={operation['kind']} order={operation['order']} "
            f"angle={operation.get('angle_deg')} {status}"
        )


def print_elements(render_data: dict, operation_index: int | None) -> None:
    if operation_index is None:
        print("Use --operation with --list-elements.")
        return

    print(f"=== Symmetry Elements for operation {operation_index} ===")
    for kind, key in (("axis", "axes"), ("plane", "planes"), ("center", "centers")):
        elements = filter_by_operation(render_data[key], operation_index)
        if not elements:
            continue
        print(f"{key}:")
        for index, element in enumerate(elements):
            label = element.get("label", "?")
            point = element.get("point_cart")
            direction = element.get("direction_cart") or element.get("normal_cart")
            print(f"  {index}: label={label} point={point} direction/normal={direction}")


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


def selected_elements(elements: list[dict], operation_index: int | None, element_index: int | None) -> list[dict]:
    filtered = filter_by_operation(elements, operation_index)
    if element_index is None:
        return filtered
    if element_index < 0 or element_index >= len(filtered):
        return []
    return [filtered[element_index]]


def has_element_index(render_data: dict, operation_index: int, element_index: int) -> bool:
    return any(
        0 <= element_index < len(filter_by_operation(render_data[key], operation_index))
        for key in ("axes", "planes", "centers")
    )


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
