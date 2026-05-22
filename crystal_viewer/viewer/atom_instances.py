from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from crystal_viewer.viewer.display_atoms import display_atom_instances


@dataclass(frozen=True)
class ElementInstanceBatch:
    element: str
    atomic_number: int
    positions: np.ndarray
    atom_indices: tuple[int, ...]
    display_shift_fracs: np.ndarray
    primary_mask: np.ndarray
    items: tuple[dict, ...]


def element_instance_batches(render_data: dict, *, display_mode: str) -> tuple[ElementInstanceBatch, ...]:
    grouped: dict[str, list[dict]] = {}
    for item in display_atom_instances(render_data, display_mode=display_mode):
        atom = item["atom"]
        element = str(atom.get("element") or atom.get("label") or atom.get("index"))
        grouped.setdefault(element, []).append(item)

    batches = []
    for element in sorted(grouped):
        items = tuple(grouped[element])
        atoms = [item["atom"] for item in items]
        batches.append(
            ElementInstanceBatch(
                element=element,
                atomic_number=int(atoms[0].get("atomic_number", 0)),
                positions=np.asarray([item["cart"] for item in items], dtype=float),
                atom_indices=tuple(int(atom["index"]) for atom in atoms),
                display_shift_fracs=np.asarray(
                    [item.get("display_shift_frac", np.zeros(3)) for item in items],
                    dtype=float,
                ),
                primary_mask=np.asarray(
                    [bool(item.get("is_primary_image", True)) for item in items],
                    dtype=bool,
                ),
                items=items,
            )
        )
    return tuple(batches)
