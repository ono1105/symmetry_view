from __future__ import annotations

import itertools

import numpy as np
import spglib

from .models import (
    CrystalAxis,
    CrystalCenter,
    CrystalPlane,
    CrystalStructureData,
    CrystalSymmetryOperation,
    RenderAxis,
    RenderCenter,
    RenderPlane,
    SymmetryAnalysisResult,
)
from .structure_loader import structure_to_spglib_cell


TOL = 1e-6


def analyze_crystal_symmetry(
    structure_data: CrystalStructureData,
    symprec: float = 1e-3,
    angle_tolerance: float = 5.0,
) -> SymmetryAnalysisResult:
    if structure_data.pymatgen_structure is None:
        raise ValueError("pymatgen Structure is required for spglib analysis.")

    cell = structure_to_spglib_cell(structure_data.pymatgen_structure)
    dataset = spglib.get_symmetry_dataset(
        cell,
        symprec=symprec,
        angle_tolerance=angle_tolerance,
    )
    if dataset is None:
        raise ValueError("spglib could not determine symmetry for this structure.")

    operations: list[CrystalSymmetryOperation] = []
    axes: list[CrystalAxis] = []
    planes: list[CrystalPlane] = []
    centers: list[CrystalCenter] = []

    rotations = dataset_value(dataset, "rotations")
    translations = dataset_value(dataset, "translations")

    for index, (W, t) in enumerate(zip(rotations, translations)):
        W = np.asarray(W, dtype=int)
        t = wrap_frac(np.asarray(t, dtype=float))
        kind, order = classify_operation(W, t)
        operation = CrystalSymmetryOperation(index=index, W=W, t=t, kind=kind, order=order)
        operations.append(operation)

        if kind.startswith("rotation") or kind.startswith("screw"):
            axis = compute_axis(W, t, kind, order, index)
            if axis is not None:
                merge_axis(axes, axis)
        elif kind in {"mirror", "glide"}:
            plane = compute_plane(W, t, kind, index)
            if plane is not None:
                merge_plane(planes, plane)
        elif kind == "inversion":
            center = compute_center(W, t, kind, index)
            if center is not None:
                merge_center(centers, center)

    return SymmetryAnalysisResult(
        operations=operations,
        axes=axes,
        planes=planes,
        centers=centers,
        space_group_number=dataset_value(dataset, "number"),
        international_symbol=dataset_value(dataset, "international"),
        hall_symbol=dataset_value(dataset, "hall"),
        point_group=dataset_value(dataset, "pointgroup"),
    )


def dataset_value(dataset, key: str):
    if isinstance(dataset, dict):
        return dataset.get(key)
    return getattr(dataset, key, None)


def classify_operation(W: np.ndarray, t: np.ndarray) -> tuple[str, int | None]:
    identity = np.eye(3, dtype=int)
    det = round(float(np.linalg.det(W)))

    if np.array_equal(W, identity):
        if is_lattice_zero(t):
            return "identity", 1
        return "pure_translation_or_centering_translation", 1

    if np.array_equal(W, -identity):
        return "inversion", 2

    order = operation_order(W)
    has_fixed = fixed_solution_exists(W, t)

    if det == 1:
        return (f"rotation_{order}" if has_fixed else f"screw_{order}"), order

    if det == -1 and np.array_equal(W @ W, identity):
        return ("mirror" if has_fixed else "glide"), 2

    return "rotoinversion_or_improper", order


def operation_order(W: np.ndarray, max_order: int = 12) -> int | None:
    identity = np.eye(3, dtype=int)
    power = np.eye(3, dtype=int)
    for order in range(1, max_order + 1):
        power = power @ W
        if np.array_equal(power, identity):
            return order
    return None


def compute_axis(
    W: np.ndarray,
    t: np.ndarray,
    kind: str,
    order: int | None,
    operation_index: int,
    search_range: int = 2,
) -> CrystalAxis | None:
    direction_basis = nullspace(W - np.eye(3))
    if direction_basis.shape[1] == 0:
        return None
    direction = canonical_direction(direction_basis[:, 0])

    for n in integer_shifts(search_range):
        matrix = np.column_stack((np.eye(3) - W, direction))
        rhs = t + n
        solution, residuals, rank, _ = np.linalg.lstsq(matrix, rhs, rcond=None)
        if np.linalg.norm(matrix @ solution - rhs) < 1e-5:
            point = wrap_frac(solution[:3])
            return CrystalAxis(
                direction_frac=direction,
                point_frac=point,
                operations=[operation_index],
                kind=kind,
                order=order,
            )
    return None


def compute_plane(
    W: np.ndarray,
    t: np.ndarray,
    kind: str,
    operation_index: int,
    search_range: int = 2,
) -> CrystalPlane | None:
    basis = nullspace(W - np.eye(3))
    normal_basis = nullspace(W + np.eye(3))
    if basis.shape[1] < 2 or normal_basis.shape[1] == 0:
        return None

    basis = independent_columns(basis, 2)
    normal = canonical_direction(normal_basis[:, 0])

    for n in integer_shifts(search_range):
        matrix = np.column_stack((np.eye(3) - W, basis))
        rhs = t + n
        solution, residuals, rank, _ = np.linalg.lstsq(matrix, rhs, rcond=None)
        if np.linalg.norm(matrix @ solution - rhs) < 1e-5:
            return CrystalPlane(
                point_frac=wrap_frac(solution[:3]),
                basis_frac=basis,
                normal_frac=normal,
                operations=[operation_index],
                kind=kind,
            )
    return None


def compute_center(
    W: np.ndarray,
    t: np.ndarray,
    kind: str,
    operation_index: int,
    search_range: int = 2,
) -> CrystalCenter | None:
    matrix = np.eye(3) - W
    for n in integer_shifts(search_range):
        rhs = t + n
        solution, residuals, rank, _ = np.linalg.lstsq(matrix, rhs, rcond=None)
        if np.linalg.norm(matrix @ solution - rhs) < 1e-5:
            return CrystalCenter(
                point_frac=wrap_frac(solution),
                operations=[operation_index],
                kind=kind,
            )
    return None


def render_axes(axes: list[CrystalAxis], lattice: np.ndarray) -> list[RenderAxis]:
    rendered = []
    for axis in axes:
        direction_cart = axis.direction_frac @ lattice
        norm = np.linalg.norm(direction_cart)
        if norm < TOL:
            continue
        rendered.append(
            RenderAxis(
                point_cart=axis.point_frac @ lattice,
                direction_cart=direction_cart / norm,
                label=axis.kind,
                operations=list(axis.operations),
            )
        )
    return rendered


def render_planes(planes: list[CrystalPlane], lattice: np.ndarray) -> list[RenderPlane]:
    rendered = []
    for plane in planes:
        basis1_cart = plane.basis_frac[:, 0] @ lattice
        basis2_cart = plane.basis_frac[:, 1] @ lattice
        normal_cart = np.cross(basis1_cart, basis2_cart)
        norm = np.linalg.norm(normal_cart)
        if norm < TOL:
            continue
        rendered.append(
            RenderPlane(
                point_cart=plane.point_frac @ lattice,
                basis1_cart=basis1_cart,
                basis2_cart=basis2_cart,
                normal_cart=normal_cart / norm,
                label=plane.kind,
                operations=list(plane.operations),
            )
        )
    return rendered


def render_centers(centers: list[CrystalCenter], lattice: np.ndarray) -> list[RenderCenter]:
    return [
        RenderCenter(
            point_cart=center.point_frac @ lattice,
            label=center.kind,
            operations=list(center.operations),
        )
        for center in centers
    ]


def nullspace(matrix: np.ndarray, tol: float = 1e-9) -> np.ndarray:
    _, singular_values, vh = np.linalg.svd(np.asarray(matrix, dtype=float))
    rank = (singular_values > tol).sum()
    return vh[rank:].T.copy()


def independent_columns(matrix: np.ndarray, count: int) -> np.ndarray:
    columns: list[np.ndarray] = []
    for i in range(matrix.shape[1]):
        candidate = matrix[:, i]
        if np.linalg.norm(candidate) < TOL:
            continue
        trial = columns + [candidate]
        if np.linalg.matrix_rank(np.column_stack(trial), tol=TOL) == len(trial):
            columns.append(candidate)
        if len(columns) == count:
            break
    return np.column_stack(columns)


def fixed_solution_exists(W: np.ndarray, t: np.ndarray, search_range: int = 2) -> bool:
    matrix = np.eye(3) - W
    for n in integer_shifts(search_range):
        rhs = t + n
        solution, residuals, rank, _ = np.linalg.lstsq(matrix, rhs, rcond=None)
        if np.linalg.norm(matrix @ solution - rhs) < 1e-5:
            return True
    return False


def merge_axis(axes: list[CrystalAxis], candidate: CrystalAxis) -> None:
    for axis in axes:
        if candidate.kind == axis.kind and lines_equivalent(
            axis.point_frac, axis.direction_frac, candidate.point_frac, candidate.direction_frac
        ):
            axis.operations.extend(candidate.operations)
            return
    axes.append(candidate)


def merge_plane(planes: list[CrystalPlane], candidate: CrystalPlane) -> None:
    for plane in planes:
        if candidate.kind == plane.kind and planes_equivalent(
            plane.point_frac,
            plane.basis_frac,
            plane.normal_frac,
            candidate.point_frac,
            candidate.normal_frac,
        ):
            plane.operations.extend(candidate.operations)
            return
    planes.append(candidate)


def merge_center(centers: list[CrystalCenter], candidate: CrystalCenter) -> None:
    for center in centers:
        if np.linalg.norm(wrap_delta(center.point_frac - candidate.point_frac)) < 1e-5:
            center.operations.extend(candidate.operations)
            return
    centers.append(candidate)


def lines_equivalent(p1: np.ndarray, v1: np.ndarray, p2: np.ndarray, v2: np.ndarray) -> bool:
    v1 = normalize(v1)
    v2 = normalize(v2)
    if abs(float(np.dot(v1, v2))) < 1.0 - 1e-5:
        return False
    for n in integer_shifts(1):
        delta = p2 - p1 + n
        solution, _, _, _ = np.linalg.lstsq(v1.reshape(3, 1), delta, rcond=None)
        if np.linalg.norm(v1 * solution[0] - delta) < 1e-5:
            return True
    return False


def planes_equivalent(
    p1: np.ndarray,
    basis1: np.ndarray,
    normal1: np.ndarray,
    p2: np.ndarray,
    normal2: np.ndarray,
) -> bool:
    normal1 = normalize(normal1)
    normal2 = normalize(normal2)
    if abs(float(np.dot(normal1, normal2))) < 1.0 - 1e-5:
        return False
    for n in integer_shifts(1):
        delta = p2 - p1 + n
        solution, _, _, _ = np.linalg.lstsq(basis1, delta, rcond=None)
        if np.linalg.norm(basis1 @ solution - delta) < 1e-5:
            return True
    return False


def integer_shifts(search_range: int):
    values = range(-search_range, search_range + 1)
    for shift in itertools.product(values, repeat=3):
        yield np.asarray(shift, dtype=float)


def wrap_frac(frac: np.ndarray) -> np.ndarray:
    return np.mod(np.asarray(frac, dtype=float), 1.0)


def wrap_delta(delta: np.ndarray) -> np.ndarray:
    return np.asarray(delta, dtype=float) - np.round(delta)


def is_lattice_zero(vec: np.ndarray) -> bool:
    return np.linalg.norm(wrap_delta(vec)) < 1e-6


def normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm < TOL:
        return np.asarray(vec, dtype=float)
    return np.asarray(vec, dtype=float) / norm


def canonical_direction(vec: np.ndarray) -> np.ndarray:
    vec = normalize(vec)
    for value in vec:
        if abs(value) > TOL:
            return vec if value > 0 else -vec
    return vec
