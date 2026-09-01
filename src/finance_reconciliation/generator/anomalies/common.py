from __future__ import annotations

from datetime import (
    date,
    datetime,
)
from decimal import Decimal
from typing import Any

from finance_reconciliation.generator.anomalies.selector import (
    AnomalySelectionError,
)

TableRow = dict[str, Any]
TableRows = list[TableRow]
Tables = dict[str, TableRows]


def get_table(
    tables: Tables,
    name: str,
) -> TableRows:
    try:
        return tables[name]
    except KeyError as exc:
        raise AnomalySelectionError(
            f"Missing generated table: {name}"
        ) from exc


def row_by_id(
    rows: TableRows,
    *,
    id_field: str,
    entity_id: str,
) -> TableRow:
    for row in rows:
        if (
            str(row[id_field])
            == entity_id
        ):
            return row

    raise AnomalySelectionError(
        f"Could not find "
        f"{id_field}={entity_id}"
    )


def as_date(
    value: Any,
) -> date:
    if isinstance(
        value,
        datetime,
    ):
        return value.date()

    if isinstance(
        value,
        date,
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        return date.fromisoformat(
            value[:10]
        )

    raise TypeError(
        f"Cannot convert "
        f"{value!r} to date"
    )


def as_datetime(
    value: Any,
) -> datetime:
    if isinstance(
        value,
        datetime,
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        return datetime.fromisoformat(value)

    raise TypeError(
        f"Cannot convert "
        f"{value!r} to datetime"
    )


def timestamp_like(
    original: Any,
    value: datetime,
) -> Any:
    if isinstance(
        original,
        str,
    ):
        return value.isoformat()

    return value


def decimal_like(
    original: Any,
    value: Decimal,
) -> Any:
    if isinstance(
        original,
        Decimal,
    ):
        return value

    if isinstance(
        original,
        str,
    ):
        return format(
            value,
            "f",
        )

    if isinstance(
        original,
        float,
    ):
        return float(
            value
        )

    return value