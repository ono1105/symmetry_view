from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
from pymatgen.core import Molecule
from pymatgen.symmetry.analyzer import PointGroupAnalyzer

from .analysis_models import (
    AtomSite,
    MolecularAxisElement,
    MolecularCenterElement,
    MolecularPlaneElement,
    MolecularSymmetryOperationInfo,
    MoleculeAnalysisResult,
    MoleculePointGroupInfo,
    MoleculeSummary,
)
from .structure_analysis import AnalysisError


TOL = 1e-7
_MOLECULE_ANALYSIS_WARMED = False


def warm_molecule_analysis() -> None:
    """Build the small pymatgen caches used on the first browser XYZ import."""
    global _MOLECULE_ANALYSIS_WARMED
    if _MOLECULE_ANALYSIS_WARMED:
        return
    methane = Molecule(
        ["C", "H", "H", "H", "H"],
        [
            [0.0, 0.0, 0.0],
            [0.629118, 0.629118, 0.629118],
            [-0.629118, -0.629118, 0.629118],
            [-0.629118, 0.629118, -0.629118],
            [0.629118, -0.629118, -0.629118],
        ],
    )
    analyze_molecule(methane)
    _MOLECULE_ANALYSIS_WARMED = True


def analyze_molecule_file(
    molecule_path: str | Path,
    *,
    tolerance: float = 0.3,
    eigen_tolerance: float = 0.01,
    matrix_tolerance: float = 0.1,
) -> MoleculeAnalysisResult:
    molecule_path = Path(molecule_path)
    if not molecule_path.exists():
        raise AnalysisError(f"molecule file not found: {molecule_path}")

    molecule = Molecule.from_file(molecule_path)
    return analyze_molecule(
        molecule,
        source_file=molecule_path,
        tolerance=tolerance,
        eigen_tolerance=eigen_tolerance,
        matrix_tolerance=matrix_tolerance,
    )


def analyze_molecule(
    molecule: Molecule,
    *,
    source_file: str | Path | None = None,
    tolerance: float = 0.3,
    eigen_tolerance: float = 0.01,
    matrix_tolerance: float = 0.1,
) -> MoleculeAnalysisResult:
    analyzer = PointGroupAnalyzer(
        molecule,
        tolerance=tolerance,
        eigen_tolerance=eigen_tolerance,
        matrix_tolerance=matrix_tolerance,
    )
    operations = tuple(analyzer.get_symmetry_operations())
    center_cart = molecule_center_from_analyzer(molecule, analyzer)

    op_infos = tuple(
        convert_operation(index, op.rotation_matrix, op.translation_vector, center_cart)
        for index, op in enumerate(operations)
    )
    axes, planes, centers = collect_molecular_elements(op_infos, center_cart)

    return MoleculeAnalysisResult(
        molecule=convert_molecule(source_file, molecule, center_cart),
        point_group=convert_point_group(analyzer, operations),
        operations=op_infos,
        axes=tuple(axes),
        planes=tuple(planes),
        centers=tuple(centers),
    )


def convert_molecule(source_file: str | Path | None, molecule: Molecule, center_cart: np.ndarray) -> MoleculeSummary:
    atoms = []
    for index, site in enumerate(molecule):
        atoms.append(
            AtomSite(
                index=index,
                element=site.specie.symbol,
                atomic_number=int(site.specie.Z),
                frac=None,
                cart=np.asarray(site.coords, dtype=float),
            )
        )

    return MoleculeSummary(
        source_file=None if source_file is None else Path(source_file),
        formula=molecule.composition.reduced_formula,
        site_count=len(molecule),
        atoms=tuple(atoms),
        center_cart=np.asarray(center_cart, dtype=float),
    )


def convert_point_group(analyzer: PointGroupAnalyzer, operations: tuple) -> MoleculePointGroupInfo:
    equivalent = analyzer.get_equivalent_atoms()
    eq_sets = equivalent.get("eq_sets", {})
    return MoleculePointGroupInfo(
        symbol=str(analyzer.get_pointgroup()),
        operation_count=len(operations),
        rotational_symmetry_number=int(analyzer.get_rotational_symmetry_number()),
        equivalent_atom_sets=tuple(tuple(sorted(indices)) for indices in eq_sets.values()),
    )


def convert_operation(
    index: int,
    rotation: np.ndarray,
    translation: np.ndarray,
    center_cart: np.ndarray,
) -> MolecularSymmetryOperationInfo:
    rotation = clean_matrix(rotation)
    translation = np.asarray(translation, dtype=float)
    det = int(round(float(np.linalg.det(rotation))))
    trace = float(np.trace(rotation))
    order = matrix_order(rotation)
    kind = classify_molecular_operation(rotation, det, trace, order)
    if kind == "mirror" and order is None:
        order = 2
    angle = rotation_angle_deg(rotation) if det == 1 and kind != "identity" else None

    # PointGroupAnalyzer operations act on centered coordinates. This is the
    # equivalent affine operation in the original molecular coordinates.
    original_translation = center_cart + translation - rotation @ center_cart

    return MolecularSymmetryOperationInfo(
        index=index,
        rotation=rotation,
        translation=clean_vector(original_translation),
        kind=kind,
        order=order,
        det=det,
        trace=trace,
        angle_deg=angle,
        symbol=operation_symbol(kind, order),
    )


def collect_molecular_elements(
    operations: tuple[MolecularSymmetryOperationInfo, ...],
    center_cart: np.ndarray,
) -> tuple[list[MolecularAxisElement], list[MolecularPlaneElement], list[MolecularCenterElement]]:
    axes: list[MolecularAxisElement] = []
    planes: list[MolecularPlaneElement] = []
    centers: list[MolecularCenterElement] = []

    for op in operations:
        if op.kind.startswith("rotation_"):
            direction = first_null_vector(op.rotation - np.eye(3))
            if direction is not None:
                merge_axis(
                    axes,
                    MolecularAxisElement(
                        point_cart=center_cart,
                        direction_cart=direction,
                        operation_indices=(op.index,),
                        kind=op.kind,
                        order=op.order,
                    ),
                )
        elif op.kind == "mirror":
            normal = first_null_vector(op.rotation + np.eye(3))
            if normal is not None:
                basis = plane_basis_from_normal(normal)
                merge_plane(
                    planes,
                    MolecularPlaneElement(
                        point_cart=center_cart,
                        normal_cart=normal,
                        basis_cart=basis,
                        operation_indices=(op.index,),
                        kind=op.kind,
                    ),
                )
        elif op.kind == "inversion":
            merge_center(
                centers,
                MolecularCenterElement(
                    point_cart=center_cart,
                    operation_indices=(op.index,),
                    kind=op.kind,
                ),
            )
        elif op.kind.startswith("improper_"):
            direction = first_null_vector(op.rotation + np.eye(3))
            if direction is not None:
                merge_axis(
                    axes,
                    MolecularAxisElement(
                        point_cart=center_cart,
                        direction_cart=direction,
                        operation_indices=(op.index,),
                        kind=op.kind,
                        order=op.order,
                    ),
                )

    return axes, planes, centers


def molecule_center_from_analyzer(molecule: Molecule, analyzer: PointGroupAnalyzer) -> np.ndarray:
    centered = getattr(analyzer, "centered_mol", None)
    if centered is not None and len(centered) == len(molecule):
        offsets = np.asarray(molecule.cart_coords, dtype=float) - np.asarray(centered.cart_coords, dtype=float)
        return clean_vector(np.mean(offsets, axis=0))
    return clean_vector(np.mean(np.asarray(molecule.cart_coords, dtype=float), axis=0))


def classify_molecular_operation(
    rotation: np.ndarray,
    det: int,
    trace: float,
    order: int | None,
) -> str:
    identity = np.eye(3)
    if np.linalg.norm(rotation - identity) < 1e-6:
        return "identity"
    if np.linalg.norm(rotation + identity) < 1e-6:
        return "inversion"
    if det == 1:
        return f"rotation_{order}"
    if det == -1 and abs(trace - 1.0) < 1e-3:
        return "mirror"
    if det == -1:
        return f"improper_{order}"
    return "unknown"


def operation_symbol(kind: str, order: int | None) -> str:
    if kind == "identity":
        return "E"
    if kind == "inversion":
        return "i"
    if kind == "mirror":
        return "sigma"
    if kind.startswith("rotation_"):
        return f"C{order}"
    if kind.startswith("improper_"):
        return f"S{order}"
    return kind


def matrix_order(matrix: np.ndarray, max_order: int = 24) -> int | None:
    identity = np.eye(3)
    power = np.eye(3)
    for order in range(1, max_order + 1):
        power = power @ matrix
        if np.linalg.norm(power - identity) < 1e-5:
            return order
    return None


def rotation_angle_deg(rotation: np.ndarray) -> float:
    cos_theta = np.clip((np.trace(rotation) - 1.0) / 2.0, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_theta)))


def nullspace(matrix: np.ndarray, tol: float = 1e-8) -> np.ndarray:
    _, singular_values, vh = np.linalg.svd(np.asarray(matrix, dtype=float))
    rank = int(np.sum(singular_values > tol))
    basis = vh[rank:].T.copy()
    basis[np.abs(basis) < 1e-12] = 0.0
    return basis


def first_null_vector(matrix: np.ndarray) -> np.ndarray | None:
    basis = nullspace(matrix)
    if basis.shape[1] == 0:
        return None
    return canonical_direction(basis[:, 0])


def canonical_direction(vector: np.ndarray) -> np.ndarray:
    vector = normalize(vector)
    for value in vector:
        if abs(value) > TOL:
            return clean_vector(vector if value > 0 else -vector)
    return clean_vector(vector)


def canonical_plane_basis(basis: np.ndarray) -> np.ndarray:
    v1 = normalize(basis[:, 0])
    v2 = basis[:, 1] - np.dot(basis[:, 1], v1) * v1
    v2 = normalize(v2)
    return np.column_stack((canonical_direction(v1), canonical_direction(v2)))


def plane_basis_from_normal(normal: np.ndarray) -> np.ndarray:
    normal = normalize(normal)
    helper = np.array([1.0, 0.0, 0.0])
    if abs(float(np.dot(normal, helper))) > 0.9:
        helper = np.array([0.0, 1.0, 0.0])
    v1 = normalize(np.cross(normal, helper))
    v2 = normalize(np.cross(normal, v1))
    return np.column_stack((canonical_direction(v1), canonical_direction(v2)))


def normalize(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=float)
    norm = np.linalg.norm(vector)
    if norm < TOL:
        return vector
    return vector / norm


def merge_axis(axes: list[MolecularAxisElement], candidate: MolecularAxisElement) -> None:
    for i, axis in enumerate(axes):
        if axis.kind == candidate.kind and parallel(axis.direction_cart, candidate.direction_cart):
            axes[i] = MolecularAxisElement(
                point_cart=axis.point_cart,
                direction_cart=axis.direction_cart,
                operation_indices=axis.operation_indices + candidate.operation_indices,
                kind=axis.kind,
                order=axis.order,
            )
            return
    axes.append(candidate)


def merge_plane(planes: list[MolecularPlaneElement], candidate: MolecularPlaneElement) -> None:
    for i, plane in enumerate(planes):
        if plane.kind == candidate.kind and parallel(plane.normal_cart, candidate.normal_cart):
            planes[i] = MolecularPlaneElement(
                point_cart=plane.point_cart,
                normal_cart=plane.normal_cart,
                basis_cart=plane.basis_cart,
                operation_indices=plane.operation_indices + candidate.operation_indices,
                kind=plane.kind,
            )
            return
    planes.append(candidate)


def merge_center(centers: list[MolecularCenterElement], candidate: MolecularCenterElement) -> None:
    for i, center in enumerate(centers):
        if np.linalg.norm(center.point_cart - candidate.point_cart) < 1e-6 and center.kind == candidate.kind:
            centers[i] = MolecularCenterElement(
                point_cart=center.point_cart,
                operation_indices=center.operation_indices + candidate.operation_indices,
                kind=center.kind,
            )
            return
    centers.append(candidate)


def parallel(a: np.ndarray, b: np.ndarray) -> bool:
    return np.linalg.norm(np.cross(normalize(a), normalize(b))) < 1e-6


def clean_matrix(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=float)
    matrix[np.abs(matrix) < 1e-12] = 0.0
    return matrix


def clean_vector(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=float)
    vector[np.abs(vector) < 1e-12] = 0.0
    return vector
