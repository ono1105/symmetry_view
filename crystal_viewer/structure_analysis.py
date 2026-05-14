from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import spglib
from pymatgen.core import Structure

from .analysis_models import (
    AtomSite,
    AxisElement,
    CenterElement,
    PlaneElement,
    SpaceGroupInfo,
    StructureAnalysisResult,
    StructureSummary,
    SymmetryOperationInfo,
)


DEFAULT_LEGACY_CORE = Path("/home/ken/work/kouzoukaiseki/symmetry_core.py")


class AnalysisError(RuntimeError):
    pass


def analyze_cif(
    cif_path: str | Path,
    *,
    symprec: float = 1e-3,
    angle_tolerance: float = 5.0,
    search_range: int = 2,
    legacy_core_path: str | Path = DEFAULT_LEGACY_CORE,
) -> StructureAnalysisResult:
    core = load_legacy_core(legacy_core_path)
    cif_path = Path(cif_path)
    if not cif_path.exists():
        raise AnalysisError(f"CIF file not found: {cif_path}")

    structure = Structure.from_file(str(cif_path))
    cell = core.structure_to_spglib_cell(structure)
    dataset = spglib.get_symmetry_dataset(
        cell,
        symprec=symprec,
        angle_tolerance=angle_tolerance,
    )
    if dataset is None:
        raise AnalysisError("spglib could not determine symmetry for this structure.")

    rotations = np.asarray(dataset_value(dataset, "rotations"), dtype=int)
    translations = np.asarray(dataset_value(dataset, "translations"), dtype=float)
    merged, per_operation = core.collect_merged_elements(
        rotations,
        translations,
        search_range=search_range,
    )
    geometry_groups = core.group_elements_by_geometry(merged, rotations)

    operations = tuple(
        convert_operation(core, index, W, t, search_range)
        for index, (W, t) in enumerate(zip(rotations, translations))
    )

    return StructureAnalysisResult(
        structure=convert_structure(cif_path, structure),
        space_group=convert_space_group(dataset),
        operations=operations,
        axes=tuple(convert_axis(axis) for axis in merged["axes"]),
        planes=tuple(convert_plane(plane) for plane in merged["planes"]),
        centers=tuple(convert_center(center) for center in merged["centers"]),
        geometry_groups=geometry_groups,
        raw_merged=merged,
        raw_per_operation=per_operation,
    )


def load_legacy_core(path: str | Path) -> ModuleType:
    path = Path(path)
    if not path.exists():
        raise AnalysisError(f"legacy symmetry core not found: {path}")

    module_name = "_kouzoukaiseki_symmetry_core"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AnalysisError(f"could not load legacy symmetry core: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def convert_structure(cif_path: Path, structure: Structure) -> StructureSummary:
    atoms = []
    for index, site in enumerate(structure):
        atoms.append(
            AtomSite(
                index=index,
                element=site.specie.symbol,
                atomic_number=int(site.specie.Z),
                frac=np.asarray(site.frac_coords, dtype=float),
                cart=np.asarray(site.coords, dtype=float),
            )
        )

    return StructureSummary(
        source_file=cif_path,
        formula=structure.composition.reduced_formula,
        site_count=len(structure),
        lattice=np.asarray(structure.lattice.matrix, dtype=float),
        atoms=tuple(atoms),
    )


def convert_space_group(dataset) -> SpaceGroupInfo:
    return SpaceGroupInfo(
        number=int(dataset_value(dataset, "number")),
        international=str(dataset_value(dataset, "international")),
        hall=str(dataset_value(dataset, "hall")),
        point_group=str(dataset_value(dataset, "pointgroup")),
        operation_count=len(dataset_value(dataset, "rotations")),
        wyckoffs=tuple(str(x) for x in dataset_value(dataset, "wyckoffs")),
        equivalent_atoms=tuple(int(x) for x in dataset_value(dataset, "equivalent_atoms")),
        site_symmetry_symbols=tuple(str(x) for x in dataset_value(dataset, "site_symmetry_symbols")),
    )


def convert_operation(core: ModuleType, index: int, W: np.ndarray, t: np.ndarray, search_range: int) -> SymmetryOperationInfo:
    kind, det, trace, order, angle = core.classify_operation(W, t, search_range=search_range)
    op = {
        "index": index,
        "type": kind,
        "order": order,
        "det": det,
        "trace": trace,
        "angle": angle,
    }
    return SymmetryOperationInfo(
        index=index,
        W=np.asarray(W, dtype=int),
        t=np.asarray(t, dtype=float),
        kind=str(kind),
        order=None if order is None else int(order),
        det=int(det),
        trace=int(trace),
        angle_deg=None if angle is None else float(angle),
        international_symbol=core.operation_international_symbol(op),
    )


def convert_axis(axis: dict) -> AxisElement:
    return AxisElement(
        point_frac=np.asarray(axis["point"], dtype=float),
        direction_frac=np.asarray(axis["direction"], dtype=float),
        operation_indices=operation_indices(axis),
        motion_coeffs=tuple(none_or_array(x) for x in axis.get("motion_coeffs", [])),
    )


def convert_plane(plane: dict) -> PlaneElement:
    return PlaneElement(
        point_frac=np.asarray(plane["point"], dtype=float),
        normal_frac=np.asarray(plane["normal"], dtype=float),
        basis_frac=np.asarray(plane["basis"], dtype=float),
        operation_indices=operation_indices(plane),
        motion_coeffs=tuple(none_or_array(x) for x in plane.get("motion_coeffs", [])),
    )


def convert_center(center: dict) -> CenterElement:
    return CenterElement(
        point_frac=np.asarray(center["point"], dtype=float),
        operation_indices=operation_indices(center),
    )


def operation_indices(element: dict) -> tuple[int, ...]:
    return tuple(int(op["index"]) for op in element.get("operations", []))


def none_or_array(value):
    if value is None:
        return None
    return np.asarray(value, dtype=float)


def dataset_value(dataset, key: str):
    if isinstance(dataset, dict):
        return dataset[key]
    return getattr(dataset, key)
