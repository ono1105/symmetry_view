from __future__ import annotations

from fractions import Fraction

import numpy as np

from tools import view_json_pyvista as viewer


def operation_summaries(
    render_data: dict,
    atom_mappings: dict | None,
) -> tuple[list[dict], dict[int, tuple[list[dict], list[dict], list[dict]]]]:
    summaries = []
    element_context_cache = {}
    for operation in render_data["operations"]:
        summary_operation = dict(operation)
        visual_translation = visual_translation_direction_cart(render_data, operation, atom_mappings)
        if visual_translation is not None:
            summary_operation["_display_translation_cart"] = visual_translation.tolist()
        axes, planes, centers = viewer.display_symmetry_elements(
            render_data,
            atom_mappings,
            operation["index"],
            element_index=None,
        )
        element_context_cache[operation["index"]] = (axes, planes, centers)
        summaries.append(
            {
                "index": operation["index"],
                "label": operation["label"],
                "symbol": operation.get("symbol") or operation["label"],
                "display_symbol": display_operation_symbol(render_data, summary_operation, axes),
                "kind": operation["kind"],
                "order": operation.get("order"),
                "angle_deg": operation.get("angle_deg"),
                "element_summary": operation_element_summary(render_data, summary_operation, axes, planes, centers),
                "element_sort_key": operation_element_sort_key(render_data, summary_operation, axes, planes, centers),
                "direction_sort_key": operation_direction_sort_key(render_data, summary_operation, axes, planes, centers),
                "direction_label": operation_direction_label(render_data, summary_operation, axes, planes, centers),
                "direction_filter_label": operation_direction_filter_label(render_data, summary_operation, axes, planes, centers),
                "matrix_frac": operation.get("matrix_frac"),
                "translation_frac": operation.get("translation_frac"),
                "matrix_cart": operation.get("matrix_cart"),
                "translation_cart": operation.get("translation_cart"),
            }
        )
    return summaries, element_context_cache


def display_operation_symbol(render_data: dict, operation: dict, axes: list[dict]) -> str:
    symbol = operation.get("symbol") or operation["label"]
    if is_pure_translation_operation(operation):
        return "t"
    if "?" not in str(symbol):
        return str(symbol)
    if not str(operation["kind"]).startswith("screw") or not axes:
        return str(symbol)
    inferred = infer_screw_symbol(render_data, operation, axes[0])
    return inferred or str(symbol)


def infer_screw_symbol(render_data: dict, operation: dict, axis: dict) -> str | None:
    order = operation.get("order")
    matrix = operation.get("matrix_cart")
    translation = operation.get("translation_cart")
    unit_cell = render_data.get("unit_cell")
    if order is None or matrix is None or translation is None or unit_cell is None:
        return None

    point = np.asarray(axis["point_cart"], dtype=float)
    direction = viewer.normalize(np.asarray(axis["direction_cart"], dtype=float))
    moved = np.asarray(matrix, dtype=float) @ point + np.asarray(translation, dtype=float)
    displacement = moved - point
    projected = float(np.dot(displacement, direction))

    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac_direction = direction @ np.linalg.inv(lattice)
    primitive_frac = integer_index_vector(frac_direction)
    if primitive_frac is None:
        return None
    period = float(np.linalg.norm(primitive_frac @ lattice))
    if period < 1e-10:
        return None

    fraction = (projected / period) % 1.0
    screw = int(round(fraction * int(order))) % int(order)
    if screw == 0:
        return None
    return f"{order}_{screw}"


def operation_element_summary(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> str:
    parts = []
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        axis = effective_axis
        parts.append(
            f"{axis_direction_label(render_data, axis)} "
            f"@ {point_label(render_data, axis['point_cart'])}"
        )
    if planes:
        plane = planes[0]
        parts.append(
            f"{plane_normal_label(render_data, plane)} "
            f"@ {point_label(render_data, plane['point_cart'])}"
        )
    if centers and effective_axis is None:
        center = centers[0]
        parts.append(f"@ {point_label(render_data, center['point_cart'])}")
    translation_direction = translation_direction_label(render_data, operation)
    if translation_direction is not None and not parts:
        parts.append(translation_direction)
    return "; ".join(parts)


def operation_element_sort_key(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> str:
    direction = operation_direction_sort_key(render_data, operation, axes, planes, centers)
    point = operation_point_sort_key(render_data, operation, axes, planes, centers)
    return f"{direction}|{point}|{operation.get('symbol', '')}"


def operation_direction_sort_key(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> str:
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        return "axis:" + plain_index_label(axis_direction_label(render_data, effective_axis))
    if planes:
        return "plane:" + plain_index_label(plane_normal_label(render_data, planes[0]))
    translation_direction = translation_direction_label(render_data, operation)
    if translation_direction is not None:
        return "translation:" + plain_index_label(translation_direction)
    if centers:
        return "center"
    return "none"


def operation_direction_label(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> str:
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        return axis_direction_label(render_data, effective_axis)
    if planes:
        return plane_normal_label(render_data, planes[0])
    translation_direction = translation_direction_label(render_data, operation)
    if translation_direction is not None:
        return translation_direction
    if centers:
        return "center"
    return "none"


def operation_direction_filter_label(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> str:
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        return axis_direction_label_text(render_data, effective_axis)
    if planes:
        return plane_normal_label_text(render_data, planes[0])
    translation_direction = translation_direction_label_text(render_data, operation)
    if translation_direction is not None:
        return translation_direction
    if centers:
        return "center"
    return "none"


def operation_point_sort_key(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> str:
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        return point_sort_key(render_data, effective_axis["point_cart"])
    if planes:
        return point_sort_key(render_data, planes[0]["point_cart"])
    if centers:
        return point_sort_key(render_data, centers[0]["point_cart"])
    return ""


def operation_view_direction_cart(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
) -> np.ndarray | None:
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        return np.asarray(effective_axis["direction_cart"], dtype=float)
    if planes:
        return np.asarray(planes[0]["normal_cart"], dtype=float)
    return translation_direction_cart(operation)


def operation_focus_point_cart(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
    display_mode: str,
) -> np.ndarray:
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        return np.asarray(effective_axis["point_cart"], dtype=float)
    if planes:
        return np.asarray(planes[0]["point_cart"], dtype=float)
    if centers:
        return np.asarray(centers[0]["point_cart"], dtype=float)
    return viewer.display_scene_center(render_data, display_mode)


def custom_focus_point_cart(result: dict, render_data: dict, display_mode: str) -> np.ndarray | None:
    elements = result.get("elements") or {}
    for key in ("axes", "planes", "centers"):
        items = elements.get(key) or []
        if items:
            return np.asarray(items[0]["point_cart"], dtype=float)
    return None


def display_point_cart(render_data: dict, point_cart: list[float] | np.ndarray, display_mode: str) -> np.ndarray:
    point = np.asarray(point_cart, dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return point
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac = point @ np.linalg.inv(lattice)
    if display_mode == "source":
        wrapped = frac - np.floor(frac + 1e-9)
    else:
        wrapped = frac - np.round(frac)
        wrapped = np.where(wrapped >= 0.5 - 1e-9, wrapped - 1.0, wrapped)
    return wrapped @ lattice


def visual_translation_direction_cart(
    render_data: dict,
    operation: dict,
    atom_mappings: dict | None,
) -> np.ndarray | None:
    if not is_pure_translation_operation(operation):
        return None
    mapping = viewer.selected_mapping(atom_mappings, operation["index"])
    if mapping is None:
        return None
    paths = viewer.animation_paths(
        render_data,
        operation,
        mapping,
        animation_scope="representative",
    )
    if not paths:
        return None
    path = next(iter(paths.values()))
    start = np.asarray(path["start"], dtype=float)
    target = np.asarray(path["target"], dtype=float)
    displacement = target - start
    if np.linalg.norm(displacement) < 1e-10:
        return None
    return displacement


def translation_direction_label(render_data: dict, operation: dict) -> str | None:
    direction = translation_direction_cart(operation)
    if direction is None:
        return None
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(direction, bracket=("[", "]"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac_direction = direction @ np.linalg.inv(lattice)
    return integer_index_label(frac_direction, bracket=("[", "]"), orient_positive=False)


def translation_direction_label_text(render_data: dict, operation: dict) -> str | None:
    direction = translation_direction_cart(operation)
    if direction is None:
        return None
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(direction, bracket=("[", "]"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac_direction = direction @ np.linalg.inv(lattice)
    return integer_index_label_text(frac_direction, bracket=("[", "]"), orient_positive=False)


def translation_direction_cart(operation: dict) -> np.ndarray | None:
    if not is_pure_translation_operation(operation):
        return None
    display_translation = operation.get("_display_translation_cart")
    if display_translation is not None:
        direction = np.asarray(display_translation, dtype=float)
        if np.linalg.norm(direction) >= 1e-10:
            return direction
    translation = operation.get("translation_cart")
    if translation is None:
        return None
    direction = np.asarray(translation, dtype=float)
    if np.linalg.norm(direction) < 1e-10:
        return None
    return direction


def is_pure_translation_operation(operation: dict) -> bool:
    kind = str(operation.get("kind", ""))
    if "translation" not in kind:
        return False
    matrix = operation.get("matrix_cart")
    if matrix is None:
        return True
    return bool(np.allclose(np.asarray(matrix, dtype=float), np.eye(3), atol=1e-8))


def point_sort_key(render_data: dict, point_cart: list[float]) -> str:
    point = np.asarray(point_cart, dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        values = point
    else:
        lattice = np.asarray(unit_cell["lattice"], dtype=float)
        values = point @ np.linalg.inv(lattice)
        values = values - np.floor(values + 1e-9)
    return ",".join(f"{float(value):.6f}" for value in values)


def plain_index_label(label: str) -> str:
    return (
        label.replace("<span class=\"overline\">", "-")
        .replace("</span>", "")
        .replace("[", "")
        .replace("]", "")
        .replace("(", "")
        .replace(")", "")
    )


def effective_axis_from_operation(operation: dict, centers: list[dict]) -> dict | None:
    kind = str(operation["kind"])
    if "rotoinversion" not in kind and "rotoreflection" not in kind and "improper" not in kind:
        return None
    if not centers:
        return None
    center = centers[0]
    axis = viewer.effective_rotation_axis(operation, None, center)
    return axis


def axis_direction_label(render_data: dict, axis: dict) -> str:
    vector = np.asarray(axis["direction_cart"], dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(vector, bracket=("[", "]"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac_direction = vector @ np.linalg.inv(lattice)
    return integer_index_label(frac_direction, bracket=("[", "]"))


def axis_direction_label_text(render_data: dict, axis: dict) -> str:
    vector = np.asarray(axis["direction_cart"], dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(vector, bracket=("[", "]"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac_direction = vector @ np.linalg.inv(lattice)
    return integer_index_label_text(frac_direction, bracket=("[", "]"))


def plane_normal_label(render_data: dict, plane: dict) -> str:
    normal = np.asarray(plane["normal_cart"], dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(normal, bracket=("(", ")"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    # frac @ lattice is the Cartesian point.  Plane coefficients in fractional
    # coordinates are therefore proportional to lattice @ normal_cart.
    hkl = lattice @ normal
    return integer_index_label(hkl, bracket=("(", ")"))


def plane_normal_label_text(render_data: dict, plane: dict) -> str:
    normal = np.asarray(plane["normal_cart"], dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(normal, bracket=("(", ")"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    hkl = lattice @ normal
    return integer_index_label_text(hkl, bracket=("(", ")"))


def point_label(render_data: dict, point_cart: list[float]) -> str:
    point = np.asarray(point_cart, dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(point, bracket=("(", ")"))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac = point @ np.linalg.inv(lattice)
    wrapped = frac - np.floor(frac + 1e-9)
    return "(" + ", ".join(format_fraction(value) for value in wrapped) + ")"


def atom_frac_label(atom: dict) -> str | None:
    frac = atom.get("frac")
    if frac is None:
        return None
    return "(" + ", ".join(format_fraction(float(value)) for value in frac) + ")"


def integer_index_label(values: np.ndarray, *, bracket: tuple[str, str], orient_positive: bool = True) -> str:
    ints = integer_index_vector(values, orient_positive=orient_positive)
    if ints is None:
        return f"{bracket[0]}0 0 0{bracket[1]}"
    return bracket[0] + " ".join(format_index(int(value)) for value in ints) + bracket[1]


def integer_index_label_text(values: np.ndarray, *, bracket: tuple[str, str], orient_positive: bool = True) -> str:
    ints = integer_index_vector(values, orient_positive=orient_positive)
    if ints is None:
        return f"{bracket[0]}0 0 0{bracket[1]}"
    return bracket[0] + " ".join(format_index_text(int(value)) for value in ints) + bracket[1]


def integer_index_vector(values: np.ndarray, *, orient_positive: bool = True) -> np.ndarray | None:
    values = np.asarray(values, dtype=float)
    if np.linalg.norm(values) < 1e-10:
        return None
    normalized = values / np.max(np.abs(values))
    best = None
    for scale in range(1, 13):
        candidate = np.rint(normalized * scale).astype(int)
        if not np.any(candidate):
            continue
        error = np.linalg.norm(normalized - candidate / max(np.max(np.abs(candidate)), 1))
        if best is None or error < best[0]:
            best = (error, candidate)
        if error < 1e-5:
            break
    ints = best[1] if best is not None else np.rint(normalized).astype(int)
    gcd = int(np.gcd.reduce(np.abs(ints[np.nonzero(ints)]))) if np.any(ints) else 1
    ints = ints // max(gcd, 1)
    first = next((value for value in ints if value != 0), 0)
    if orient_positive and first < 0:
        ints = -ints
    return ints


def format_index(value: int) -> str:
    return f"<span class=\"overline\">{abs(value)}</span>" if value < 0 else str(value)


def format_index_text(value: int) -> str:
    return f"{abs(value)}\u0305" if value < 0 else str(value)


def format_fraction(value: float) -> str:
    value = float(value)
    if abs(value) < 1e-8 or abs(value - 1.0) < 1e-8:
        return "0"
    fraction = Fraction(value).limit_denominator(24)
    if abs(value - float(fraction)) < 2e-3:
        if fraction.denominator == 1:
            return str(fraction.numerator)
        return f"{fraction.numerator}/{fraction.denominator}"
    return f"{value:.3f}"


def vector_label(values: np.ndarray, *, bracket: tuple[str, str]) -> str:
    return bracket[0] + ", ".join(f"{float(value):.3f}" for value in values) + bracket[1]


def scene_center(render_data: dict) -> np.ndarray:
    atoms = render_data.get("atoms", [])
    if atoms:
        points = np.asarray([atom["cart"] for atom in atoms], dtype=float)
        return np.mean(points, axis=0)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is not None:
        lattice = np.asarray(unit_cell["lattice"], dtype=float)
        return np.asarray([0.5, 0.5, 0.5]) @ lattice
    return np.zeros(3)


def camera_up_vector(direction: np.ndarray) -> np.ndarray:
    direction = viewer.normalize(direction)
    candidates = [
        np.asarray([0.0, 0.0, 1.0]),
        np.asarray([0.0, 1.0, 0.0]),
        np.asarray([1.0, 0.0, 0.0]),
    ]
    up = min(candidates, key=lambda candidate: abs(float(np.dot(candidate, direction))))
    up = up - np.dot(up, direction) * direction
    return viewer.normalize(up)


def rotate_vector(vector: np.ndarray, axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = viewer.normalize(axis)
    vector = np.asarray(vector, dtype=float)
    return (
        vector * np.cos(angle_rad)
        + np.cross(axis, vector) * np.sin(angle_rad)
        + axis * np.dot(axis, vector) * (1.0 - np.cos(angle_rad))
    )
