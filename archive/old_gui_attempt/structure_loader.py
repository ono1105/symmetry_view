from __future__ import annotations

import numpy as np
from pymatgen.core import Structure

from .models import CrystalStructureData, RenderAtom


def load_crystal_from_cif(cif_path: str) -> CrystalStructureData:
    structure = Structure.from_file(cif_path)
    lattice = np.asarray(structure.lattice.matrix, dtype=float)

    atoms: list[RenderAtom] = []
    for index, site in enumerate(structure):
        specie = site.specie
        atoms.append(
            RenderAtom(
                index=index,
                element=specie.symbol,
                atomic_number=int(specie.Z),
                frac=np.asarray(site.frac_coords, dtype=float),
                cart=np.asarray(site.coords, dtype=float),
            )
        )

    return CrystalStructureData(
        lattice=lattice,
        atoms=atoms,
        source_file=cif_path,
        pymatgen_structure=structure,
    )


def structure_to_spglib_cell(structure: Structure):
    lattice = np.asarray(structure.lattice.matrix, dtype=float)
    positions = np.asarray(structure.frac_coords, dtype=float)
    numbers = [int(site.specie.Z) for site in structure]
    return lattice, positions, numbers

