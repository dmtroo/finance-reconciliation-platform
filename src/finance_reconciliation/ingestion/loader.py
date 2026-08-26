from __future__ import annotations

import csv
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from psycopg import sql

from finance_reconciliation.ingestion.database import (
    connect,
)
from finance_reconciliation.ingestion.parsing import (
    parse_value,
)
from finance_reconciliation.ingestion.source_run import (
    SourceRun,
    load_source_run,
)
from finance_reconciliation.ingestion.specs import (
    TABLE_SPECS,
    TableSpec,
)

BATCH_SIZE = 1000


def iter_parsed_rows(
    *,
    path: Path,
    spec: TableSpec,
) -> Iterator[
    tuple[Any, ...]
]:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file_handle:
        reader = csv.DictReader(
            file_handle
        )

        for row in reader:
            yield tuple(
                parse_value(
                    column.kind,
                    row[column.name],
                )
                for column in spec.columns
            )


def batched(
    rows: Iterator[
        tuple[Any, ...]
    ],
    size: int = BATCH_SIZE,
) -> Iterator[
    list[tuple[Any, ...]]
]:
    batch: list[
        tuple[Any, ...]
    ] = []

    for row in rows:
        batch.append(row)

        if len(batch) >= size:
            yield batch
            batch = []

    if batch:
        yield batch


def build_insert_sql(
    spec: TableSpec,
):
    source_columns = [
        column.name
        for column in spec.columns
    ]

    all_columns = [
        *source_columns,
        "_loaded_at",
        "_batch_id",
    ]

    identifiers = sql.SQL(
        ", "
    ).join(
        sql.Identifier(
            name
        )
        for name in all_columns
    )

    placeholders = sql.SQL(
        ", "
    ).join(
        sql.Placeholder()
        for _ in all_columns
    )

    conflict_columns = sql.SQL(
        ", "
    ).join(
        sql.Identifier(
            name
        )
        for name in spec.primary_key
    )

    base = sql.SQL(
        """
        insert into {}.{} ({})
        values ({})
        """
    ).format(
        sql.Identifier(
            spec.schema
        ),
        sql.Identifier(
            spec.table
        ),
        identifiers,
        placeholders,
    )

    if spec.mode == "append":
        return base + sql.SQL(
            " on conflict ({}) do nothing"
        ).format(
            conflict_columns
        )

    update_columns = [
        name
        for name in all_columns
        if name
        not in spec.primary_key
    ]

    assignments = sql.SQL(
        ", "
    ).join(
        sql.SQL(
            "{} = excluded.{}"
        ).format(
            sql.Identifier(
                name
            ),
            sql.Identifier(
                name
            ),
        )
        for name
        in update_columns
    )

    return base + sql.SQL(
        """
        on conflict ({})
        do update set {}
        """
    ).format(
        conflict_columns,
        assignments,
    )


def load_table(
    *,
    cursor,
    source_run: SourceRun,
    spec: TableSpec,
    loaded_at: datetime,
) -> int:
    path = (
        source_run.run_dir
        / spec.relative_path
    )

    query = build_insert_sql(
        spec
    )

    row_count = 0

    parsed_rows = iter_parsed_rows(
        path=path,
        spec=spec,
    )

    for batch in batched(
        parsed_rows
    ):
        parameters = [
            (
                *row,
                loaded_at,
                source_run.batch_id,
            )
            for row in batch
        ]

        cursor.executemany(
            query,
            parameters,
        )

        row_count += len(
            batch
        )

    return row_count


def load_run_directory(
    run_dir: str | Path,
) -> dict[str, int]:
    source_run = load_source_run(
        run_dir
    )

    loaded_at = datetime.now(
        UTC
    )

    source_counts: dict[
        str,
        int,
    ] = {}

    with connect() as connection, connection.cursor() as cursor:
        for spec in TABLE_SPECS:
            source_counts[
                spec.key
            ] = load_table(
                cursor=cursor,
                source_run=source_run,
                spec=spec,
                loaded_at=loaded_at,
            )

    return source_counts