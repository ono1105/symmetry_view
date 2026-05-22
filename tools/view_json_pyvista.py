from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ModuleNotFoundError:
    from tools import _bootstrap  # noqa: F401

import pyvista as pv

from crystal_viewer.viewer.cli_animation import run_animation
from crystal_viewer.viewer.cli_helpers import (
    add_title,
    parse_selected_atoms,
    print_elements,
    print_mapping,
    print_operations,
)
from crystal_viewer.viewer.operation_lookup import (
    has_element_index,
)
from crystal_viewer.viewer.scene_rendering import (
    add_animated_atoms,
    add_atoms,
    add_displacements,
    add_unit_cell,
)
from crystal_viewer.viewer.symmetry_elements import (
    add_symmetry_elements,
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


if __name__ == "__main__":
    raise SystemExit(main())
