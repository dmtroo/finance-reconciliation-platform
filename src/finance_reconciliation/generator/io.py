from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


def serialize_value(value: Any) -> str:
    """Convert Python values to stable source-extract CSV representations."""

    if value is None:
        return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError(
                "Generator timestamps must be timezone-aware"
            )

        utc_value = value.astimezone(UTC)

        return utc_value.isoformat().replace("+00:00", "Z")

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return format(value, "f")

    return str(value)


def write_csv(
    path: Path,
    *,
    rows: Iterable[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> int:
    """Write canonical UTF-8 CSV output and return row count."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    row_count = 0

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file_handle:
        writer = csv.DictWriter(
            file_handle,
            fieldnames=fieldnames,
            extrasaction="raise",
            lineterminator="\n",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    field: serialize_value(row.get(field))
                    for field in fieldnames
                }
            )

            row_count += 1

    return row_count