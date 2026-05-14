from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class RenderAtom:
    index: int
    element: str
    atomic_number: int
    cart: np.ndarray
    frac: np.ndarray | None = None
    selected: bool = False


@dataclass
class CrystalStructureData:
    lattice: np.ndarray
    atoms: list[RenderAtom]
    source_file: str
    pymatgen_structure: object | None = None


@dataclass
class CrystalSymmetryOperation:
    index: int
    W: np.ndarray
    t: np.ndarray
    kind: str
    order: int | None

    @property
    def label(self) -> str:
        if self.order is None:
            return f"Operation {self.index}: {self.kind}"
        return f"Operation {self.index}: {self.kind} ({self.order})"


@dataclass
class CrystalAxis:
    direction_frac: np.ndarray
    point_frac: np.ndarray
    operations: list[int]
    kind: str
    order: int | None


@dataclass
class CrystalPlane:
    point_frac: np.ndarray
    basis_frac: np.ndarray
    normal_frac: np.ndarray
    operations: list[int]
    kind: str


@dataclass
class CrystalCenter:
    point_frac: np.ndarray
    operations: list[int]
    kind: str


@dataclass
class RenderAxis:
    point_cart: np.ndarray
    direction_cart: np.ndarray
    label: str
    operations: list[int] = field(default_factory=list)


@dataclass
class RenderPlane:
    point_cart: np.ndarray
    basis1_cart: np.ndarray
    basis2_cart: np.ndarray
    normal_cart: np.ndarray
    label: str
    operations: list[int] = field(default_factory=list)


@dataclass
class RenderCenter:
    point_cart: np.ndarray
    label: str
    operations: list[int] = field(default_factory=list)


@dataclass
class SymmetryAnalysisResult:
    operations: list[CrystalSymmetryOperation]
    axes: list[CrystalAxis]
    planes: list[CrystalPlane]
    centers: list[CrystalCenter]
    space_group_number: int | None = None
    international_symbol: str | None = None
    hall_symbol: str | None = None
    point_group: str | None = None

