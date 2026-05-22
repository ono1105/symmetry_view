from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ChallengeKind = Literal["operation_symbol", "operation_direction"]


@dataclass(frozen=True)
class SymmetryChallenge:
    kind: ChallengeKind
    prompt: str
    expected_operation_index: int
    expected_value: str


@dataclass(frozen=True)
class ChallengeResult:
    correct: bool
    expected_operation_index: int
    selected_operation_index: int | None
    hint: str


def operation_symbol_challenge(operation: dict) -> SymmetryChallenge:
    symbol = str(operation.get("display_symbol") or operation.get("symbol") or operation.get("label") or "")
    return SymmetryChallenge(
        kind="operation_symbol",
        prompt=f"Select operation {symbol}.",
        expected_operation_index=int(operation["index"]),
        expected_value=symbol,
    )


def check_operation_choice(
    challenge: SymmetryChallenge,
    selected_operation_index: int | None,
) -> ChallengeResult:
    correct = selected_operation_index == challenge.expected_operation_index
    hint = "" if correct else f"Look for {challenge.expected_value}."
    return ChallengeResult(
        correct=correct,
        expected_operation_index=challenge.expected_operation_index,
        selected_operation_index=selected_operation_index,
        hint=hint,
    )

