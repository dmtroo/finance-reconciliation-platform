from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


class AnomalySelectionError(RuntimeError):
    """Raised when no deterministic anomaly target can be selected."""


def select_first_eligible(
    rows: Sequence[T],
    *,
    predicate: Callable[[T], bool],
    label: str,
) -> T:
    eligible = [
        row
        for row in rows
        if predicate(row)
    ]

    if not eligible:
        raise AnomalySelectionError(
            f"No eligible anomaly target for {label}"
        )

    return eligible[0]