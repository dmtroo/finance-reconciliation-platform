from __future__ import annotations

import argparse
from pathlib import Path

from psycopg import sql

from finance_reconciliation.ecb.extractor import (
    read_raw_csv,
)
from finance_reconciliation.ingestion.database import (
    connect,
)
from finance_reconciliation.ingestion.source_run import (
    SourceRun,
    load_source_run,
)
from finance_reconciliation.ingestion.specs import (
    TABLE_SPECS,
)
from finance_reconciliation.paths import (
    resolve_project_path,
)

EXPECTED_RAW_RELATIONS = {
    (
        spec.schema,
        spec.table,
    )
    for spec in TABLE_SPECS
} | {
    (
        "raw_ecb",
        "fx_rates",
    )
}


class M1ValidationError(
    RuntimeError
):
    """Raised when the M1 RAW acceptance contract fails."""


def relation_count(
    cursor,
    *,
    schema: str,
    table: str,
) -> int:
    query = sql.SQL(
        "select count(*) from {}.{}"
    ).format(
        sql.Identifier(schema),
        sql.Identifier(table),
    )

    cursor.execute(query)

    row = cursor.fetchone()

    if row is None:
        raise M1ValidationError(
            f"Could not count {schema}.{table}"
        )

    return int(
        row[0]
    )


def null_metadata_count(
    cursor,
    *,
    schema: str,
    table: str,
) -> int:
    query = sql.SQL(
        """
        select count(*)
        from {}.{}
        where
            _loaded_at is null
            or _batch_id is null
        """
    ).format(
        sql.Identifier(schema),
        sql.Identifier(table),
    )

    cursor.execute(query)

    row = cursor.fetchone()

    if row is None:
        raise M1ValidationError(
            "Could not validate ingestion "
            f"metadata for {schema}.{table}"
        )

    return int(
        row[0]
    )


def batch_ids(
    cursor,
    *,
    schema: str,
    table: str,
) -> set[str]:
    query = sql.SQL(
        """
        select distinct _batch_id
        from {}.{}
        order by _batch_id
        """
    ).format(
        sql.Identifier(schema),
        sql.Identifier(table),
    )

    cursor.execute(query)

    return {
        str(row[0])
        for row in cursor.fetchall()
    }


def validate_raw_relation_set(
    cursor,
) -> None:
    cursor.execute(
        """
        select
            table_schema,
            table_name
        from information_schema.tables
        where
            table_type = 'BASE TABLE'
            and table_schema in (
                'raw_billing',
                'raw_psp',
                'raw_bank',
                'raw_accounting',
                'raw_ecb'
            )
        """
    )

    actual = {
        (
            str(row[0]),
            str(row[1]),
        )
        for row in cursor.fetchall()
    }

    if actual != EXPECTED_RAW_RELATIONS:
        missing = (
            EXPECTED_RAW_RELATIONS
            - actual
        )

        unexpected = (
            actual
            - EXPECTED_RAW_RELATIONS
        )

        raise M1ValidationError(
            "RAW relation contract mismatch. "
            f"Missing={sorted(missing)}; "
            f"unexpected={sorted(unexpected)}"
        )

    print(
        "PASS RAW relation contract: "
        "exactly 10 source tables"
    )


def validate_synthetic_sources(
    cursor,
    *,
    source_run: SourceRun,
) -> None:
    expected_counts = (
        source_run.manifest[
            "row_counts"
        ]
    )

    for spec in TABLE_SPECS:
        expected = int(
            expected_counts[
                spec.key
            ]
        )

        actual = relation_count(
            cursor,
            schema=spec.schema,
            table=spec.table,
        )

        if actual != expected:
            raise M1ValidationError(
                f"{spec.schema}.{spec.table} "
                "row-count mismatch: "
                f"expected={expected}, "
                f"actual={actual}. "
                "M1 acceptance expects a clean "
                "local RAW database."
            )

        null_metadata = (
            null_metadata_count(
                cursor,
                schema=spec.schema,
                table=spec.table,
            )
        )

        if null_metadata != 0:
            raise M1ValidationError(
                f"{spec.schema}.{spec.table} "
                f"has {null_metadata} rows "
                "with missing ingestion metadata"
            )

        batches = batch_ids(
            cursor,
            schema=spec.schema,
            table=spec.table,
        )

        if (
            expected > 0
            and batches
            != {
                source_run.batch_id
            }
        ):
            raise M1ValidationError(
                f"{spec.schema}.{spec.table} "
                "contains unexpected batch IDs: "
                f"{sorted(batches)}"
            )

        print(
            "PASS "
            f"{spec.schema}.{spec.table}: "
            f"{actual:,} rows"
        )


def validate_ecb_source(
    cursor,
    *,
    ecb_file: Path,
) -> None:
    observations = (
        read_raw_csv(
            ecb_file
        )
    )

    expected = {
        (
            observation.rate_date,
            observation.currency,
        ): observation.units_per_eur
        for observation
        in observations
    }

    cursor.execute(
        """
        select
            rate_date,
            currency,
            units_per_eur
        from raw_ecb.fx_rates
        order by
            rate_date,
            currency
        """
    )

    actual = {
        (
            row[0],
            str(row[1]),
        ): row[2]
        for row
        in cursor.fetchall()
    }

    if actual != expected:
        expected_keys = set(
            expected
        )

        actual_keys = set(
            actual
        )

        missing = (
            expected_keys
            - actual_keys
        )

        unexpected = (
            actual_keys
            - expected_keys
        )

        mismatched = {
            key
            for key
            in (
                expected_keys
                & actual_keys
            )
            if (
                expected[key]
                != actual[key]
            )
        }

        raise M1ValidationError(
            "raw_ecb.fx_rates does not "
            "match the source-oriented extract. "
            f"missing={len(missing)}, "
            f"unexpected={len(unexpected)}, "
            f"value_mismatches={len(mismatched)}"
        )

    null_metadata = (
        null_metadata_count(
            cursor,
            schema="raw_ecb",
            table="fx_rates",
        )
    )

    if null_metadata != 0:
        raise M1ValidationError(
            "raw_ecb.fx_rates contains rows "
            "with missing ingestion metadata"
        )

    currencies = {
        currency
        for (
            _,
            currency,
        )
        in actual
    }

    if currencies != {
        "USD",
        "GBP",
        "PLN",
        "SEK",
    }:
        raise M1ValidationError(
            "Unexpected ECB currencies: "
            f"{sorted(currencies)}"
        )

    if any(
        currency == "EUR"
        for (
            _,
            currency,
        )
        in actual
    ):
        raise M1ValidationError(
            "EUR must not be created in RAW ECB"
        )

    batches = batch_ids(
        cursor,
        schema="raw_ecb",
        table="fx_rates",
    )

    if (
        len(batches) != 1
        or not next(
            iter(batches)
        ).startswith(
            "ECB-"
        )
    ):
        raise M1ValidationError(
            "Unexpected ECB batch IDs: "
            f"{sorted(batches)}"
        )

    print(
        "PASS raw_ecb.fx_rates: "
        f"{len(actual):,} rows"
    )


def validate_m1(
    *,
    run_dir: Path,
    ecb_file: Path,
) -> None:
    resolved_ecb_file = resolve_project_path(
        ecb_file
    )

    if not resolved_ecb_file.exists():
        raise M1ValidationError(
            "Missing ECB acceptance extract: "
            f"{resolved_ecb_file}. "
            "Run the M1 ECB fixture extraction before validation."
        )

    source_run = load_source_run(
        run_dir
    )

    with connect() as connection, connection.cursor() as cursor:
        validate_raw_relation_set(
            cursor
        )

        validate_synthetic_sources(
            cursor,
            source_run=source_run,
        )

        validate_ecb_source(
            cursor,
            ecb_file=resolved_ecb_file,
        )

    print()
    print(
        "M1 validation passed."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the clean M1 RAW "
            "pipeline acceptance contract."
        )
    )

    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help=(
            "Generated synthetic source run."
        ),
    )

    parser.add_argument(
        "--ecb-file",
        type=Path,
        required=True,
        help=(
            "Source-oriented ECB extract."
        ),
    )

    args = parser.parse_args()

    validate_m1(
        run_dir=args.run_dir,
        ecb_file=args.ecb_file,
    )


if __name__ == "__main__":
    main()