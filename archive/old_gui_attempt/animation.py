from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np

from .models import CrystalAxis, CrystalSymmetryOperation, RenderAtom


def choose_nearest_periodic_image(
    start_frac: np.ndarray, target_frac: np.ndarray, lattice: np.ndarray
) -> np.ndarray:
    best = None
    best_dist = None
    for shift in itertools.product([-1, 0, 1], repeat=3):
        candidate = target_frac + np.asarray(shift, dtype=float)
        dist = np.linalg.norm((candidate - start_frac) @ lattice)
        if best is None or dist < best_dist:
            best = candidate
            best_dist = dist
    return np.asarray(best, dtype=float)


def rodrigues(axis: np.ndarray, angle: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    norm = np.linalg.norm(axis)
    if norm < 1e-12:
        return np.eye(3)
    x, y, z = axis / norm
    k = np.array(
        [
            [0.0, -z, y],
            [z, 0.0, -x],
            [-y, x, 0.0],
        ]
    )
    return np.eye(3) + np.sin(angle) * k + (1.0 - np.cos(angle)) * (k @ k)


def rotation_angle_from_matrix(
    W: np.ndarray,
    lattice: np.ndarray,
    axis_direction_cart: np.ndarray,
    order: int | None,
) -> float:
    if order and order > 1:
        transform_cart = lattice.T @ W @ np.linalg.inv(lattice.T)
        skew = np.array(
            [
                transform_cart[2, 1] - transform_cart[1, 2],
                transform_cart[0, 2] - transform_cart[2, 0],
                transform_cart[1, 0] - transform_cart[0, 1],
            ]
        )
        axis = axis_direction_cart / max(np.linalg.norm(axis_direction_cart), 1e-12)
        sin_theta = 0.5 * float(np.dot(axis, skew))
        cos_theta = np.clip((np.trace(transform_cart) - 1.0) / 2.0, -1.0, 1.0)
        theta = float(np.arctan2(sin_theta, cos_theta))
        return theta if abs(theta) > 1e-8 else 2.0 * np.pi / order
    return 0.0


@dataclass
class AtomAnimationPath:
    atom_index: int
    start_cart: np.ndarray
    target_cart: np.ndarray
    axis_point_cart: np.ndarray | None = None
    axis_direction_cart: np.ndarray | None = None
    theta: float = 0.0
    axis_translation_cart: np.ndarray | None = None

    def position_at(self, s: float, circular: bool) -> np.ndarray:
        if not circular or self.axis_point_cart is None or self.axis_direction_cart is None:
            return (1.0 - s) * self.start_cart + s * self.target_cart

        rotation = rodrigues(self.axis_direction_cart, s * self.theta)
        rotated = self.axis_point_cart + rotation @ (self.start_cart - self.axis_point_cart)
        if self.axis_translation_cart is not None:
            rotated = rotated + s * self.axis_translation_cart
        return rotated


def build_animation_paths(
    atoms: list[RenderAtom],
    selected_indices: set[int],
    operation: CrystalSymmetryOperation,
    lattice: np.ndarray,
    mode: str,
    axis: CrystalAxis | None = None,
) -> tuple[list[AtomAnimationPath], bool]:
    atom_indices = range(len(atoms)) if mode == "all" else sorted(selected_indices)
    paths: list[AtomAnimationPath] = []
    circular = operation.kind.startswith("rotation") or operation.kind.startswith("screw")

    axis_point_cart = None
    axis_direction_cart = None
    theta = 0.0
    if circular and axis is not None:
        axis_point_cart = axis.point_frac @ lattice
        axis_direction_cart = axis.direction_frac @ lattice
        theta = rotation_angle_from_matrix(operation.W, lattice, axis_direction_cart, operation.order)

    for atom_index in atom_indices:
        atom = atoms[atom_index]
        if atom.frac is None:
            continue

        start_frac = np.asarray(atom.frac, dtype=float)
        raw_target_frac = operation.W @ start_frac + operation.t
        target_frac = choose_nearest_periodic_image(start_frac, raw_target_frac, lattice)
        start_cart = start_frac @ lattice
        target_cart = target_frac @ lattice

        axis_translation_cart = None
        if circular and axis_point_cart is not None and axis_direction_cart is not None:
            end_after_rotation = axis_point_cart + rodrigues(axis_direction_cart, theta) @ (
                start_cart - axis_point_cart
            )
            axis_translation_cart = target_cart - end_after_rotation

        paths.append(
            AtomAnimationPath(
                atom_index=atom_index,
                start_cart=start_cart,
                target_cart=target_cart,
                axis_point_cart=axis_point_cart,
                axis_direction_cart=axis_direction_cart,
                theta=theta,
                axis_translation_cart=axis_translation_cart,
            )
        )

    return paths, circular
