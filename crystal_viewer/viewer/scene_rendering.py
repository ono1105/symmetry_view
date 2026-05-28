from __future__ import annotations

import numpy as np
import pyvista as pv

from crystal_viewer.viewer.atom_style import ATOM_MESH_STYLE, atom_color, display_atom_radius
from crystal_viewer.viewer.atom_instances import element_instance_batches
from crystal_viewer.viewer.display_atoms import display_atom_instances, scene_span
from crystal_viewer.viewer.glyph_atoms import build_element_glyph_preview
from crystal_viewer.viewer.operation_lookup import selected_mapping


VIEWER_BACKGROUND_COLOR = "#ffffff"


def setup_viewer_lighting(plotter: pv.Plotter, *, background: str = VIEWER_BACKGROUND_COLOR) -> None:
    plotter.set_background(background)
    try:
        plotter.remove_all_lights()
    except Exception:
        pass
    try:
        main_light = pv.Light(
            position=(8.0, -10.0, 12.0),
            focal_point=(0.0, 0.0, 0.0),
            color="#ffffff",
            intensity=0.88,
            positional=True,
            cone_angle=70.0,
            exponent=1.0,
        )
        try:
            main_light.shadow_attenuation = 0.35
        except Exception:
            pass
        plotter.add_light(main_light)
        plotter.add_light(
            pv.Light(
                position=(-7.0, 8.0, 9.0),
                focal_point=(0.0, 0.0, 0.0),
                color="#ffffff",
                intensity=0.42,
                positional=True,
                cone_angle=95.0,
                exponent=1.0,
            )
        )
        plotter.add_light(
            pv.Light(
                position=(-9.0, -6.0, -7.0),
                focal_point=(0.0, 0.0, 0.0),
                color="#ffffff",
                intensity=0.24,
                positional=True,
                cone_angle=110.0,
                exponent=1.0,
            )
        )
    except Exception:
        pass
    try:
        plotter.enable_shadows()
    except Exception:
        pass


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
