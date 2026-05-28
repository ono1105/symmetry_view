from __future__ import annotations

import numpy as np
import pyvista as pv

from crystal_viewer.geometry import normalize
from crystal_viewer.viewer.animation import (
    improper_inversion_center,
    improper_reflection_plane,
    preferred_improper_mode,
    render_source_kind,
    select_animation_context,
)
from crystal_viewer.viewer.display_atoms import display_point_cart, display_scene_span
from crystal_viewer.viewer.operation_lookup import (
    operation_by_index,
    selected_elements,
    selected_mapping,
)


def add_symmetry_elements(
    plotter: pv.Plotter,
    render_data: dict,
    atom_mappings: dict | None,
    *,
    operation_index: int | None,
    element_index: int | None = None,
    display_mode: str = "source",
    cell_origin_mode: str = "center",
    improper_mode: str = "auto",
) -> list:
    axes, planes, centers = display_symmetry_elements(
        render_data,
        atom_mappings,
        operation_index,
        element_index,
        improper_mode=improper_mode,
    )
    return add_symmetry_element_actors(
        plotter,
        render_data,
        axes,
        planes,
        centers,
        display_mode=display_mode,
        cell_origin_mode=cell_origin_mode,
    )


def add_symmetry_element_actors(
    plotter: pv.Plotter,
    render_data: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
    *,
    display_mode: str = "source",
    cell_origin_mode: str = "center",
) -> list:
    actors = []
    span = display_scene_span(render_data, display_mode, cell_origin_mode)
    axis_length = max(span * 0.75, 1.0)
    plane_scale = max(span * 0.45, 0.8)

    for axis in axes:
        point = display_point_cart(render_data, axis["point_cart"], display_mode, cell_origin_mode)
        direction = normalize(np.asarray(axis["direction_cart"], dtype=float))
        line = pv.Line(point - axis_length * direction, point + axis_length * direction)
        actors.append(plotter.add_mesh(line, color="#58d68d", line_width=6))

    for plane in planes:
        point = display_point_cart(render_data, plane["point_cart"], display_mode, cell_origin_mode)
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
        point = display_point_cart(render_data, center["point_cart"], display_mode, cell_origin_mode)
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
