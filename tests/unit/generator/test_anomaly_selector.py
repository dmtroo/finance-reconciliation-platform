from __future__ import annotations

import pytest

from finance_reconciliation.generator.anomalies.selector import (
    AnomalySelectionError,
    select_first_eligible,
)


def test_select_first_eligible_returns_first_match() -> None:
    rows = [
        {
            "id": "A",
            "eligible": False,
        },
        {
            "id": "B",
            "eligible": True,
        },
        {
            "id": "C",
            "eligible": True,
        },
    ]

    selected = select_first_eligible(
        rows,
        predicate=lambda row: bool(
            row["eligible"]
        ),
        label="test target",
    )

    assert selected["id"] == "B"


def test_select_first_eligible_is_deterministic() -> None:
    rows = [
        {
            "id": "A",
            "eligible": True,
        },
        {
            "id": "B",
            "eligible": True,
        },
    ]

    first = select_first_eligible(
        rows,
        predicate=lambda row: bool(
            row["eligible"]
        ),
        label="test target",
    )

    second = select_first_eligible(
        rows,
        predicate=lambda row: bool(
            row["eligible"]
        ),
        label="test target",
    )

    assert first == second
    assert first["id"] == "A"


def test_select_first_eligible_raises_when_no_match_exists() -> None:
    rows = [
        {
            "id": "A",
            "eligible": False,
        },
        {
            "id": "B",
            "eligible": False,
        },
    ]

    with pytest.raises(
        AnomalySelectionError,
        match="No eligible anomaly target for test target",
    ):
        select_first_eligible(
            rows,
            predicate=lambda row: bool(
                row["eligible"]
            ),
            label="test target",
        )