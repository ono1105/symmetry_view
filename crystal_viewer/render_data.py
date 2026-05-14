from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

from .analysis_models import (
    AtomSite,
    MoleculeAnalysisResult,
    MolecularAxisElement,
    MolecularCenterElement,
    MolecularPlaneElement,
    StructureAnalysisResult,
)


RenderMode = Literal["crystal", "molecule"]


@dataclass(frozen=True)
class RenderAtomData:
    index: int
    element: str
    atomic_number: int
    cart: np.ndarray
    frac: np.ndarray | None = None


@dataclass(frozen=True)
class RenderOperationData:
    index: int
    label: str
    kind: str
    order: int | None
    angle_deg: float | None
    symbol: str


@dataclass(frozen=True)
class RenderAxisData:
    point_cart: np.ndarray
    direction_cart: np.ndarray
    label: str
    operation_indices: tuple[int, ...]


@dataclass(frozen=True)
class RenderPlaneData:
    point_cart: np.ndarray
    basis1_cart: np.ndarray
    basis2_cart: np.ndarray
    normal_cart: np.ndarray
    label: str
    operation_indices: tuple[int, ...]


@dataclass(frozen=True)
class RenderCenterData:
    point_cart: np.ndarray
    label: str
    operation_indices: tuple[int, ...]


@dataclass(frozen=True)
class UnitCellRenderData:
    lattice: np.ndarray
    vertices_cart: np.ndarray
    edges: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class RenderMetadata:
    mode: RenderMode
    source_file: Path | None
    formula: str
    symmetry_label: str
    operation_count: int


@dataclass(frozen=True)
class RenderData:
    metadata: RenderMetadata
    atoms: tuple[RenderAtomData, ...]
    operations: tuple[RenderOperationData, ...]
    axes: tuple[RenderAxisData, ...]
    planes: tuple[RenderPlaneData, ...]
    centers: tuple[RenderCenterData, ...]
    unit_cell: UnitCellRenderData | None = None
    bounds_min: np.ndarray = field(default_factory=lambda: np.zeros(3))
    bounds_max: np.ndarray = field(default_factory=lambda: np.zeros(3))


def render_data_from_analysis(result: StructureAnalysisResult | MoleculeAnalysisResult) -> RenderData:
    if isinstance(result, StructureAnalysisResult):
        return render_data_from_crystal(result)
    if isinstance(result, MoleculeAnalysisResult):
        return render_data_from_molecule(result)
    raise TypeError(f"unsupported analysis result type: {type(result).__name__}")


def render_data_from_crystal(result: StructureAnalysisResult) -> RenderData:
    lattice = np.asarray(result.structure.lattice, dtype=float)
    atoms = tuple(render_atom_from_site(atom) for atom in result.structure.atoms)
    unit_cell = unit_cell_from_lattice(lattice)
    operations = tuple(
        RenderOperationData(
            index=op.index,
            label=f"{op.index}: {op.international_symbol} {op.kind}",
            kind=op.kind,
            order=op.order,
            angle_deg=op.angle_deg,
            symbol=op.international_symbol,
        )
        for op in result.operations
    )

    symbols = {op.index: op.international_symbol for op in result.operations}

    axes = tuple(
        RenderAxisData(
            point_cart=axis.point_frac @ lattice,
            direction_cart=normalize(axis.direction_frac @ lattice),
            label=operation_group_label(axis.operation_indices, symbols),
            operation_indices=axis.operation_indices,
        )
        for axis in result.axes
    )

    planes = []
    for plane in result.planes:
        basis1_cart = plane.basis_frac[:, 0] @ lattice
        basis2_cart = plane.basis_frac[:, 1] @ lattice
        normal_cart = normalize(np.cross(basis1_cart, basis2_cart))
        planes.append(
            RenderPlaneData(
                point_cart=plane.point_frac @ lattice,
                basis1_cart=normalize(basis1_cart),
                basis2_cart=normalize(basis2_cart),
                normal_cart=normal_cart,
                label=operation_group_label(plane.operation_indices, symbols),
                operation_indices=plane.operation_indices,
            )
        )

    centers = tuple(
        RenderCenterData(
            point_cart=center.point_frac @ lattice,
            label=operation_group_label(center.operation_indices, symbols),
            operation_indices=center.operation_indices,
        )
        for center in result.centers
    )

    bpoints = bounds_points(atoms, unit_cell)
    bmin = np.min(bpoints, axis=0) if len(bpoints) else np.zeros(3)
    bmax = np.max(bpoints, axis=0) if len(bpoints) else np.zeros(3)

    return RenderData(
        metadata=RenderMetadata(
            mode="crystal",
            source_file=result.structure.source_file,
            formula=result.structure.formula,
            symmetry_label=f"{result.space_group.number} {result.space_group.international}",
            operation_count=result.space_group.operation_count,
        ),
        atoms=atoms,
        operations=operations,
        axes=axes,
        planes=tuple(planes),
        centers=centers,
        unit_cell=unit_cell,
        bounds_min=bmin,
        bounds_max=bmax,
    )


def render_data_from_molecule(result: MoleculeAnalysisResult) -> RenderData:
    atoms = tuple(render_atom_from_site(atom) for atom in result.molecule.atoms)
    operations = tuple(
        RenderOperationData(
            index=op.index,
            label=f"{op.index}: {op.symbol} {op.kind}",
            kind=op.kind,
            order=op.order,
            angle_deg=op.angle_deg,
            symbol=op.symbol,
        )
        for op in result.operations
    )

    symbols = {op.index: op.symbol for op in result.operations}

    axes = tuple(render_axis_from_molecular_axis(axis, symbols) for axis in result.axes)
    planes = tuple(render_plane_from_molecular_plane(plane, symbols) for plane in result.planes)
    centers = tuple(render_center_from_molecular_center(center, symbols) for center in result.centers)

    bpoints = bounds_points(atoms, None)
    bmin = np.min(bpoints, axis=0) if len(bpoints) else np.zeros(3)
    bmax = np.max(bpoints, axis=0) if len(bpoints) else np.zeros(3)

    return RenderData(
        metadata=RenderMetadata(
            mode="molecule",
            source_file=result.molecule.source_file,
            formula=result.molecule.formula,
            symmetry_label=result.point_group.symbol,
            operation_count=result.point_group.operation_count,
        ),
        atoms=atoms,
        operations=operations,
        axes=axes,
        planes=planes,
        centers=centers,
        unit_cell=None,
        bounds_min=bmin,
        bounds_max=bmax,
    )


def render_atom_from_site(atom: AtomSite) -> RenderAtomData:
    return RenderAtomData(
        index=atom.index,
        element=atom.element,
        atomic_number=atom.atomic_number,
        frac=None if atom.frac is None else np.asarray(atom.frac, dtype=float),
        cart=np.asarray(atom.cart, dtype=float),
    )


def render_axis_from_molecular_axis(
    axis: MolecularAxisElement,
    symbols: dict[int, str],
) -> RenderAxisData:
    return RenderAxisData(
        point_cart=np.asarray(axis.point_cart, dtype=float),
        direction_cart=normalize(axis.direction_cart),
        label=operation_group_label(axis.operation_indices, symbols),
        operation_indices=axis.operation_indices,
    )


def render_plane_from_molecular_plane(
    plane: MolecularPlaneElement,
    symbols: dict[int, str],
) -> RenderPlaneData:
    basis = np.asarray(plane.basis_cart, dtype=float)
    basis1_cart = normalize(basis[:, 0])
    basis2_cart = normalize(basis[:, 1])
    normal_cart = normalize(plane.normal_cart)
    return RenderPlaneData(
        point_cart=np.asarray(plane.point_cart, dtype=float),
        basis1_cart=basis1_cart,
        basis2_cart=basis2_cart,
        normal_cart=normal_cart,
        label=operation_group_label(plane.operation_indices, symbols),
        operation_indices=plane.operation_indices,
    )


def render_center_from_molecular_center(
    center: MolecularCenterElement,
    symbols: dict[int, str],
) -> RenderCenterData:
    return RenderCenterData(
        point_cart=np.asarray(center.point_cart, dtype=float),
        label=operation_group_label(center.operation_indices, symbols),
        operation_indices=center.operation_indices,
    )


def unit_cell_from_lattice(lattice: np.ndarray) -> UnitCellRenderData:
    lattice = np.asarray(lattice, dtype=float)
    a, b, c = lattice[0], lattice[1], lattice[2]
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            a,
            b,
            c,
            a + b,
            a + c,
            b + c,
            a + b + c,
        ],
        dtype=float,
    )
    edges = (
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 4),
        (1, 5),
        (2, 4),
        (2, 6),
        (3, 5),
        (3, 6),
        (4, 7),
        (5, 7),
        (6, 7),
    )
    return UnitCellRenderData(lattice=lattice, vertices_cart=vertices, edges=edges)


def operation_group_label(operation_indices: tuple[int, ...], symbols_by_index: dict[int, str]) -> str:
    counts: dict[str, int] = {}
    for index in operation_indices:
        symbol = symbols_by_index.get(index, "?")
        counts[symbol] = counts.get(symbol, 0) + 1
    parts = [f"{symbol}x{count}" if count > 1 else symbol for symbol, count in sorted(counts.items())]
    return ", ".join(parts)


def bounds_points(atoms: tuple[RenderAtomData, ...], unit_cell: UnitCellRenderData | None) -> np.ndarray:
    parts = []
    if atoms:
        parts.append(np.array([atom.cart for atom in atoms], dtype=float))
    if unit_cell is not None:
        parts.append(np.asarray(unit_cell.vertices_cart, dtype=float))
    if not parts:
        return np.empty((0, 3))
    return np.vstack(parts)


def normalize(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=float)
    norm = np.linalg.norm(vector)
    if norm < 1e-12:
        return vector
    return vector / norm
