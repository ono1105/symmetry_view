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
    HIGHLIGHT_RADIUS_SCALE,
    atom_color,
    color_to_rgb,
    display_atom_radius,
)
from crystal_viewer.viewer.animation import (
    animation_paths,
    build_operation_path,
    custom_operation_speed_multiplier,
    effective_rotation_axis,
    evaluate_path,
    improper_inversion_center,
    improper_reflection_plane,
    normalize,
    operation_speed_multiplier,
    path_applies_to_display_item,
    preferred_improper_mode,
    render_source_kind,
    select_animation_context,
    update_animated_atoms,
)
from crystal_viewer.viewer.display_atoms import (
    display_atom_instances,
    display_fractional_shifts,
    display_mode_margin,
    display_scene_center,
    display_scene_span,
    is_primary_centered_image,
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
from crystal_viewer.viewer.scene_rendering import (
    add_animated_atoms,
    add_atoms,
    add_displacements,
    add_unit_cell,
)
from crystal_viewer.viewer.symmetry_elements import (
    add_symmetry_element_actors,
    add_symmetry_elements,
    display_symmetry_elements,
    visual_improper_elements,
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

if __name__ == "__main__":
    raise SystemExit(main())
