from __future__ import annotations

from fractions import Fraction

import numpy as np

from crystal_viewer.geometry import normalize
from crystal_viewer.viewer.animation import animation_paths
from crystal_viewer.viewer.animation_path import effective_rotation_axis
from crystal_viewer.viewer.display_atoms import display_point_cart, display_scene_center
from crystal_viewer.viewer.glide_geometry import centered_fractional_vector, glide_translation_frac
from crystal_viewer.viewer.operation_lookup import selected_elements, selected_mapping
from crystal_viewer.viewer.symmetry_elements import visual_improper_elements


def operation_summaries(
    render_data: dict,
    atom_mappings: dict | None,
) -> list[dict]:
    summaries = []
    for operation in render_data["operations"]:
        summary_operation = dict(operation)
        visual_translation = visual_translation_direction_cart(render_data, operation, atom_mappings)
        if visual_translation is not None:
            summary_operation["_display_translation_cart"] = visual_translation.tolist()
        axes, planes, centers = operation_summary_elements(
            render_data,
            summary_operation,
        )
        display_symbol = display_operation_symbol(render_data, summary_operation, axes, planes)
        summaries.append(
            {
                "index": operation["index"],
                "label": operation["label"],
                "symbol": operation.get("symbol") or operation["label"],
                "display_symbol": display_symbol,
                "kind": operation["kind"],
                "order": operation.get("order"),
                "angle_deg": operation.get("angle_deg"),
                "element_summary": operation_element_summary(
                    render_data,
                    summary_operation,
                    axes,
                    planes,
                    centers,
                    display_symbol=display_symbol,
                ),
                "itc_like_summary": operation_itc_like_summary(
                    render_data,
                    summary_operation,
                    axes,
                    planes,
                    centers,
                    display_symbol=display_symbol,
                ),
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
    return summaries


def operation_summary_elements(
    render_data: dict,
    operation: dict,
) -> tuple[list[dict], list[dict], list[dict]]:
    operation_index = operation["index"]
    axes, planes, centers = (
        selected_elements(render_data["axes"], operation_index, element_index=None),
        selected_elements(render_data["planes"], operation_index, element_index=None),
        selected_elements(render_data["centers"], operation_index, element_index=None),
    )
    return visual_improper_elements(
        render_data,
        operation,
        axes,
        planes,
        centers,
        improper_mode="auto",
    )


def display_operation_symbol(render_data: dict, operation: dict, axes: list[dict], planes: list[dict]) -> str:
    symbol = operation.get("symbol") or operation["label"]
    if is_pure_translation_operation(operation):
        return "t"
    if str(operation["kind"]).find("glide") >= 0 and str(symbol) == "g" and planes:
        inferred = infer_standard_glide_symbol_for_planes(render_data, operation, planes)
        if inferred is not None:
            return inferred
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
    direction = normalize(np.asarray(axis["direction_cart"], dtype=float))
    moved = np.asarray(matrix, dtype=float) @ point + np.asarray(translation, dtype=float)
    displacement = moved - point
    projected = float(np.dot(displacement, direction))

    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    frac_direction = direction @ lattice_inverse(unit_cell)
    primitive_frac = integer_index_vector(frac_direction)
    if primitive_frac is None:
        return None
    period = float(np.linalg.norm(primitive_frac @ lattice))
    if period < 1e-10:
        return None

    fraction = (projected / period) % 1.0
    order_int = int(order)
    if order_int == 2 and not np.isclose(fraction, 0.0, atol=1e-6):
        screw = 1
    else:
        raw_screw = fraction * order_int
        screw = int(np.floor(raw_screw + 0.5 + 1e-8))
        if screw == 0 and not np.isclose(fraction, 0.0, atol=1e-6):
            screw = 1
        elif screw >= order_int:
            screw = order_int - 1
    if screw == 0:
        return None
    return f"{order_int}_{screw}"


def plane_hkl_vector(render_data: dict, plane: dict) -> np.ndarray | None:
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return None
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    normal = np.asarray(plane["normal_cart"], dtype=float)
    return lattice @ normal


def infer_standard_glide_symbol(render_data: dict, operation: dict, plane: dict) -> str | None:
    glide_frac = glide_translation_frac(render_data, operation, plane)
    if glide_frac is None:
        return None

    magnitudes = np.abs(centered_fractional_vector(glide_frac))
    half_axes = [index for index, value in enumerate(magnitudes) if abs(float(value) - 0.5) < 1e-5]
    quarter_axes = [
        index
        for index, value in enumerate(magnitudes)
        if min(abs(float(value) - 0.25), abs(float(value) - 0.75)) < 1e-5
    ]
    other_axes = [
        index
        for index, value in enumerate(magnitudes)
        if value > 1e-5 and index not in half_axes and index not in quarter_axes
    ]
    if other_axes:
        return None
    if len(quarter_axes) >= 2 and not half_axes:
        return "d"
    if len(half_axes) >= 2 and not quarter_axes:
        return "n"
    if len(half_axes) == 1 and not quarter_axes:
        return ("a", "b", "c")[half_axes[0]]
    return None


def infer_standard_glide_symbol_for_planes(render_data: dict, operation: dict, planes: list[dict]) -> str | None:
    candidates = []
    for plane in planes:
        symbol = infer_standard_glide_symbol(render_data, operation, plane)
        glide_frac = glide_translation_frac(render_data, operation, plane)
        if symbol is None or glide_frac is None:
            continue
        centered = centered_fractional_vector(glide_frac)
        candidates.append((glide_vector_cart_norm(render_data, centered), symbol))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    best_norm = candidates[0][0]
    symbols = {symbol for norm, symbol in candidates if abs(norm - best_norm) < 1e-5}
    if len(symbols) != 1:
        return None
    return next(iter(symbols))


def readable_glide_representative(
    render_data: dict,
    operation: dict,
    planes: list[dict],
) -> tuple[dict, np.ndarray] | None:
    candidates = []
    for index, plane in enumerate(planes):
        glide_frac = glide_translation_frac(render_data, operation, plane)
        if glide_frac is None:
            continue
        centered = centered_fractional_vector(glide_frac)
        cart_norm = glide_vector_cart_norm(render_data, centered)
        fraction_score = fractional_vector_complexity(centered)
        offset_score = plane_offset_complexity(render_data, plane)
        candidates.append((cart_norm, fraction_score, offset_score, index, plane, centered))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[:4])
    _, _, _, _, plane, glide_frac = candidates[0]
    return plane, glide_frac


def glide_vector_cart_norm(render_data: dict, glide_frac: np.ndarray) -> float:
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return float(np.linalg.norm(glide_frac))
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    return float(np.linalg.norm(np.asarray(glide_frac, dtype=float) @ lattice))


def fractional_vector_complexity(values: np.ndarray) -> int:
    return sum(fraction_denominator(value) for value in np.asarray(values, dtype=float))


def plane_offset_complexity(render_data: dict, plane: dict) -> int:
    hkl = plane_hkl_vector(render_data, plane)
    if hkl is None:
        return 999
    ints = integer_index_vector(hkl)
    if ints is None:
        return 999
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return 999
    frac = np.asarray(plane["point_cart"], dtype=float) @ lattice_inverse(unit_cell)
    offset = float(np.dot(ints, frac))
    offset -= np.floor(offset)
    return fraction_denominator(offset)


def fraction_denominator(value: float) -> int:
    value = float(abs(value))
    value -= np.floor(value)
    if value > 0.5:
        value = 1.0 - value
    fraction = Fraction(value).limit_denominator(24)
    if abs(value - float(fraction)) < 2e-3:
        return fraction.denominator
    return 999


def operation_element_summary(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
    *,
    display_symbol: str | None = None,
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
        summary = (
            f"{plane_normal_label(render_data, plane)} "
            f"@ {point_label(render_data, plane['point_cart'])}"
        )
        if "glide" in str(operation["kind"]) and display_symbol == "g":
            glide_frac = glide_translation_frac(render_data, operation, plane)
            if glide_frac is not None:
                summary += f"; glide {fractional_vector_label(centered_fractional_vector(glide_frac))}"
        parts.append(summary)
    if centers and effective_axis is None:
        center = centers[0]
        parts.append(f"@ {point_label(render_data, center['point_cart'])}")
    translation_direction = translation_direction_label(render_data, operation)
    if translation_direction is not None and not parts:
        parts.append(translation_direction)
    return "; ".join(parts)


def operation_itc_like_summary(
    render_data: dict,
    operation: dict,
    axes: list[dict],
    planes: list[dict],
    centers: list[dict],
    *,
    display_symbol: str | None = None,
) -> str:
    if "glide" in str(operation["kind"]) and planes:
        representative = readable_glide_representative(render_data, operation, planes)
        if representative is not None:
            plane, glide_frac = representative
            return (
                f"g{fractional_vector_label(glide_frac)} "
                f"{plane_equation_label(render_data, plane)}"
            )
    return operation_element_summary(
        render_data,
        operation,
        axes,
        planes,
        centers,
        display_symbol=display_symbol,
    )


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
    cell_origin_mode: str = "center",
) -> np.ndarray:
    effective_axis = axes[0] if axes else effective_axis_from_operation(operation, centers)
    if effective_axis is not None:
        return display_point_cart(render_data, effective_axis["point_cart"], display_mode, cell_origin_mode)
    if planes:
        return display_point_cart(render_data, planes[0]["point_cart"], display_mode, cell_origin_mode)
    if centers:
        return display_point_cart(render_data, centers[0]["point_cart"], display_mode, cell_origin_mode)
    return display_scene_center(render_data, display_mode, cell_origin_mode)


def custom_focus_point_cart(
    result: dict,
    render_data: dict,
    display_mode: str,
    cell_origin_mode: str = "center",
) -> np.ndarray | None:
    elements = result.get("elements") or {}
    for key in ("axes", "planes", "centers"):
        items = elements.get(key) or []
        if items:
            return display_point_cart(render_data, items[0]["point_cart"], display_mode, cell_origin_mode)
    return None


def visual_translation_direction_cart(
    render_data: dict,
    operation: dict,
    atom_mappings: dict | None,
) -> np.ndarray | None:
    if not is_pure_translation_operation(operation):
        return None
    mapping = selected_mapping(atom_mappings, operation["index"])
    if mapping is None:
        return None
    paths = animation_paths(
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
    frac_direction = direction @ lattice_inverse(unit_cell)
    return integer_index_label(frac_direction, bracket=("[", "]"), orient_positive=False)


def translation_direction_label_text(render_data: dict, operation: dict) -> str | None:
    direction = translation_direction_cart(operation)
    if direction is None:
        return None
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(direction, bracket=("[", "]"))
    frac_direction = direction @ lattice_inverse(unit_cell)
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
        values = point @ lattice_inverse(unit_cell)
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
    axis = effective_rotation_axis(operation, None, center)
    return axis


def axis_direction_label(render_data: dict, axis: dict) -> str:
    vector = np.asarray(axis["direction_cart"], dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(vector, bracket=("[", "]"))
    frac_direction = vector @ lattice_inverse(unit_cell)
    return integer_index_label(frac_direction, bracket=("[", "]"))


def axis_direction_label_text(render_data: dict, axis: dict) -> str:
    vector = np.asarray(axis["direction_cart"], dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(vector, bracket=("[", "]"))
    frac_direction = vector @ lattice_inverse(unit_cell)
    return integer_index_label_text(frac_direction, bracket=("[", "]"))


def plane_normal_label(render_data: dict, plane: dict) -> str:
    hkl = plane_hkl_vector(render_data, plane)
    if hkl is None:
        normal = np.asarray(plane["normal_cart"], dtype=float)
        return vector_label(normal, bracket=("(", ")"))
    return integer_index_label(hkl, bracket=("(", ")"))


def plane_normal_label_text(render_data: dict, plane: dict) -> str:
    hkl = plane_hkl_vector(render_data, plane)
    if hkl is None:
        normal = np.asarray(plane["normal_cart"], dtype=float)
        return vector_label(normal, bracket=("(", ")"))
    return integer_index_label_text(hkl, bracket=("(", ")"))


def plane_equation_label(render_data: dict, plane: dict) -> str:
    hkl = plane_hkl_vector(render_data, plane)
    unit_cell = render_data.get("unit_cell")
    if hkl is None or unit_cell is None:
        return (
            f"{plane_normal_label_text(render_data, plane)} "
            f"@ {point_label(render_data, plane['point_cart'])}"
        )
    ints = integer_index_vector(hkl)
    if ints is None:
        return (
            f"{plane_normal_label_text(render_data, plane)} "
            f"@ {point_label(render_data, plane['point_cart'])}"
        )
    frac = np.asarray(plane["point_cart"], dtype=float) @ lattice_inverse(unit_cell)
    offset = float(np.dot(ints, frac))
    offset -= np.floor(offset)
    terms = []
    variables = ("x", "y", "z")
    for coefficient, variable in zip(ints, variables):
        coefficient = int(coefficient)
        if coefficient == 0:
            continue
        if coefficient == 1:
            term = variable
        elif coefficient == -1:
            term = f"-{variable}"
        else:
            term = f"{coefficient}{variable}"
        terms.append(term)
    left = " + ".join(terms).replace("+ -", "- ")
    return f"plane {left}={format_fraction(offset)}"


def point_label(render_data: dict, point_cart: list[float]) -> str:
    point = np.asarray(point_cart, dtype=float)
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return vector_label(point, bracket=("(", ")"))
    frac = point @ lattice_inverse(unit_cell)
    wrapped = frac - np.floor(frac + 1e-9)
    return "(" + ", ".join(format_fraction(value) for value in wrapped) + ")"


def fractional_vector_label(values: np.ndarray) -> str:
    return "(" + ",".join(format_fraction(float(value)) for value in values) + ")"


def lattice_inverse(unit_cell: dict) -> np.ndarray:
    return np.linalg.inv(np.asarray(unit_cell["lattice"], dtype=float))


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
    return np.zeros(3)


def camera_up_vector(direction: np.ndarray) -> np.ndarray:
    direction = normalize(direction)
    candidates = [
        np.asarray([0.0, 0.0, 1.0]),
        np.asarray([0.0, 1.0, 0.0]),
        np.asarray([1.0, 0.0, 0.0]),
    ]
    up = min(candidates, key=lambda candidate: abs(float(np.dot(candidate, direction))))
    up = up - np.dot(up, direction) * direction
    return normalize(up)


def rotate_vector(vector: np.ndarray, axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = normalize(axis)
    vector = np.asarray(vector, dtype=float)
    return (
        vector * np.cos(angle_rad)
        + np.cross(axis, vector) * np.sin(angle_rad)
        + axis * np.dot(axis, vector) * (1.0 - np.cos(angle_rad))
    )
