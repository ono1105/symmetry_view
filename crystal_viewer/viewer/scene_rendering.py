from __future__ import annotations

import numpy as np
import pyvista as pv

from crystal_viewer.viewer.atom_style import ATOM_MESH_STYLE, atom_color, display_atom_radius
from crystal_viewer.viewer.atom_instances import element_instance_batches
from crystal_viewer.viewer.display_atoms import display_atom_instances, scene_span
from crystal_viewer.viewer.glyph_atoms import build_element_glyph_preview
from crystal_viewer.viewer.operation_lookup import selected_mapping


VIEWER_LIGHT_BACKGROUND_COLOR = "#ffffff"
VIEWER_DARK_BACKGROUND_COLOR = "#101216"
VIEWER_LIGHT_TEXT_COLOR = "#111827"
VIEWER_DARK_TEXT_COLOR = "#eef2f7"
AXIS_A_COLOR = "#ff0000"
AXIS_B_COLOR = "#00b000"
AXIS_C_COLOR = "#2468ff"


def viewer_background_color(background_mode: str) -> str:
    return VIEWER_DARK_BACKGROUND_COLOR if background_mode == "dark" else VIEWER_LIGHT_BACKGROUND_COLOR


def viewer_text_color(background_mode: str) -> str:
    return VIEWER_DARK_TEXT_COLOR if background_mode == "dark" else VIEWER_LIGHT_TEXT_COLOR


def setup_viewer_lighting(plotter: pv.Plotter, *, background_mode: str = "light") -> None:
    plotter.set_background(viewer_background_color(background_mode))
    try:
        plotter.remove_all_lights()
    except Exception:
        pass
    try:
        plotter.add_light(
            pv.Light(
                light_type="headlight",
                color="#ffffff",
                intensity=0.55,
            )
        )
        plotter.add_light(
            pv.Light(
                light_type="camera light",
                position=(-3.5, 4.0, 5.5),
                focal_point=(0.0, 0.0, 0.0),
                color="#ffffff",
                intensity=0.72,
                positional=True,
                cone_angle=80.0,
                exponent=1.0,
            )
        )
        plotter.add_light(
            pv.Light(
                light_type="camera light",
                position=(4.0, -3.5, 3.0),
                focal_point=(0.0, 0.0, 0.0),
                color="#ffffff",
                intensity=0.28,
                positional=True,
                cone_angle=100.0,
                exponent=1.0,
            )
        )
    except Exception:
        pass
    try:
        plotter.enable_shadows()
    except Exception:
        pass


def add_orientation_axes(plotter: pv.Plotter, *, unit_cell: bool = False) -> None:
    labels = ("a", "b", "c") if unit_cell else ("X", "Y", "Z")
    plotter.add_axes(
        x_color=AXIS_A_COLOR,
        y_color=AXIS_B_COLOR,
        z_color=AXIS_C_COLOR,
        xlabel=labels[0],
        ylabel=labels[1],
        zlabel=labels[2],
    )


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


def add_glyph_atoms(plotter: pv.Plotter, render_data: dict, *, display_mode: str = "expanded") -> None:
    for batch in element_instance_batches(render_data, display_mode=display_mode):
        preview = build_element_glyph_preview(batch, render_data)
        color = atom_color({"element": batch.element, "atomic_number": batch.atomic_number})
        plotter.add_mesh(preview.glyph_mesh, color=color, **ATOM_MESH_STYLE)


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
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    vertices = vertices - (np.asarray([0.5, 0.5, 0.5], dtype=float) @ lattice)
    edge_colors = {
        (0, 1): AXIS_A_COLOR,
        (2, 4): AXIS_A_COLOR,
        (3, 5): AXIS_A_COLOR,
        (6, 7): AXIS_A_COLOR,
        (0, 2): AXIS_B_COLOR,
        (1, 4): AXIS_B_COLOR,
        (3, 6): AXIS_B_COLOR,
        (5, 7): AXIS_B_COLOR,
        (0, 3): AXIS_C_COLOR,
        (1, 5): AXIS_C_COLOR,
        (2, 6): AXIS_C_COLOR,
        (4, 7): AXIS_C_COLOR,
    }
    for start, end in unit_cell["edges"]:
        edge = (int(start), int(end))
        line = pv.Line(vertices[edge[0]], vertices[edge[1]])
        plotter.add_mesh(line, color=edge_colors.get(edge, "#d6dde6"), line_width=3)


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
