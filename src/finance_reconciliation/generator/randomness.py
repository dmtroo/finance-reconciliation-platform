from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from typing import TypeVar

T = TypeVar("T")


class DeterministicRandom:
    """Local seeded RNG used by the synthetic source generator."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def chance(self, probability: float) -> bool:
        if not 0 <= probability <= 1:
            raise ValueError(
                f"Probability must be between 0 and 1; got {probability}"
            )

        return self._rng.random() < probability

    def randint(self, start: int, end: int) -> int:
        return self._rng.randint(start, end)

    def choice(self, values: Sequence[T]) -> T:
        if not values:
            raise ValueError("Cannot choose from an empty sequence")

        return self._rng.choice(values)

    def weighted_choice(
        self,
        weights: Mapping[T, float],
    ) -> T:
        if not weights:
            raise ValueError("Weights cannot be empty")

        items = list(weights.items())

        total = sum(weight for _, weight in items)

        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                f"Weights must sum to 1.0; got {total}"
            )

        threshold = self._rng.random()
        cumulative = 0.0

        for value, weight in items:
            cumulative += weight

            if threshold < cumulative:
                return value

        # Protect against floating-point boundary effects.
        return items[-1][0]