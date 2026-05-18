from __future__ import annotations

from itertools import product

import numpy as np


def display_atom_instances(render_data: dict, *, display_mode: str = "expanded") -> list[dict]:
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return [
            {
                "atom": atom,
                "cart": np.asarray(atom["cart"], dtype=float),
                "display_shift_frac": np.zeros(3),
                "display_shift_cart": np.zeros(3),
                "is_primary_image": True,
            }
            for atom in render_data["atoms"]
        ]

    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    instances = []
    for atom in render_data["atoms"]:
        frac = atom.get("frac")
        if frac is None:
            instances.append(
                {
                    "atom": atom,
                    "cart": np.asarray(atom["cart"], dtype=float),
                    "display_shift_frac": np.zeros(3),
                    "display_shift_cart": np.zeros(3),
                    "is_primary_image": True,
                }
            )
            continue

        frac = np.asarray(frac, dtype=float)
        for shift in display_fractional_shifts(frac, display_mode=display_mode):
            shift_cart = shift @ lattice
            is_primary = (
                np.allclose(shift, 0.0, atol=1e-9)
                if display_mode == "source"
                else is_primary_centered_image(frac, shift)
            )
            instances.append(
                {
                    "atom": atom,
                    "cart": np.asarray(atom["cart"], dtype=float) + shift_cart,
                    "display_shift_frac": shift.copy(),
                    "display_shift_cart": shift_cart,
                    "is_primary_image": is_primary,
                }
            )
    return instances


def display_fractional_shifts(frac: np.ndarray, *, display_mode: str = "expanded") -> list[np.ndarray]:
    if display_mode == "source":
        return source_boundary_fractional_shifts(frac)
    margin = display_mode_margin(display_mode)
    shifts = []
    lower = -0.5 - margin
    upper = 0.5 + margin
    for shift in periodic_shifts(max(int(np.ceil(margin + 1.0)), 1)):
        image_frac = frac + shift
        if np.all(image_frac >= lower - 1e-9) and np.all(image_frac <= upper + 1e-9):
            shifts.append(shift)
    return shifts


def source_boundary_fractional_shifts(frac: np.ndarray, *, tolerance: float = 1e-6) -> list[np.ndarray]:
    shift_options = []
    for value in np.asarray(frac, dtype=float):
        options = [0.0]
        if value <= tolerance:
            options.append(1.0)
        if value >= 1.0 - tolerance:
            options.append(-1.0)
        shift_options.append(options)
    shifts = [
        np.asarray(shift, dtype=float)
        for shift in product(*shift_options)
    ]
    shifts.sort(key=lambda shift: (np.count_nonzero(shift), tuple(shift)))
    return shifts


def is_primary_centered_image(frac: np.ndarray, shift: np.ndarray) -> bool:
    image_frac = np.asarray(frac, dtype=float) + np.asarray(shift, dtype=float)
    return bool(np.all(image_frac >= -0.5 - 1e-9) and np.all(image_frac < 0.5 - 1e-9))


def periodic_shifts(limit: int = 1) -> np.ndarray:
    limit = max(int(limit), 0)
    return np.asarray(
        list(product(range(-limit, limit + 1), repeat=3)),
        dtype=float,
    )


def display_mode_margin(display_mode: str) -> float:
    if display_mode == "source":
        return 0.0
    if display_mode in ("expanded", "expanded_quarter"):
        return 0.25
    if display_mode == "expanded_half":
        return 0.5
    if display_mode.startswith("expanded_"):
        value = display_mode.removeprefix("expanded_").replace("_", ".")
        try:
            return max(float(value), 0.0)
        except ValueError:
            return 0.25
    return 0.25


def scene_span(render_data: dict) -> float:
    bounds_min = np.asarray(render_data["bounds_min"], dtype=float)
    bounds_max = np.asarray(render_data["bounds_max"], dtype=float)
    span = np.linalg.norm(bounds_max - bounds_min)
    return float(span if span > 1e-9 else 1.0)


def display_scene_span(render_data: dict, display_mode: str = "source") -> float:
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None or display_mode == "source":
        return scene_span(render_data)
    margin = display_mode_margin(display_mode)
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    lower = -0.5 - margin
    upper = 0.5 + margin
    corners_frac = np.asarray(list(product((lower, upper), repeat=3)), dtype=float)
    corners_cart = corners_frac @ lattice
    span = np.linalg.norm(corners_cart.max(axis=0) - corners_cart.min(axis=0))
    return float(span if span > 1e-9 else scene_span(render_data))


def display_scene_center(render_data: dict, display_mode: str = "source") -> np.ndarray:
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        atoms = render_data.get("atoms", [])
        if atoms:
            points = np.asarray([atom["cart"] for atom in atoms], dtype=float)
            return np.mean(points, axis=0)
        return np.zeros(3)
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    if display_mode == "source":
        return np.asarray([0.5, 0.5, 0.5], dtype=float) @ lattice
    return np.zeros(3)
