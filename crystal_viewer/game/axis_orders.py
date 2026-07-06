"""Judging for the "how many-fold is this rotation axis?" puzzle.

Renderer-independent: consumes ``render_data`` only. See ``docs/PUZZLE_SPEC.md``.

For a rotation axis the correct answer is the set of rotation orders that hold
about it (the divisors >= 2 of its principal order); an infinite axis (C-inf on
a linear molecule) accepts every option. Collinear axis elements are merged, and
symmetry-equivalent axes (e.g. the x/y/z C4 axes of an octahedron) are collapsed
into one representative via their orbit under the group operations (option A).
"""

from __future__ import annotations

import numpy as np

ROTATION_ORDER_OPTIONS: tuple[int, ...] = (2, 3, 4, 6)

_DIRECTION_TOL = 1e-4


def canonical_direction(vector) -> np.ndarray | None:
    """Unit direction with a canonical sign (first significant component > 0)."""
    vec = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(vec))
    if norm < 1e-9:
        return None
    vec = vec / norm
    for component in vec:
        if abs(component) > 1e-6:
            if component < 0:
                vec = -vec
            break
    return vec


def _geometric_rotation_axes(render_data: dict) -> list[dict]:
    """Merge collinear rotation-axis elements into geometric axes.

    Returns dicts with ``direction`` (canonical), ``point``, the set of pure
    rotation ``orders`` present, and whether an infinite (C-inf) rotation lives
    on the axis.
    """
    operations = {int(op["index"]): op for op in render_data.get("operations", [])}
    groups: dict[tuple, dict] = {}
    for axis in render_data.get("axes", []):
        direction = canonical_direction(axis.get("direction_cart"))
        if direction is None:
            continue
        orders: set[int] = set()
        infinite = False
        for index in axis.get("operation_indices", []):
            operation = operations.get(int(index))
            if operation is None:
                continue
            kind = str(operation.get("kind", ""))
            if kind == "rotation_infinite":
                infinite = True
            elif kind.startswith("rotation_"):
                order = operation.get("order")
                if order is not None:
                    orders.add(int(order))
        if not orders and not infinite:
            continue
        # Molecules share the centre, so the canonical direction identifies the
        # line. (Crystals with parallel axes at different points need the point
        # in the key too; out of scope for the molecule-first puzzle.)
        key = tuple(np.round(direction, 4))
        group = groups.get(key)
        if group is None:
            group = {
                "direction": direction,
                "point": np.asarray(axis.get("point_cart", [0.0, 0.0, 0.0]), dtype=float),
                "orders": set(),
                "infinite": False,
            }
            groups[key] = group
        group["orders"] |= orders
        group["infinite"] = group["infinite"] or infinite
    return list(groups.values())


def _equivalence_classes(axes: list[dict], render_data: dict) -> list[list[int]]:
    """Group geometric axes by their orbit under all group operations."""
    matrices = [
        np.asarray(op["matrix_cart"], dtype=float)
        for op in render_data.get("operations", [])
        if op.get("matrix_cart") is not None
    ]
    directions = [axis["direction"] for axis in axes]
    parent = list(range(len(axes)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    def match(direction: np.ndarray) -> int | None:
        canonical = canonical_direction(direction)
        if canonical is None:
            return None
        for index, other in enumerate(directions):
            if np.linalg.norm(canonical - other) < _DIRECTION_TOL:
                return index
        return None

    for i, axis in enumerate(axes):
        for matrix in matrices:
            target = match(matrix @ axis["direction"])
            if target is not None:
                union(i, target)

    classes: dict[int, list[int]] = {}
    for i in range(len(axes)):
        classes.setdefault(find(i), []).append(i)
    return list(classes.values())


def rotation_axis_questions(
    render_data: dict,
    *,
    options: tuple[int, ...] = ROTATION_ORDER_OPTIONS,
) -> list[dict]:
    """Return one quiz question per symmetry-inequivalent rotation axis.

    Each question: ``direction_cart``, ``point_cart``, ``correct_orders``
    (sorted subset of ``options``), ``equivalent_count`` (axes in the class),
    ``infinite`` (C-inf). Axes carrying an order outside ``options`` (C5, C7…)
    are excluded from the v1 pool.
    """
    axes = _geometric_rotation_axes(render_data)
    questions = []
    for members in _equivalence_classes(axes, render_data):
        axis = axes[members[0]]
        if axis["infinite"]:
            correct = list(options)
        else:
            if any(order not in options for order in axis["orders"]):
                continue
            correct = sorted(order for order in options if order in axis["orders"])
            if not correct:
                continue
        questions.append(
            {
                "direction_cart": axis["direction"].tolist(),
                "point_cart": axis["point"].tolist(),
                "correct_orders": correct,
                "equivalent_count": len(members),
                "infinite": bool(axis["infinite"]),
            }
        )
    questions.sort(key=lambda q: (-max(q["correct_orders"]), q["correct_orders"]))
    return questions


def public_questions(
    render_data: dict,
    *,
    options: tuple[int, ...] = ROTATION_ORDER_OPTIONS,
) -> list[dict]:
    """Questions for the client with the correct answer withheld."""
    return [
        {
            "id": index,
            "direction_cart": question["direction_cart"],
            "point_cart": question["point_cart"],
            "options": list(options),
            "equivalent_count": question["equivalent_count"],
            "infinite": question["infinite"],
        }
        for index, question in enumerate(rotation_axis_questions(render_data, options=options))
    ]


def check_answer(
    render_data: dict,
    question_id: int,
    selected_orders,
    *,
    options: tuple[int, ...] = ROTATION_ORDER_OPTIONS,
) -> dict | None:
    """Judge one answer and reveal the correct set. ``None`` if id is unknown."""
    questions = rotation_axis_questions(render_data, options=options)
    if not 0 <= question_id < len(questions):
        return None
    correct = questions[question_id]["correct_orders"]
    selected = sorted({int(order) for order in selected_orders})
    return {
        "correct": selected == correct,
        "correct_orders": correct,
        "selected_orders": selected,
    }
