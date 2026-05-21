from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ModuleNotFoundError:
    from tools import _bootstrap  # noqa: F401

import numpy as np
import pyvista as pv

from crystal_viewer.viewer.atom_style import (
    ATOM_MESH_STYLE,
    atom_color,
    atom_radius,
    color_to_rgb,
    display_atom_radius,
    display_radius_scale,
    element_radius_angstrom,
    normalize_hex_color,
)
from crystal_viewer.viewer.display_atoms import (
    display_atom_instances,
    display_fractional_shifts,
    display_mode_margin,
    display_scene_center,
    display_scene_span,
    is_primary_centered_image,
    periodic_shifts,
    scene_span,
    source_boundary_fractional_shifts,
)
from crystal_viewer.viewer.operation_lookup import (
    filter_by_operation,
    has_element_index,
    operation_by_index,
    selected_elements,
    selected_mapping,
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
    parser.add_argument(
        "--animation-speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier. Use 0.5 for half speed or 2.0 for double speed.",
    )
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
        "--selected-atom",
        type=int,
        default=None,
        help="Animate only this source atom index. Static atoms remain visible.",
    )
    parser.add_argument(
        "--selected-atoms",
        nargs="+",
        default=None,
        help="Animate only these source atom indices. Accepts spaces or commas, e.g. 0 3 8 or 0,3,8.",
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
        return 0

    if args.animate and args.operation is None:
        parser.error("--animate requires --operation")
    animation_scope = args.animation_scope
    representative_atom = args.representative_atom
    selected_atoms = parse_selected_atoms(args.selected_atoms)
    if args.selected_atom is not None:
        selected_atoms = tuple((*selected_atoms, args.selected_atom))
    if selected_atoms:
        animation_scope = "selected"
        representative_atom = representative_atom if representative_atom is not None else selected_atoms[0]
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
            atom_mappings,
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
            speed=args.animation_speed,
            output_path=args.animation_output,
            element_index=args.element_index,
            animation_scope=animation_scope,
            representative_atom=representative_atom,
            selected_atoms=selected_atoms,
        )
    elif args.screenshot is not None:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        plotter.show(screenshot=str(args.screenshot), auto_close=True)
        print(f"Wrote {args.screenshot}")
    else:
        plotter.show()

    return 0


def add_atoms(plotter: pv.Plotter, render_data: dict, *, display_mode: str = "expanded") -> None:
    for item in display_atom_instances(render_data, display_mode=display_mode):
        atom = item["atom"]
        center = item["cart"]
        radius = display_atom_radius(atom, render_data)
        color = atom_color(atom)
        sphere = pv.Sphere(
            radius=radius,
            center=center,
            theta_resolution=24,
            phi_resolution=16,
        )
        plotter.add_mesh(sphere, color=color, **ATOM_MESH_STYLE)


def add_animated_atoms(
    plotter: pv.Plotter,
    render_data: dict,
    *,
    display_mode: str = "expanded",
    theta_resolution: int = 16,
    phi_resolution: int = 10,
    smooth_shading: bool = True,
) -> list[dict]:
    animated = []
    for item in display_atom_instances(render_data, display_mode=display_mode):
        atom = item["atom"]
        center = item["cart"]
        radius = display_atom_radius(atom, render_data)
        color = atom_color(atom)
        base = pv.Sphere(
            radius=radius,
            center=(0.0, 0.0, 0.0),
            theta_resolution=theta_resolution,
            phi_resolution=phi_resolution,
        )
        mesh = base.copy()
        mesh_style = dict(ATOM_MESH_STYLE)
        mesh_style["smooth_shading"] = smooth_shading
        actor = plotter.add_mesh(mesh, color=color, **mesh_style)
        actor.SetPosition(*center)
        animated.append(
            {
                "atom": atom,
                "display_shift_frac": item["display_shift_frac"],
                "display_shift_cart": item["display_shift_cart"],
                "is_primary_image": item.get("is_primary_image", True),
                "base_points": base.points.copy(),
                "mesh": mesh,
                "actor": actor,
            }
        )
    return animated


def add_unit_cell(plotter: pv.Plotter, unit_cell: dict) -> None:
    vertices = np.asarray(unit_cell["vertices_cart"], dtype=float)
    edge_colors = {
        (0, 1): "#ff0000",
        (2, 4): "#ff0000",
        (3, 5): "#ff0000",
        (6, 7): "#ff0000",
        (0, 2): "#00b000",
        (1, 4): "#00b000",
        (3, 6): "#00b000",
        (5, 7): "#00b000",
        (0, 3): "#2468ff",
        (1, 5): "#2468ff",
        (2, 6): "#2468ff",
        (4, 7): "#2468ff",
    }
    for start, end in unit_cell["edges"]:
        edge = (int(start), int(end))
        line = pv.Line(vertices[edge[0]], vertices[edge[1]])
        plotter.add_mesh(line, color=edge_colors.get(edge, "#d6dde6"), line_width=3)


def add_symmetry_elements(
    plotter: pv.Plotter,
    render_data: dict,
    atom_mappings: dict | None,
    *,
    operation_index: int | None,
    element_index: int | None = None,
    display_mode: str = "source",
    improper_mode: str = "auto",
) -> list:
    axes, planes, centers = display_symmetry_elements(
        render_data,
        atom_mappings,
        operation_index,
        element_index,
        improper_mode=improper_mode,
    )
    return add_symmetry_element_actors(plotter, render_data, axes, planes, centers, display_mode=display_mode)


def add_symmetry_element_actors(
    plotter: pv.Plotter,
    render_data: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
    *,
    display_mode: str = "source",
) -> list:
    actors = []
    span = display_scene_span(render_data, display_mode)
    axis_length = max(span * 0.75, 1.0)
    plane_scale = max(span * 0.45, 0.8)

    for axis in axes:
        point = np.asarray(axis["point_cart"], dtype=float)
        direction = normalize(np.asarray(axis["direction_cart"], dtype=float))
        line = pv.Line(point - axis_length * direction, point + axis_length * direction)
        actors.append(plotter.add_mesh(line, color="#58d68d", line_width=6))

    for plane in planes:
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
        actors.append(
            plotter.add_mesh(
                mesh,
                color="#5dade2",
                opacity=0.35,
                show_edges=True,
                edge_color="#aed6f1",
            )
        )

    for center in centers:
        point = np.asarray(center["point_cart"], dtype=float)
        cube = pv.Cube(
            center=point,
            x_length=max(span * 0.055, 0.12),
            y_length=max(span * 0.055, 0.12),
            z_length=max(span * 0.055, 0.12),
        )
        actors.append(plotter.add_mesh(cube, color="#ff5f57", opacity=0.8, show_edges=True))

    return actors


def display_symmetry_elements(
    render_data: dict,
    atom_mappings: dict | None,
    operation_index: int | None,
    element_index: int | None,
    *,
    improper_mode: str = "auto",
) -> tuple[list[dict], list[dict], list[dict]]:
    operation = operation_by_index(render_data["operations"], operation_index)
    if operation_index is not None and element_index is None and atom_mappings is not None:
        mapping = selected_mapping(atom_mappings, operation_index)
        if operation is not None and mapping is not None:
            atoms_by_index = {atom["index"]: atom for atom in render_data["atoms"]}
            axis, plane, center, _, _, _ = select_animation_context(
                render_data,
                operation,
                mapping,
                atoms_by_index,
                element_index=None,
                representative_atom=None,
            )
            return visual_improper_elements(
                render_data,
                operation,
                [axis] if axis is not None else [],
                [plane] if plane is not None else [],
                [center] if center is not None else [],
                improper_mode=improper_mode,
            )

    axes, planes, centers = (
        selected_elements(render_data["axes"], operation_index, element_index),
        selected_elements(render_data["planes"], operation_index, element_index),
        selected_elements(render_data["centers"], operation_index, element_index),
    )
    if operation is None:
        return axes, planes, centers
    return visual_improper_elements(
        render_data,
        operation,
        axes,
        planes,
        centers,
        improper_mode=improper_mode,
    )


def visual_improper_elements(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
    *,
    improper_mode: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    kind = str(operation.get("kind", ""))
    if "rotoinversion" not in kind and "rotoreflection" not in kind and "improper" not in kind:
        return axes, planes, centers

    mode = preferred_improper_mode(operation, improper_mode, render_source_kind(render_data))
    axis = axes[0] if axes else None
    if mode == "rotoreflection" and axis is not None and not planes:
        plane = improper_reflection_plane(axis)
        if plane is not None:
            planes = [plane]
    elif mode == "rotoinversion" and axis is not None and not centers:
        center = improper_inversion_center(axis)
        if center is not None:
            centers = [center]
    return axes, planes, centers


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
    speed: float,
    output_path: Path | None,
    element_index: int | None,
    animation_scope: str,
    representative_atom: int | None,
    selected_atoms: tuple[int, ...],
) -> None:
    if animated_atoms is None:
        print("Animation skipped because atoms are hidden.")
        return
    operation = operation_by_index(render_data["operations"], operation_index)
    mapping = selected_mapping(atom_mappings, operation_index)
    if operation is None or mapping is None:
        print("Animation requires a valid --operation with atom mapping.")
        return
    available_atoms = {entry["source_atom"] for entry in mapping["entries"]}
    if representative_atom is not None and representative_atom not in available_atoms:
        print(f"Animation skipped because --representative-atom {representative_atom} is not in this mapping.")
        return
    missing_atoms = sorted(set(selected_atoms) - available_atoms)
    if missing_atoms:
        print(f"Animation skipped because selected atoms are not in this mapping: {missing_atoms}")
        return

    frames = max(frame_count, 2)
    playback_fps = effective_animation_fps(fps, speed)
    paths = animation_paths(
        render_data,
        operation,
        mapping,
        element_index=element_index,
        animation_scope=animation_scope,
        representative_atom=representative_atom,
        selected_atoms=selected_atoms,
    )
    if not paths:
        print("Animation skipped because no atom path could be built. Check --representative-atom.")
        return

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plotter.open_gif(str(output_path), fps=playback_fps)
        plotter.show(auto_close=False, interactive_update=True)
        for frame in range(frames):
            update_animated_atoms(animated_atoms, paths, frame / (frames - 1))
            plotter.write_frame()
        plotter.close()
        print(f"Wrote {output_path}")
        return

    plotter.show(auto_close=False, interactive_update=True)
    delay = 1.0 / playback_fps
    for frame in range(frames):
        update_animated_atoms(animated_atoms, paths, frame / (frames - 1))
        plotter.update()
        time.sleep(delay)
    plotter.show()


def effective_animation_fps(fps: float, speed: float) -> float:
    return max(float(fps), 1.0) * max(float(speed), 0.05)


def parse_selected_atoms(values: list[str] | None) -> tuple[int, ...]:
    if not values:
        return ()
    selected = []
    for value in values:
        for item in str(value).split(","):
            item = item.strip()
            if item:
                selected.append(int(item))
    return tuple(dict.fromkeys(selected))


def update_animated_atoms(animated_atoms: list[dict], paths: dict[int, dict], s: float) -> None:
    for item in animated_atoms:
        atom = item["atom"]
        path = paths.get(atom["index"])
        display_shift = item["display_shift_cart"]
        center = np.asarray(atom["cart"], dtype=float) + display_shift
        if path is not None and path_applies_to_display_item(path, item):
            center = evaluate_path(path, s, start_override=np.asarray(atom["cart"], dtype=float) + display_shift)
        actor = item.get("actor")
        if actor is not None:
            actor.SetPosition(*center)


def path_applies_to_display_item(path: dict, item: dict) -> bool:
    if not path.get("unit_cell_only"):
        return True
    return bool(item.get("is_primary_image", False))


def animation_paths(
    render_data: dict,
    operation: dict,
    mapping: dict,
    *,
    element_index: int | None = None,
    animation_scope: str = "all",
    representative_atom: int | None = None,
    selected_atoms: tuple[int, ...] = (),
    improper_mode: str = "auto",
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

    translation_override = shared_step_translation(
        render_data,
        operation,
        atoms_by_index,
        reference_entry,
        axis,
        plane,
        shared_shift,
        shared_angle,
    )

    paths = {}
    entries = mapping["entries"]
    if animation_scope == "representative":
        entries = [reference_entry]
    elif animation_scope == "selected":
        selected_set = set(selected_atoms)
        entries = [entry for entry in entries if entry["source_atom"] in selected_set]

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
            translation_override=translation_override,
            improper_mode=improper_mode,
            source_kind=str(render_data.get("metadata", {}).get("mode", "")),
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
        score = animation_context_score(
            render_data,
            operation,
            mapping,
            atoms_by_index,
            context,
            threshold=best_score,
        )
        if score < best_score:
            best_score = score
            best_context = context
        if best_score <= 1e-10:
            break
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
    *,
    threshold: float = float("inf"),
) -> float:
    axis, plane, center, _, shared_shift, shared_angle = context
    reference_entry = context[3]
    translation_override = shared_step_translation(
        render_data,
        operation,
        atoms_by_index,
        reference_entry,
        axis,
        plane,
        shared_shift,
        shared_angle,
    )
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
            translation_override=translation_override,
            improper_mode="auto",
            source_kind=str(render_data.get("metadata", {}).get("mode", "")),
        )
        worst = max(worst, max_path_residual(path))
        if worst >= threshold:
            return worst
    return worst


def max_path_residual(path: dict) -> float:
    residual = 0.0
    stack = [path]
    while stack:
        current = stack.pop()
        if current["type"] == "sequential":
            stack.extend(current["segments"])
            continue
        target = current.get("target")
        if target is not None:
            endpoint = evaluate_path(current, 1.0)
            residual = max(residual, float(np.linalg.norm(np.asarray(target, dtype=float) - endpoint)))
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


def shared_step_translation(
    render_data: dict,
    operation: dict,
    atoms_by_index: dict[int, dict],
    reference_entry: dict | None,
    axis: dict | None,
    plane: dict | None,
    shared_shift: np.ndarray | None,
    shared_angle: float | None,
) -> np.ndarray | None:
    if reference_entry is None:
        return None
    reference_atom = atoms_by_index.get(reference_entry["source_atom"])
    if reference_atom is None:
        return None

    kind = str(operation["kind"])
    start = np.asarray(reference_atom["cart"], dtype=float)
    target = animation_target(
        render_data,
        start,
        reference_entry,
        operation,
        axis,
        plane,
        None,
        shared_shift=shared_shift,
    )

    if kind.startswith("screw"):
        if axis is None or shared_angle is None:
            return None
        rotated_end = rotate_about_axis(
            start,
            np.asarray(axis["point_cart"], dtype=float),
            normalize(np.asarray(axis["direction_cart"], dtype=float)),
            shared_angle,
        )
        return target - rotated_end

    if "glide" in kind:
        if plane is None:
            return None
        mirrored_end = reflect_point(
            start,
            np.asarray(plane["point_cart"], dtype=float),
            normalize(np.asarray(plane["normal_cart"], dtype=float)),
        )
        return target - mirrored_end

    return None


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
    return (frac + periodic_shifts(1)) @ lattice


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
    translation_override: np.ndarray | None = None,
    improper_mode: str = "auto",
    source_kind: str = "",
) -> dict:
    kind = str(operation["kind"])
    axis = effective_rotation_axis(operation, axis, center)
    geometric_kind = (
        kind.startswith(("rotation", "screw"))
        or kind in ("mirror", "inversion")
        or "glide" in kind
        or "rotoinversion" in kind
        or "rotoreflection" in kind
        or "improper" in kind
    )
    if not geometric_kind and np.linalg.norm(target - start) < 1e-10:
        return translation_path(start, target)
    if kind.startswith("screw"):
        return screw_path(
            start,
            target,
            operation,
            axis,
            angle_override=angle_override,
            translation_override=translation_override,
        )
    if "glide" in kind:
        return glide_path(start, target, plane, translation_override=translation_override)
    if "rotoinversion" in kind or "rotoreflection" in kind or "improper" in kind:
        return improper_path(
            start,
            target,
            operation,
            axis,
            plane,
            center,
            angle_override=angle_override,
            improper_mode=improper_mode,
            source_kind=source_kind,
        )
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
    if axis is None or (angle_deg is None and angle_override is None):
        return translation_path(start, target)
    axis_point = np.asarray(axis["point_cart"], dtype=float)
    axis_direction = normalize(np.asarray(axis["direction_cart"], dtype=float))
    angle = (
        angle_override
        if angle_override is not None
        else signed_angle_to_target(start, target, axis_point, axis_direction, angle_deg)
    )
    return {
        "type": "rotation",
        "start": start,
        "target": target,
        "axis_point": axis_point,
        "axis_direction": axis_direction,
        "angle": angle,
    }


def screw_path(
    start: np.ndarray,
    target: np.ndarray,
    operation: dict,
    axis: dict | None,
    *,
    angle_override: float | None = None,
    translation_override: np.ndarray | None = None,
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
        "type": "screw",
        "start": start,
        "target": target,
        "axis_point": rotated_path["axis_point"],
        "axis_direction": rotated_path["axis_direction"],
        "angle": rotated_path["angle"],
        "translation": target - rotated_end if translation_override is None else np.asarray(translation_override, dtype=float),
    }


def mirror_path(start: np.ndarray, target: np.ndarray, plane: dict | None) -> dict:
    if plane is None:
        return translation_path(start, target)
    point = np.asarray(plane["point_cart"], dtype=float)
    normal = normalize(np.asarray(plane["normal_cart"], dtype=float))
    return {
        "type": "mirror",
        "start": start,
        "target": target,
        "plane_point": point,
        "plane_normal": normal,
    }


def glide_path(
    start: np.ndarray,
    target: np.ndarray,
    plane: dict | None,
    *,
    translation_override: np.ndarray | None = None,
) -> dict:
    mirrored_path = mirror_path(start, target, plane)
    if mirrored_path["type"] != "mirror":
        return translation_path(start, target)
    mirrored_end = reflect_point(start, mirrored_path["plane_point"], mirrored_path["plane_normal"])
    return {
        "type": "glide",
        "start": start,
        "target": target,
        "plane_point": mirrored_path["plane_point"],
        "plane_normal": mirrored_path["plane_normal"],
        "translation": target - mirrored_end if translation_override is None else np.asarray(translation_override, dtype=float),
    }


def inversion_path(start: np.ndarray, target: np.ndarray, center: dict | None) -> dict:
    center_point = None if center is None else np.asarray(center["point_cart"], dtype=float)
    if center_point is None:
        return translation_path(start, target)
    return {
        "type": "inversion",
        "start": start,
        "target": target,
        "center": center_point,
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
    improper_mode: str = "auto",
    source_kind: str = "",
) -> dict:
    axis = effective_rotation_axis(operation, axis, center)
    mode = preferred_improper_mode(operation, improper_mode, source_kind)
    plane = plane or improper_reflection_plane(axis)
    center = center or improper_inversion_center(axis)
    if angle_override is None:
        angle_override = improper_rotation_angle(operation, axis, mode)
    rotated = rotation_path(start, target, operation, axis, angle_override=angle_override)
    if rotated["type"] != "rotation":
        if mode == "rotoinversion":
            return inversion_path(start, target, center)
        return mirror_path(start, target, plane)
    if mode == "rotoinversion":
        if center is None:
            return translation_path(start, target)
        return {
            "type": "rotoinversion",
            "start": start,
            "target": target,
            "axis_point": rotated["axis_point"],
            "axis_direction": rotated["axis_direction"],
            "angle": rotated["angle"],
            "center": np.asarray(center["point_cart"], dtype=float),
        }
    if plane is None:
        return translation_path(start, target)
    return {
        "type": "rotoreflection",
        "start": start,
        "target": target,
        "axis_point": rotated["axis_point"],
        "axis_direction": rotated["axis_direction"],
        "angle": rotated["angle"],
        "plane_point": np.asarray(plane["point_cart"], dtype=float),
        "plane_normal": normalize(np.asarray(plane["normal_cart"], dtype=float)),
    }


def preferred_improper_mode(operation: dict, requested: str, source_kind: str) -> str:
    if requested in ("rotoreflection", "rotoinversion"):
        return requested
    kind = str(operation.get("kind", ""))
    if "rotoreflection" in kind or "improper" in kind:
        return "rotoreflection" if source_kind == "molecule" else "rotoinversion"
    return "rotoinversion"


def render_source_kind(render_data: dict) -> str:
    return str((render_data.get("metadata") or {}).get("mode") or "crystal")


def improper_reflection_plane(axis: dict | None) -> dict | None:
    if axis is None:
        return None
    normal = normalize(np.asarray(axis["direction_cart"], dtype=float))
    basis1, basis2 = plane_basis_from_normal_cart(normal)
    return {
        "point_cart": axis["point_cart"],
        "normal_cart": normal,
        "basis1_cart": basis1,
        "basis2_cart": basis2,
        "label": "rotoreflection mirror plane",
        "operation_indices": axis.get("operation_indices", ()),
    }


def improper_inversion_center(axis: dict | None) -> dict | None:
    if axis is None:
        return None
    return {"point_cart": axis["point_cart"]}


def plane_basis_from_normal_cart(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    normal = normalize(normal)
    helper = np.array([1.0, 0.0, 0.0])
    if abs(float(np.dot(normal, helper))) > 0.9:
        helper = np.array([0.0, 1.0, 0.0])
    basis1 = normalize(np.cross(normal, helper))
    basis2 = normalize(np.cross(normal, basis1))
    return basis1, basis2


def improper_rotation_angle(operation: dict, axis: dict | None, mode: str) -> float | None:
    if axis is None or operation.get("matrix_cart") is None:
        return None
    matrix = np.asarray(operation["matrix_cart"], dtype=float)
    axis_direction = normalize(np.asarray(axis["direction_cart"], dtype=float))
    if mode == "rotoreflection":
        normal = axis_direction.reshape(3, 1)
        reflection = np.eye(3) - 2.0 * (normal @ normal.T)
        rotation = reflection @ matrix
    else:
        rotation = -matrix
    return signed_rotation_angle_from_matrix(rotation, axis_direction)


def translation_path(start: np.ndarray, target: np.ndarray) -> dict:
    return {"type": "linear", "start": start, "target": target}


def evaluate_path(path: dict, s: float, start_override: np.ndarray | None = None) -> np.ndarray:
    s = float(np.clip(s, 0.0, 1.0))
    path_type = path["type"]
    start = np.asarray(path["start"], dtype=float) if start_override is None else np.asarray(start_override, dtype=float)
    if path_type == "sequential":
        segments = path["segments"]
        segment_count = len(segments)
        index = min(int(s * segment_count), segment_count - 1)
        local_s = (s - index / segment_count) * segment_count
        return evaluate_path(segments[index], local_s, start_override=start_override if index == 0 else None)
    if path_type == "rotation":
        rotated = rotate_about_axis(
            start,
            path["axis_point"],
            path["axis_direction"],
            path["angle"] * s,
        )
        return rotated
    if path_type == "screw":
        if s <= 0.5:
            return rotate_about_axis(
                start,
                path["axis_point"],
                path["axis_direction"],
                path["angle"] * (2.0 * s),
            )
        rotated_end = rotate_about_axis(
            start,
            path["axis_point"],
            path["axis_direction"],
            path["angle"],
        )
        return rotated_end + np.asarray(path["translation"], dtype=float) * (2.0 * s - 1.0)
    if path_type == "mirror":
        mirrored = reflect_point(start, path["plane_point"], path["plane_normal"])
        return interpolate(start, mirrored, s)
    if path_type == "glide":
        mirrored = reflect_point(start, path["plane_point"], path["plane_normal"])
        if s <= 0.5:
            return interpolate(start, mirrored, 2.0 * s)
        return mirrored + np.asarray(path["translation"], dtype=float) * (2.0 * s - 1.0)
    if path_type == "inversion":
        inverted = 2.0 * path["center"] - start
        return interpolate(start, inverted, s)
    if path_type == "rotoinversion":
        if s <= 0.5:
            return rotate_about_axis(
                start,
                path["axis_point"],
                path["axis_direction"],
                path["angle"] * (2.0 * s),
            )
        rotated_end = rotate_about_axis(
            start,
            path["axis_point"],
            path["axis_direction"],
            path["angle"],
        )
        inverted = 2.0 * path["center"] - rotated_end
        return interpolate(rotated_end, inverted, 2.0 * s - 1.0)
    if path_type == "rotoreflection":
        if s <= 0.5:
            return rotate_about_axis(
                start,
                path["axis_point"],
                path["axis_direction"],
                path["angle"] * (2.0 * s),
            )
        rotated_end = rotate_about_axis(
            start,
            path["axis_point"],
            path["axis_direction"],
            path["angle"],
        )
        mirrored = reflect_point(rotated_end, path["plane_point"], path["plane_normal"])
        return interpolate(rotated_end, mirrored, 2.0 * s - 1.0)
    target = np.asarray(path["target"], dtype=float)
    if start_override is not None:
        target = target + (start - np.asarray(path["start"], dtype=float))
    return interpolate(start, target, s)


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


def normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm < 1e-12:
        return vector
    return vector / norm


if __name__ == "__main__":
    raise SystemExit(main())
