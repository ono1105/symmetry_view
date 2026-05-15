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
        "--animation-scope",
        choices=("all", "representative"),
        default="all",
        help="Animate all atoms with one shared periodic image choice, or only one representative atom.",
    )
    parser.add_argument(
        "--representative-atom",
        type=int,
        default=None,
        help="Source atom index used to choose the shared animation target image.",
    )
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
            animation_scope=args.animation_scope,
            representative_atom=args.representative_atom,
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
    for item in display_atom_instances(render_data):
        atom = item["atom"]
        center = item["cart"]
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
    for item in display_atom_instances(render_data):
        atom = item["atom"]
        center = item["cart"]
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
        animated.append(
            {
                "atom": atom,
                "display_shift_cart": item["display_shift_cart"],
                "base_points": base.points.copy(),
                "mesh": mesh,
            }
        )
    return animated


def display_atom_instances(render_data: dict) -> list[dict]:
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return [
            {
                "atom": atom,
                "cart": np.asarray(atom["cart"], dtype=float),
                "display_shift_cart": np.zeros(3),
            }
            for atom in render_data["atoms"]
        ]

    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    instances = []
    for atom in render_data["atoms"]:
        frac = atom.get("frac")
        if frac is None:
            instances.append(
                {
                    "atom": atom,
                    "cart": np.asarray(atom["cart"], dtype=float),
                    "display_shift_cart": np.zeros(3),
                }
            )
            continue

        frac = np.asarray(frac, dtype=float)
        for shift in display_fractional_shifts(frac):
            shift_cart = shift @ lattice
            instances.append(
                {
                    "atom": atom,
                    "cart": np.asarray(atom["cart"], dtype=float) + shift_cart,
                    "display_shift_cart": shift_cart,
                }
            )
    return instances


def display_fractional_shifts(frac: np.ndarray) -> list[np.ndarray]:
    shifts = []
    for shift in _PERIODIC_SHIFTS:
        image_frac = frac + shift
        if np.all(image_frac >= -0.5 - 1e-9) and np.all(image_frac <= 1.5 + 1e-9):
            shifts.append(shift)
    return shifts


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
    animation_scope: str,
    representative_atom: int | None,
) -> None:
    if animated_atoms is None:
        print("Animation skipped because atoms are hidden.")
        return
    operation = operation_by_index(render_data["operations"], operation_index)
    mapping = selected_mapping(atom_mappings, operation_index)
    if operation is None or mapping is None:
        print("Animation requires a valid --operation with atom mapping.")
        return
    if representative_atom is not None and not any(
        entry["source_atom"] == representative_atom for entry in mapping["entries"]
    ):
        print(f"Animation skipped because --representative-atom {representative_atom} is not in this mapping.")
        return

    frames = max(frame_count, 2)
    paths = animation_paths(
        render_data,
        operation,
        mapping,
        element_index=element_index,
        animation_scope=animation_scope,
        representative_atom=representative_atom,
    )
    if not paths:
        print("Animation skipped because no atom path could be built. Check --representative-atom.")
        return

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
        center = center + item["display_shift_cart"]
        item["mesh"].points = item["base_points"] + center


def animation_paths(
    render_data: dict,
    operation: dict,
    mapping: dict,
    *,
    element_index: int | None = None,
    animation_scope: str = "all",
    representative_atom: int | None = None,
) -> dict[int, dict]:
    atoms_by_index = {atom["index"]: atom for atom in render_data["atoms"]}
    axis, plane, center, reference_entry, shared_shift, shared_angle = select_animation_context(
        render_data,
        operation,
        mapping,
        atoms_by_index,
        element_index=element_index,
        representative_atom=representative_atom,
    )

    if reference_entry is None:
        return {}

    axis = effective_rotation_axis(operation, axis, center)
    shared_angle = shared_rotation_angle(
        render_data,
        reference_entry,
        operation,
        axis,
        plane,
        center,
        shared_shift,
    )

    paths = {}
    entries = mapping["entries"]
    if animation_scope == "representative":
        entries = [reference_entry]

    for entry in entries:
        atom = atoms_by_index.get(entry["source_atom"])
        if atom is None:
            continue
        start = np.asarray(atom["cart"], dtype=float)
        target = animation_target(
            render_data,
            start,
            entry,
            operation,
            axis,
            plane,
            center,
            shared_shift=shared_shift,
        )
        paths[entry["source_atom"]] = build_operation_path(
            start,
            target,
            operation,
            axis=axis,
            plane=plane,
            center=center,
            angle_override=shared_angle,
        )
    return paths


def select_animation_context(
    render_data: dict,
    operation: dict,
    mapping: dict,
    atoms_by_index: dict[int, dict],
    *,
    element_index: int | None,
    representative_atom: int | None,
) -> tuple[dict | None, dict | None, dict | None, dict | None, np.ndarray | None, float | None]:
    if element_index is not None:
        return build_animation_context(
            render_data,
            operation,
            mapping,
            atoms_by_index,
            element_index=element_index,
            representative_atom=representative_atom,
        )

    candidates = []
    max_count = max(
        len(filter_by_operation(render_data[key], operation["index"]))
        for key in ("axes", "planes", "centers")
    )
    if max_count == 0:
        candidates.append(
            build_animation_context(
                render_data,
                operation,
                mapping,
                atoms_by_index,
                element_index=None,
                representative_atom=representative_atom,
            )
        )
    else:
        for candidate_index in range(max_count):
            candidates.append(
                build_animation_context(
                    render_data,
                    operation,
                    mapping,
                    atoms_by_index,
                    element_index=candidate_index,
                    representative_atom=representative_atom,
                )
            )

    best_context = candidates[0]
    best_score = float("inf")
    for context in candidates:
        score = animation_context_score(render_data, operation, mapping, atoms_by_index, context)
        if score < best_score:
            best_score = score
            best_context = context
    return best_context


def build_animation_context(
    render_data: dict,
    operation: dict,
    mapping: dict,
    atoms_by_index: dict[int, dict],
    *,
    element_index: int | None,
    representative_atom: int | None,
) -> tuple[dict | None, dict | None, dict | None, dict | None, np.ndarray | None, float | None]:
    axes = selected_elements(render_data["axes"], operation["index"], element_index)
    planes = selected_elements(render_data["planes"], operation["index"], element_index)
    centers = selected_elements(render_data["centers"], operation["index"], element_index)
    axis = axes[0] if axes else None
    plane = planes[0] if planes else None
    center = centers[0] if centers else None
    reference_entry = representative_mapping_entry(
        render_data,
        operation,
        mapping,
        atoms_by_index,
        axis,
        plane,
        center,
        representative_atom,
    )
    shared_shift = shared_periodic_shift(render_data, reference_entry, operation, axis, plane, center)
    element_shift = symmetry_element_shared_shift(render_data, operation, axis, plane, center)
    if element_shift is not None:
        shared_shift = element_shift
    center = effective_operation_center(render_data, operation, center, shared_shift)
    axis = effective_rotation_axis(operation, axis, center)
    shared_angle = shared_rotation_angle(
        render_data,
        reference_entry,
        operation,
        axis,
        plane,
        center,
        shared_shift,
    )
    return axis, plane, center, reference_entry, shared_shift, shared_angle


def animation_context_score(
    render_data: dict,
    operation: dict,
    mapping: dict,
    atoms_by_index: dict[int, dict],
    context: tuple[dict | None, dict | None, dict | None, dict | None, np.ndarray | None, float | None],
) -> float:
    axis, plane, center, _, shared_shift, shared_angle = context
    worst = 0.0
    for entry in mapping["entries"]:
        atom = atoms_by_index.get(entry["source_atom"])
        if atom is None:
            continue
        start = np.asarray(atom["cart"], dtype=float)
        target = animation_target(
            render_data,
            start,
            entry,
            operation,
            axis,
            plane,
            center,
            shared_shift=shared_shift,
        )
        path = build_operation_path(
            start,
            target,
            operation,
            axis=axis,
            plane=plane,
            center=center,
            angle_override=shared_angle,
        )
        worst = max(worst, max_path_residual(path))
    return worst


def max_path_residual(path: dict) -> float:
    residual = 0.0
    stack = [path]
    while stack:
        current = stack.pop()
        if current["type"] == "sequential":
            stack.extend(current["segments"])
        if current["type"] in ("rotation", "mirror", "inversion"):
            residual = max(residual, float(np.linalg.norm(current.get("residual", np.zeros(3)))))
    return residual


def representative_mapping_entry(
    render_data: dict,
    operation: dict,
    mapping: dict,
    atoms_by_index: dict[int, dict],
    axis: dict | None,
    plane: dict | None,
    center: dict | None,
    representative_atom: int | None,
) -> dict | None:
    entries = list(mapping["entries"])
    if representative_atom is not None:
        return next((entry for entry in entries if entry["source_atom"] == representative_atom), None)

    for entry in entries:
        atom = atoms_by_index.get(entry["source_atom"])
        if atom is None:
            continue
        start = np.asarray(atom["cart"], dtype=float)
        target = animation_target(render_data, start, entry, operation, axis, plane, center)
        if np.linalg.norm(target - start) > 1e-8:
            return entry
    return entries[0] if entries else None


def shared_periodic_shift(
    render_data: dict,
    reference_entry: dict | None,
    operation: dict,
    axis: dict | None,
    plane: dict | None,
    center: dict | None,
) -> np.ndarray | None:
    if reference_entry is None or reference_entry.get("transformed_frac") is None:
        return None
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return None

    atoms_by_index = {atom["index"]: atom for atom in render_data["atoms"]}
    reference_atom = atoms_by_index.get(reference_entry["source_atom"])
    if reference_atom is None:
        return None

    start = np.asarray(reference_atom["cart"], dtype=float)
    target = animation_target(render_data, start, reference_entry, operation, axis, plane, center)
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    target_frac = target @ np.linalg.inv(lattice)
    raw_frac = np.asarray(reference_entry["transformed_frac"], dtype=float)
    return np.rint(target_frac - raw_frac)


def symmetry_element_shared_shift(
    render_data: dict,
    operation: dict,
    axis: dict | None,
    plane: dict | None,
    center: dict | None,
) -> np.ndarray | None:
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None or operation.get("matrix_cart") is None or operation.get("translation_cart") is None:
        return None

    kind = str(operation["kind"])
    point = None
    if kind.startswith(("rotation", "screw")) and axis is not None:
        point = np.asarray(axis["point_cart"], dtype=float)
    elif (kind == "inversion" or "rotoinversion" in kind) and center is not None:
        point = np.asarray(center["point_cart"], dtype=float)
    elif kind == "mirror" and plane is not None:
        point = np.asarray(plane["point_cart"], dtype=float)

    if point is None:
        return None

    matrix = np.asarray(operation["matrix_cart"], dtype=float)
    translation = np.asarray(operation["translation_cart"], dtype=float)
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    required = (point - (matrix @ point + translation)) @ np.linalg.inv(lattice)
    rounded = np.rint(required)
    if np.linalg.norm(required - rounded) > 1e-5:
        return None
    return rounded


def shared_rotation_angle(
    render_data: dict,
    reference_entry: dict | None,
    operation: dict,
    axis: dict | None,
    plane: dict | None,
    center: dict | None,
    shared_shift: np.ndarray | None,
) -> float | None:
    kind = str(operation["kind"])
    if not (
        kind.startswith(("rotation", "screw"))
        or "rotoinversion" in kind
        or "rotoreflection" in kind
        or "improper" in kind
    ):
        return None
    angle_deg = operation_angle_deg(operation)
    if reference_entry is None or axis is None or angle_deg is None:
        return None

    atoms_by_index = {atom["index"]: atom for atom in render_data["atoms"]}
    reference_atom = atoms_by_index.get(reference_entry["source_atom"])
    if reference_atom is None:
        return None

    start = np.asarray(reference_atom["cart"], dtype=float)
    axis_point = np.asarray(axis["point_cart"], dtype=float)
    axis_direction = normalize(np.asarray(axis["direction_cart"], dtype=float))
    rotation = operation_rotation_matrix(operation)
    if rotation is not None:
        return signed_rotation_angle_from_matrix(rotation, axis_direction)
    target = animation_target(
        render_data,
        start,
        reference_entry,
        operation,
        axis,
        plane,
        center,
        shared_shift=shared_shift,
    )
    return signed_angle_to_target(start, target, axis_point, axis_direction, angle_deg)


def animation_target(
    render_data: dict,
    start: np.ndarray,
    entry: dict,
    operation: dict,
    axis: dict | None,
    plane: dict | None,
    center: dict | None,
    *,
    shared_shift: np.ndarray | None = None,
) -> np.ndarray:
    default_target = np.asarray(entry["transformed_cart"], dtype=float)
    if shared_shift is not None and entry.get("transformed_frac") is not None:
        affine_target = operation_affine_target(render_data, start, operation, shared_shift)
        if affine_target is not None:
            return affine_target
        unit_cell = render_data.get("unit_cell")
        if unit_cell is not None:
            lattice = np.asarray(unit_cell["lattice"], dtype=float)
            return (np.asarray(entry["transformed_frac"], dtype=float) + shared_shift) @ lattice

    candidates = periodic_target_candidates(render_data, entry)
    if len(candidates) == 1:
        return candidates[0]

    kind = str(operation["kind"])
    angle_deg = operation_angle_deg(operation)
    if kind.startswith(("rotation", "screw")) and axis is not None and angle_deg is not None:
        axis_point = np.asarray(axis["point_cart"], dtype=float)
        axis_direction = normalize(np.asarray(axis["direction_cart"], dtype=float))
        angle = signed_angle_to_target(start, default_target, axis_point, axis_direction, angle_deg)
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


def operation_affine_target(
    render_data: dict,
    start: np.ndarray,
    operation: dict,
    shared_shift: np.ndarray | None,
) -> np.ndarray | None:
    affine = operation_affine_matrix_translation(render_data, operation, shared_shift)
    if affine is None:
        return None
    matrix, translation = affine
    return matrix @ start + translation


def operation_affine_matrix_translation(
    render_data: dict,
    operation: dict,
    shared_shift: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray] | None:
    matrix = operation.get("matrix_cart")
    translation = operation.get("translation_cart")
    if matrix is None or translation is None:
        return None
    affine_matrix = np.asarray(matrix, dtype=float)
    affine_translation = np.asarray(translation, dtype=float)
    if shared_shift is not None and operation.get("matrix_frac") is not None:
        unit_cell = render_data.get("unit_cell")
        if unit_cell is not None:
            lattice = np.asarray(unit_cell["lattice"], dtype=float)
            affine_translation = affine_translation + np.asarray(shared_shift, dtype=float) @ lattice
    return affine_matrix, affine_translation


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


def effective_rotation_axis(operation: dict, axis: dict | None, center: dict | None) -> dict | None:
    if axis is not None:
        return axis
    kind = str(operation["kind"])
    if "rotoinversion" not in kind or center is None:
        return None
    matrix = operation.get("matrix_cart")
    if matrix is None:
        return None
    rotation = -np.asarray(matrix, dtype=float)
    direction = rotation_axis_from_matrix(rotation)
    if direction is None:
        return None
    return {
        "point_cart": center["point_cart"],
        "direction_cart": direction,
    }


def effective_operation_center(
    render_data: dict,
    operation: dict,
    center: dict | None,
    shared_shift: np.ndarray | None,
) -> dict | None:
    kind = str(operation["kind"])
    affine = operation_affine_matrix_translation(render_data, operation, shared_shift)
    if affine is None:
        return center
    matrix, translation = affine

    point = None
    if kind == "inversion":
        point = 0.5 * translation
    elif "rotoinversion" in kind:
        rotation = -matrix
        coeff = np.eye(3) + rotation
        point = np.linalg.pinv(coeff) @ translation

    if point is None:
        return center

    # Snap to the nearest periodic image of the visual center marker (Q4 fix).
    # The affine-computed fixed point can land on a different lattice image than
    # the visual element.  Only snap when shared_shift is absent or zero,
    # because the render_data visual center corresponds to the unshifted operation.
    # When shared_shift is nonzero, the correct pivot has already moved and
    # snapping to the original visual center would introduce a new error.
    shift_is_zero = shared_shift is None or not np.any(np.asarray(shared_shift, dtype=float))
    if center is not None and shift_is_zero:
        unit_cell = render_data.get("unit_cell")
        if unit_cell is not None:
            lattice = np.asarray(unit_cell["lattice"], dtype=float)
            visual_pt = np.asarray(center["point_cart"], dtype=float)
            diff_frac = (point - visual_pt) @ np.linalg.inv(lattice)
            snapped = point - np.round(diff_frac) @ lattice
            if np.linalg.norm(matrix @ snapped + translation - snapped) < 1e-8:
                point = snapped

    return {"point_cart": point}


def operation_angle_deg(operation: dict) -> float | None:
    angle = operation.get("angle_deg")
    if angle is not None:
        return float(angle)
    kind = str(operation["kind"])
    matrix = operation.get("matrix_cart")
    if matrix is None:
        return None
    rotation = operation_rotation_matrix(operation)
    if rotation is None:
        return None
    return rotation_angle_deg(rotation)


def operation_rotation_matrix(operation: dict) -> np.ndarray | None:
    kind = str(operation["kind"])
    matrix = operation.get("matrix_cart")
    if matrix is None:
        return None
    matrix = np.asarray(matrix, dtype=float)
    if "rotoinversion" in kind:
        return -matrix
    if kind.startswith(("rotation", "screw")):
        return matrix
    return None


def rotation_axis_from_matrix(rotation: np.ndarray) -> np.ndarray | None:
    values, vectors = np.linalg.eig(np.asarray(rotation, dtype=float))
    index = int(np.argmin(np.abs(values - 1.0)))
    if np.abs(values[index] - 1.0) > 1e-5:
        return None
    return normalize(np.real(vectors[:, index]))


def rotation_angle_deg(rotation: np.ndarray) -> float | None:
    trace = float(np.trace(rotation))
    cos_angle = np.clip((trace - 1.0) / 2.0, -1.0, 1.0)
    angle = float(np.degrees(np.arccos(cos_angle)))
    if abs(angle) < 1e-8:
        return 0.0
    return angle


def signed_rotation_angle_from_matrix(rotation: np.ndarray, axis_direction: np.ndarray) -> float:
    rotation = np.asarray(rotation, dtype=float)
    axis = normalize(axis_direction)
    sin_angle = 0.5 * np.dot(
        axis,
        np.array(
            [
                rotation[2, 1] - rotation[1, 2],
                rotation[0, 2] - rotation[2, 0],
                rotation[1, 0] - rotation[0, 1],
            ]
        ),
    )
    cos_angle = np.clip((np.trace(rotation) - 1.0) / 2.0, -1.0, 1.0)
    if np.isclose(cos_angle, -1.0, atol=1e-8):
        return float(np.pi)
    return float(np.arctan2(sin_angle, cos_angle))


def build_operation_path(
    start: np.ndarray,
    target: np.ndarray,
    operation: dict,
    *,
    axis: dict | None,
    plane: dict | None,
    center: dict | None,
    angle_override: float | None = None,
) -> dict:
    kind = str(operation["kind"])
    axis = effective_rotation_axis(operation, axis, center)
    if np.linalg.norm(target - start) < 1e-10:
        return translation_path(start, target)
    if kind.startswith("screw"):
        return screw_path(start, target, operation, axis, angle_override=angle_override)
    if "glide" in kind:
        return glide_path(start, target, plane)
    if "rotoinversion" in kind or "rotoreflection" in kind or "improper" in kind:
        return improper_path(start, target, operation, axis, plane, center, angle_override=angle_override)
    if kind.startswith("rotation"):
        return rotation_path(start, target, operation, axis, angle_override=angle_override)
    if kind == "mirror":
        return mirror_path(start, target, plane)
    if kind == "inversion":
        return inversion_path(start, target, center)
    return translation_path(start, target)


def rotation_path(
    start: np.ndarray,
    target: np.ndarray,
    operation: dict,
    axis: dict | None,
    *,
    angle_override: float | None = None,
) -> dict:
    angle_deg = operation_angle_deg(operation)
    if axis is None or angle_deg is None:
        return translation_path(start, target)
    axis_point = np.asarray(axis["point_cart"], dtype=float)
    axis_direction = normalize(np.asarray(axis["direction_cart"], dtype=float))
    angle = (
        angle_override
        if angle_override is not None
        else signed_angle_to_target(start, target, axis_point, axis_direction, angle_deg)
    )
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


def screw_path(
    start: np.ndarray,
    target: np.ndarray,
    operation: dict,
    axis: dict | None,
    *,
    angle_override: float | None = None,
) -> dict:
    rotated_path = rotation_path(start, target, operation, axis, angle_override=angle_override)
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
    *,
    angle_override: float | None = None,
) -> dict:
    axis = effective_rotation_axis(operation, axis, center)
    rotated = rotation_path(start, target, operation, axis, angle_override=angle_override)
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
