"""Judging for the "identify the operation" puzzle (docs/PUZZLE_SPEC.md).

An animation of one symmetry operation is shown and the player names it: the kind
(rotation / mirror / inversion / rotoreflection Sn / rotoinversion -n) and, where
it applies, the fold. Renderer-independent: consumes ``render_data`` only.

Motionless operations (all atoms map to themselves) are dropped — they are
indistinguishable from the identity and have no answer. Operations whose
animation looks identical are *merged into one question that accepts any of
their names*: e.g. for CO2 the inversion and the perpendicular mirror move both
O atoms the same straight way, so one question is asked and both 反転 and 鏡映
count as correct. (Dropping them instead would leave CO2 with no question at all,
which reads as "no symmetry".)

The reveal reuses ``/api/animation_path``, so each public question carries its
operation index; the name/fold is revealed only by ``check_answer``.
"""

from __future__ import annotations

import numpy as np

# Canonical answer kinds (the client maps these to Japanese labels).
ROTATION = "rotation"          # 回転
MIRROR = "mirror"              # 鏡映
INVERSION = "inversion"        # 反転
ROTOREFLECTION = "rotoreflection"  # 回映 (Sn, molecules)
ROTOINVERSION = "rotoinversion"    # 回反 (-n, crystals)
SCREW = "screw"                # らせん (screw axis, crystals)
GLIDE = "glide"                # 映進 (glide plane, crystals)

# Operation scopes. "normal" and "hard" are kept for API/test compatibility;
# the puzzle UI uses "all" so operation-identify is one quiz, not split by
# difficulty.
NORMAL = "normal"
HARD = "hard"
ALL = "all"

ROTATION_ORDER_OPTIONS: tuple[int, ...] = (2, 3, 4, 6)
IMPROPER_ORDER_OPTIONS: tuple[int, ...] = (3, 4, 6)

# An operation that maps every atom onto its own position shows no motion, so it
# is dropped (indistinguishable from the identity). Matches the molecule
# fixed-point tolerance used elsewhere (PointGroupAnalyzer is only ~1e-4 exact).
_NO_MOTION_TOL = 1e-2

# Operations whose animation follows a curved (rotational) path, as opposed to
# the straight motion of a mirror/inversion. Used to tell whether two operations
# would look the same.
_CURVED_PREFIXES = ("rotation_", "screw", "improper_", "rotoinversion")


def _improper_index(operation: dict, *, invert: bool) -> int | None:
    """The Sn / -n index of an improper operation, read from its rotation angle.

    The stored kind number is the matrix period (S3 has period 6), so the true
    index comes from the angle: trace(S)=2cosθ-1 for a rotoreflection, and
    trace(-n)=-(2cosθ+1) for a rotoinversion (hence the sign flip).
    """
    matrix = operation.get("matrix_cart")
    if matrix is None:
        return None
    m = np.asarray(matrix, dtype=float)
    if np.linalg.det(m) > 0:  # a proper rotation slipped in
        return None
    cos_theta = (np.trace(m) + 1.0) / 2.0
    if invert:
        cos_theta = -cos_theta
    cos_theta = float(np.clip(cos_theta, -1.0, 1.0))
    theta = float(np.degrees(np.arccos(cos_theta)))
    if theta < 1e-6:  # S1 = mirror, S2 = inversion — handled by their own kinds
        return None
    index = round(360.0 / theta)
    return int(index) if index >= 2 else None


def _operation_answer(operation: dict) -> dict | None:
    """The basic-operation answer for one render_data operation, or None."""
    kind = str(operation.get("kind", ""))
    if kind.startswith("rotation_") and kind != "rotation_infinite":
        order = operation.get("order")
        if order is None or int(order) not in ROTATION_ORDER_OPTIONS:
            return None
        return {"kind": ROTATION, "order": int(order)}
    if kind == "mirror":
        return {"kind": MIRROR, "order": None}
    if kind == "inversion":
        return {"kind": INVERSION, "order": None}
    if kind.startswith("improper_"):
        index = _improper_index(operation, invert=False)
        if index is None or index not in IMPROPER_ORDER_OPTIONS:
            return None
        return {"kind": ROTOREFLECTION, "order": index}
    if kind.startswith("rotoinversion"):
        index = _improper_index(operation, invert=True)
        if index is None or index not in IMPROPER_ORDER_OPTIONS:
            return None
        return {"kind": ROTOINVERSION, "order": index}
    return None


def _translation_answer(operation: dict) -> dict | None:
    """The hard-mode answer (a screw axis or glide plane), or None."""
    kind = str(operation.get("kind", ""))
    if kind.startswith("screw"):
        order = operation.get("order")
        if order is None or int(order) not in ROTATION_ORDER_OPTIONS:
            return None
        return {"kind": SCREW, "order": int(order)}
    if kind == "glide":
        return {"kind": GLIDE, "order": None}
    return None


def _answer_for(operation: dict, difficulty: str) -> dict | None:
    if difficulty == HARD:
        return _translation_answer(operation)
    if difficulty == ALL:
        return _translation_answer(operation) or _operation_answer(operation)
    return _operation_answer(operation)


def _transform(operation: dict, atoms: list[dict]) -> np.ndarray | None:
    """Cartesian image of every atom under the operation (rows aligned to atoms)."""
    matrix = operation.get("matrix_cart")
    if matrix is None:
        return None
    m = np.asarray(matrix, dtype=float)
    translation = np.asarray(operation.get("translation_cart") or [0.0, 0.0, 0.0], dtype=float)
    points = np.array([atom["cart"] for atom in atoms if atom.get("cart") is not None], dtype=float)
    if points.size == 0:
        return points
    return points @ m.T + translation


def _moves_any_atom(operation: dict, atoms: list[dict], starts: np.ndarray) -> bool:
    """True if the operation visibly displaces at least one atom."""
    image = _transform(operation, atoms)
    if image is None or image.size == 0:
        return True  # unknown geometry — keep it rather than silently drop
    return bool(np.linalg.norm(image - starts, axis=1).max() > _NO_MOTION_TOL)


def _visual_signature(operation: dict, atoms: list[dict]) -> tuple | None:
    """A key that is equal for two operations whose animations look the same.

    Same motion character (curved vs straight) AND same atom destinations means
    the two animations are visually identical.
    """
    image = _transform(operation, atoms)
    if image is None:
        return None
    kind = str(operation.get("kind", ""))
    motion = "curved" if any(kind.startswith(prefix) for prefix in _CURVED_PREFIXES) else "straight"
    return (motion, tuple(map(tuple, np.round(image, 2))))


def identify_questions(render_data: dict, difficulty: str = NORMAL) -> list[dict]:
    """One question per distinct animation among the in-scope, moving operations.

    Operations that look the same are merged into a single question whose
    ``answers`` lists every name that motion can validly carry (usually one; more
    than one when e.g. an inversion and a mirror coincide)."""
    atoms = [atom for atom in render_data.get("atoms", []) if atom.get("cart") is not None]
    if not atoms:
        return []
    starts = np.array([atom["cart"] for atom in atoms], dtype=float)

    # Group by visual signature, preserving first-seen order for stable ids.
    groups: dict[tuple, dict] = {}
    for operation in render_data.get("operations", []):
        answer = _answer_for(operation, difficulty)
        if answer is None:
            continue
        if not _moves_any_atom(operation, atoms, starts):
            continue
        signature = _visual_signature(operation, atoms)
        group = groups.get(signature)
        if group is None:
            group = {"operation_index": int(operation["index"]), "answers": [], "seen": set()}
            groups[signature] = group
        key = (answer["kind"], answer["order"])
        if key not in group["seen"]:
            group["seen"].add(key)
            group["answers"].append(answer)

    return [
        {"operation_index": group["operation_index"], "answers": group["answers"]}
        for group in groups.values()
    ]


def public_questions(render_data: dict, difficulty: str = NORMAL) -> list[dict]:
    """Questions for the client (operation to animate; the name is withheld).

    Each question carries an opaque ``group`` id shared by questions with the same
    answer, so the client can sample answer types evenly (a highly symmetric
    crystal has many equivalent operations of the common kinds) without learning
    what the answer is.
    """
    group_ids: dict[tuple, int] = {}
    public = []
    for index, question in enumerate(identify_questions(render_data, difficulty)):
        signature = tuple(
            sorted((a["kind"], -1 if a["order"] is None else a["order"]) for a in question["answers"])
        )
        group = group_ids.setdefault(signature, len(group_ids))
        public.append(
            {"id": index, "operation_index": question["operation_index"], "group": group}
        )
    return public


def _answer_matches(answer: dict, selected_kind, selected_order) -> bool:
    if str(selected_kind) != answer["kind"]:
        return False
    if answer["order"] is None:
        return True
    try:
        return int(selected_order) == answer["order"]
    except (TypeError, ValueError):
        return False  # e.g. the ∞ molecule distractor never matches a finite fold


def check_answer(
    render_data: dict,
    question_id: int,
    selected_kind,
    selected_order=None,
    difficulty: str = NORMAL,
) -> dict | None:
    """Judge one answer and reveal the operation. ``None`` if id is unknown.

    ``answers`` holds every acceptable name; a match with any of them is correct.
    """
    questions = identify_questions(render_data, difficulty)
    if not 0 <= question_id < len(questions):
        return None
    question = questions[question_id]
    correct = any(_answer_matches(answer, selected_kind, selected_order) for answer in question["answers"])
    return {
        "correct": correct,
        "answers": question["answers"],
        "operation_index": question["operation_index"],
    }
