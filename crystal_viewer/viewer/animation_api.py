from __future__ import annotations

from typing import Any

import numpy as np

from crystal_viewer.json_export import to_jsonable
from crystal_viewer.source_kinds import SOURCE_KIND_MOLECULE, normalize_source_kind
from crystal_viewer.viewer.animation_context import animation_paths, display_equivalent_operation_context
from crystal_viewer.viewer.custom_animation import build_custom_animation_paths
from crystal_viewer.viewer.animation_path import (
    maximum_travel_distance,
    normalized_animation_duration_seconds,
)
from crystal_viewer.viewer.display_atoms import display_atom_instances, display_scene_span
from crystal_viewer.viewer.operation_lookup import operation_by_index, selected_mapping
from crystal_viewer.viewer.operation_labels import (
    is_pure_translation_operation,
    operation_focus_point_cart,
    operation_view_direction_cart,
    visual_translation_direction_cart,
)
from crystal_viewer.viewer.symmetry_elements import display_symmetry_elements, glide_translation_cart


ANIMATION_PATH_SCHEMA_VERSION = 1
ANIMATION_COORDINATE_SPACE = "cartesian"
CRYSTAL_PERIODIC_IMAGE_POLICY = "transform_with_source"
MOLECULE_PERIODIC_IMAGE_POLICY = "not_applicable"


def animation_path_response(
    render_data: dict,
    atom_mappings: dict | None,
    operation_index: int,
    *,
    scope: str = "displayed",
    selected_atoms: tuple[int, ...] = (),
    improper_mode: str = "auto",
    display_mode: str = "source",
    cell_origin_mode: str = "center",
    include_boundary_images: bool = False,
    animation_boundary_mode: str = "continuous",
) -> dict[str, Any]:
    operation = operation_by_index(render_data.get("operations", []), operation_index)
    if operation is None:
        raise ValueError(f"Operation index not found: {operation_index}")
    mapping = selected_mapping(atom_mappings, operation_index)
    if mapping is None:
        raise ValueError(f"Atom mapping not found for operation: {operation_index}")

    source_kind = normalize_source_kind(
        str((render_data.get("metadata") or {}).get("mode") or "crystal")
    )
    animation_scope, effective_selected_atoms, representative_atom, unit_cell_only = _scope_options(
        render_data,
        scope,
        selected_atoms,
    )
    paths = animation_paths(
        render_data,
        operation,
        mapping,
        animation_scope=animation_scope,
        representative_atom=representative_atom,
        selected_atoms=effective_selected_atoms,
        improper_mode=improper_mode,
        display_mode=display_mode,
        cell_origin_mode=cell_origin_mode,
    )
    entries_by_source = {
        int(entry["source_atom"]): entry
        for entry in mapping.get("entries", [])
    }
    items = []
    for source_atom, path in sorted(paths.items()):
        public_path = serialize_animation_path(path)
        if unit_cell_only:
            public_path["unit_cell_only"] = True
        entry = entries_by_source.get(int(source_atom), {})
        items.append(
            {
                "source_atom": int(source_atom),
                "target_atom": entry.get("target_atom"),
                "path": public_path,
            }
        )

    travel = maximum_travel_distance(
        render_data,
        paths,
        display_mode=display_mode,
        cell_origin_mode=cell_origin_mode,
        include_boundary_images=include_boundary_images,
        unit_cell_only=unit_cell_only,
    )

    return {
        "schema_version": ANIMATION_PATH_SCHEMA_VERSION,
        "source_kind": source_kind,
        "coordinate_space": ANIMATION_COORDINATE_SPACE,
        "periodic_image_policy": (
            MOLECULE_PERIODIC_IMAGE_POLICY
            if source_kind == SOURCE_KIND_MOLECULE
            else CRYSTAL_PERIODIC_IMAGE_POLICY
        ),
        "operation_index": int(operation_index),
        "maximum_travel_distance": travel,
        "animation_duration_seconds": normalized_animation_duration_seconds(
            travel,
            display_scene_span(render_data, display_mode, cell_origin_mode),
        ),
        "boundary": animation_boundary_context(
            render_data,
            animation_boundary_mode=animation_boundary_mode,
            cell_origin_mode=cell_origin_mode,
        ),
        "scope": scope,
        "paths": items,
    }


def serialize_animation_path(path: dict) -> dict[str, Any]:
    """Convert an internal NumPy/radian path to the public JSON schema."""
    result = {}
    for key, value in path.items():
        if key == "angle":
            result["angle_deg"] = float(np.rad2deg(value))
        elif key == "segments":
            result[key] = [serialize_animation_path(segment) for segment in value]
        else:
            result[key] = to_jsonable(value)
    return result


def custom_animation_path_response(
    render_data: dict,
    atom_mappings: dict | None,
    request: dict,
    *,
    improper_mode: str = "auto",
    display_mode: str = "source",
    cell_origin_mode: str = "center",
    include_boundary_images: bool = False,
    animation_boundary_mode: str = "continuous",
) -> dict[str, Any]:
    paths = build_custom_animation_paths(
        render_data, atom_mappings, request, improper_mode=improper_mode,
        display_mode=display_mode, cell_origin_mode=cell_origin_mode,
    )
    items = [{"source_atom": source, "path": serialize_animation_path(path)} for source, path in sorted(paths.items())]
    maximum = maximum_travel_distance(
        render_data,
        paths,
        display_mode=display_mode,
        cell_origin_mode=cell_origin_mode,
        include_boundary_images=include_boundary_images,
    )
    return {
        "schema_version": ANIMATION_PATH_SCHEMA_VERSION,
        "coordinate_space": ANIMATION_COORDINATE_SPACE,
        "animate_id": request.get("animate_id"),
        "maximum_travel_distance": maximum,
        "animation_duration_seconds": normalized_animation_duration_seconds(
            maximum, display_scene_span(render_data, display_mode, cell_origin_mode)
        ),
        "boundary": animation_boundary_context(
            render_data,
            animation_boundary_mode=animation_boundary_mode,
            cell_origin_mode=cell_origin_mode,
        ),
        "paths": items,
    }


def animation_boundary_context(
    render_data: dict,
    *,
    animation_boundary_mode: str,
    cell_origin_mode: str,
) -> dict[str, Any]:
    unit_cell = render_data.get("unit_cell")
    if animation_boundary_mode != "wrap" or unit_cell is None:
        return {"mode": "continuous"}
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    try:
        inverse_lattice = np.linalg.inv(lattice)
    except np.linalg.LinAlgError:
        return {"mode": "continuous"}
    return {
        "mode": "wrap",
        "coordinate_space": ANIMATION_COORDINATE_SPACE,
        "cell_origin_mode": "corner" if cell_origin_mode == "corner" else "center",
        "cart_to_cell": to_jsonable(inverse_lattice),
        "cell_to_cart": to_jsonable(lattice),
        "boundary_epsilon": 1e-9,
    }


def symmetry_elements_response(
    render_data: dict,
    atom_mappings: dict | None,
    operation_index: int,
    *,
    improper_mode: str = "auto",
    display_mode: str = "source",
    cell_origin_mode: str = "center",
) -> dict[str, Any]:
    operation = operation_by_index(render_data.get("operations", []), operation_index)
    if operation is None:
        raise ValueError(f"Operation index not found: {operation_index}")
    axes, planes, centers = display_symmetry_elements(
        render_data,
        atom_mappings,
        operation_index,
        None,
        improper_mode=improper_mode,
    )
    mapping = selected_mapping(atom_mappings, operation_index)
    glide_translation = (
        glide_translation_cart(render_data, operation, planes[0], mapping=mapping)
        if planes and "glide" in str(operation.get("kind", ""))
        else None
    )
    _, axis, plane, center = display_equivalent_operation_context(
        render_data,
        operation,
        axes[0] if axes else None,
        planes[0] if planes else None,
        centers[0] if centers else None,
        display_mode,
        cell_origin_mode,
    )
    view_direction = (
        visual_translation_direction_cart(render_data, operation, atom_mappings)
        if is_pure_translation_operation(operation)
        else None
    )
    if view_direction is None:
        view_direction = operation_view_direction_cart(render_data, operation, axes, planes, centers)
    focus_point = operation_focus_point_cart(
        render_data,
        operation,
        axes,
        planes,
        centers,
        display_mode,
        cell_origin_mode,
    )
    return {
        "schema_version": ANIMATION_PATH_SCHEMA_VERSION,
        "coordinate_space": ANIMATION_COORDINATE_SPACE,
        "operation_index": int(operation_index),
        "axes": to_jsonable([axis] if axis is not None else []),
        "planes": to_jsonable([plane] if plane is not None else []),
        "centers": to_jsonable([center] if center is not None else []),
        "glide_translation_cart": to_jsonable(glide_translation),
        "view_direction_cart": to_jsonable(view_direction),
        "focus_point_cart": to_jsonable(focus_point),
    }


def _scope_options(
    render_data: dict,
    scope: str,
    selected_atoms: tuple[int, ...],
) -> tuple[str, tuple[int, ...], int | None, bool]:
    atom_indices = tuple(int(atom["index"]) for atom in render_data.get("atoms", []))
    effective_selected_atoms = tuple(int(index) for index in selected_atoms)
    animation_scope = scope
    unit_cell_only = scope in ("selected", "unit_cell", "representative")
    if scope in ("displayed", "unit_cell"):
        animation_scope = "selected"
        effective_selected_atoms = atom_indices
    elif scope == "selected_displayed":
        animation_scope = "selected"
    representative_atom = (
        effective_selected_atoms[0]
        if scope in ("selected", "selected_displayed") and effective_selected_atoms
        else None
    )
    return animation_scope, effective_selected_atoms, representative_atom, unit_cell_only
