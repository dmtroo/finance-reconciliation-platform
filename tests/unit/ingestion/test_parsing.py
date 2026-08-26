from datetime import (
    UTC,
    date,
    datetime,
)
from decimal import Decimal

import pytest

from finance_reconciliation.ingestion.parsing import (
    parse_boolean,
    parse_date,
    parse_decimal,
    parse_integer,
    parse_timestamp,
)


def test_empty_values_become_none() -> None:
    assert parse_integer("") is None
    assert parse_date("") is None
    assert parse_timestamp("") is None
    assert parse_decimal("") is None
    assert parse_boolean("") is None


def test_numeric_values_are_typed() -> None:
    assert parse_integer(
        "8999"
    ) == 8999

    assert parse_decimal(
        "0.92500000"
    ) == Decimal(
        "0.92500000"
    )


def test_date_is_typed() -> None:
    assert parse_date(
        "2026-01-31"
    ) == date(
        2026,
        1,
        31,
    )


def test_utc_timestamp_is_typed() -> None:
    assert parse_timestamp(
        "2026-01-31T10:30:00Z"
    ) == datetime(
        2026,
        1,
        31,
        10,
        30,
        tzinfo=UTC,
    )


def test_boolean_is_typed() -> None:
    assert parse_boolean(
        "true"
    ) is True

    assert parse_boolean(
        "false"
    ) is False


def test_invalid_boolean_fails() -> None:
    with pytest.raises(
        ValueError
    ):
        parse_boolean(
            "yes"
        )