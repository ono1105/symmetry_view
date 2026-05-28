from __future__ import annotations

from copy import deepcopy

import numpy as np
from pymatgen.core import Lattice, Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


def hexagonal_conventional_render_data(render_data: dict, *, symprec: float = 1e-3) -> dict | None:
    """Return display-only hexagonal conventional render data for an R lattice.

    This intentionally does not transform operation mappings or symmetry elements.
    It is a small, isolated conversion layer that can be wired into the viewer after
    the visual behavior is validated.
    """
    unit_cell = render_data.get("unit_cell")
    atoms = render_data.get("atoms") or []
    if unit_cell is None or not atoms:
        return None

    structure = _structure_from_render_data(render_data)
    try:
        analyzer = SpacegroupAnalyzer(structure, symprec=symprec)
        conventional = analyzer.get_conventional_standard_structure(keep_site_properties=True)
    except Exception:
        return None

    if not _is_hexagonal_conventional_r_lattice(conventional):
        return None

    converted = deepcopy(render_data)
    lattice = np.asarray(conventional.lattice.matrix, dtype=float)
    converted["unit_cell"] = _unit_cell_from_lattice(lattice)
    converted["atoms"] = _atoms_from_conventional_structure(conventional)
    converted["bounds_min"], converted["bounds_max"] = _bounds_from_atoms_and_cell(converted)
    metadata = dict(converted.get("metadata") or {})
    metadata["display_cell_setting"] = "hexagonal_conventional"
    metadata["display_lattice_parameters"] = _lattice_parameters(lattice)
    converted["metadata"] = metadata
    return converted


def _structure_from_render_data(render_data: dict) -> Structure:
    unit_cell = render_data["unit_cell"]
    atoms = render_data["atoms"]
    lattice = Lattice(np.asarray(unit_cell["lattice"], dtype=float))
    species = [str(atom.get("element") or atom.get("label") or atom.get("index")) for atom in atoms]
    frac_coords = [atom.get("frac") for atom in atoms]
    source_indices = [int(atom.get("index", index)) for index, atom in enumerate(atoms)]
    asymmetric_indices = [atom.get("asymmetric_index") for atom in atoms]
    generation_indices = [atom.get("generation_operation_index") for atom in atoms]
    site_properties = {"source_index": source_indices}
    if all(index is not None for index in asymmetric_indices):
        site_properties["asymmetric_index"] = asymmetric_indices
    if all(index is not None for index in generation_indices):
        site_properties["generation_operation_index"] = generation_indices
    return Structure(
        lattice,
        species,
        frac_coords,
        coords_are_cartesian=False,
        to_unit_cell=True,
        site_properties=site_properties,
    )


def _is_hexagonal_conventional_r_lattice(structure: Structure) -> bool:
    symbol = str(SpacegroupAnalyzer(structure, symprec=1e-3).get_space_group_symbol())
    if not symbol.startswith("R"):
        return False
    alpha, beta, gamma = structure.lattice.angles
    return (
        abs(alpha - 90.0) < 1e-5
        and abs(beta - 90.0) < 1e-5
        and abs(gamma - 120.0) < 1e-5
    )


def _atoms_from_conventional_structure(structure: Structure) -> list[dict]:
    source_indices = structure.site_properties.get("source_index", [None] * len(structure))
    asymmetric_indices = structure.site_properties.get("asymmetric_index", [None] * len(structure))
    generation_indices = structure.site_properties.get("generation_operation_index", [None] * len(structure))
    atoms = []
    for index, site in enumerate(structure):
        element = str(site.specie.symbol)
        atom = {
            "index": index,
            "element": element,
            "atomic_number": int(site.specie.Z),
            "cart": np.asarray(site.coords, dtype=float).tolist(),
            "frac": np.asarray(site.frac_coords, dtype=float).tolist(),
            "asymmetric_index": asymmetric_indices[index],
            "generation_operation_index": generation_indices[index],
            "source_atom_index": source_indices[index],
        }
        atoms.append(atom)
    return atoms


def _unit_cell_from_lattice(lattice: np.ndarray) -> dict:
    lattice = np.asarray(lattice, dtype=float)
    a, b, c = lattice[0], lattice[1], lattice[2]
    vertices = np.asarray(
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
    return {
        "lattice": lattice.tolist(),
        "vertices_cart": vertices.tolist(),
        "edges": [list(edge) for edge in edges],
    }


def _bounds_from_atoms_and_cell(render_data: dict) -> tuple[list[float], list[float]]:
    parts = []
    atoms = render_data.get("atoms") or []
    if atoms:
        parts.append(np.asarray([atom["cart"] for atom in atoms], dtype=float))
    unit_cell = render_data.get("unit_cell")
    if unit_cell is not None:
        parts.append(np.asarray(unit_cell["vertices_cart"], dtype=float))
    if not parts:
        zero = [0.0, 0.0, 0.0]
        return zero, zero
    points = np.vstack(parts)
    return points.min(axis=0).tolist(), points.max(axis=0).tolist()


def _lattice_parameters(lattice: np.ndarray) -> dict[str, float]:
    vectors = np.asarray(lattice, dtype=float)
    lengths = np.linalg.norm(vectors, axis=1)
    return {
        "a": float(lengths[0]),
        "b": float(lengths[1]),
        "c": float(lengths[2]),
        "alpha": _angle(vectors[1], vectors[2]),
        "beta": _angle(vectors[0], vectors[2]),
        "gamma": _angle(vectors[0], vectors[1]),
    }


def _angle(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom <= 1e-12:
        return 0.0
    value = float(np.clip(np.dot(a, b) / denom, -1.0, 1.0))
    return float(np.degrees(np.arccos(value)))
