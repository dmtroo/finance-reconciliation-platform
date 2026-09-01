from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from psycopg import sql

from finance_reconciliation.ingestion.database import (
    connect,
)
from finance_reconciliation.ingestion.source_run import (
    SourceRun,
    load_source_run,
)
from finance_reconciliation.paths import (
    resolve_project_path,
)

EXPECTED_ANOMALY_CODES = [
    "MISSING_CAPTURE",
    "CAPTURE_AMOUNT_MISMATCH",
    "DUPLICATE_CAPTURE",
    "INVALID_REFUND",
    "OVER_REFUND",
    "MISSING_SETTLEMENT",
    "LATE_SETTLEMENT",
    "SETTLEMENT_TOTAL_MISMATCH",
    "MISSING_BANK_RECEIPT",
    "BANK_AMOUNT_MISMATCH",
    "MISSING_LEDGER_POSTING",
    "LEDGER_AMOUNT_MISMATCH",
    "UNBALANCED_JOURNAL",
    "MISSING_FX_RATE",
    "FX_RATE_OUTLIER",
    "UNMAPPED_PRODUCT",
]


FIXED_EXCEPTION_POLICY: dict[
    str,
    tuple[str, str],
] = {
    "MISSING_CAPTURE": (
        "OPEN_BREAK",
        "CRITICAL",
    ),
    "CAPTURE_AMOUNT_MISMATCH": (
        "OPEN_BREAK",
        "CRITICAL",
    ),
    "DUPLICATE_CAPTURE": (
        "OPEN_BREAK",
        "CRITICAL",
    ),
    "INVALID_REFUND": (
        "OPEN_BREAK",
        "CRITICAL",
    ),
    "OVER_REFUND": (
        "OPEN_BREAK",
        "CRITICAL",
    ),
    "LATE_SETTLEMENT": (
        "RESOLVED",
        "WARNING",
    ),
    "SETTLEMENT_TOTAL_MISMATCH": (
        "OPEN_BREAK",
        "CRITICAL",
    ),
    "BANK_AMOUNT_MISMATCH": (
        "OPEN_BREAK",
        "CRITICAL",
    ),
    "MISSING_LEDGER_POSTING": (
        "OPEN_BREAK",
        "CRITICAL",
    ),
    "LEDGER_AMOUNT_MISMATCH": (
        "OPEN_BREAK",
        "CRITICAL",
    ),
    "UNBALANCED_JOURNAL": (
        "OPEN_BREAK",
        "CRITICAL",
    ),
    "MISSING_FX_RATE": (
        "OPEN_BREAK",
        "CRITICAL",
    ),
    "FX_RATE_OUTLIER": (
        "OPEN_BREAK",
        "WARNING",
    ),
    "UNMAPPED_PRODUCT": (
        "OPEN_BREAK",
        "WARNING",
    ),
}


AGING_EXCEPTION_POLICY = {
    "MISSING_SETTLEMENT": 5,
    "MISSING_BANK_RECEIPT": 2,
}


@dataclass(frozen=True)
class Relation:
    schema: str
    name: str


@dataclass(frozen=True)
class ExceptionRow:
    exception_code: str
    exception_status: str
    severity: str
    age_days: int | None
    exception_amount_eur: (
        Decimal | None
    )


class M5AnomalyValidationError(
    RuntimeError
):
    """Raised when M5 anomaly acceptance fails."""


def load_dbt_manifest(
    path: Path,
) -> dict[str, Any]:
    if not path.exists():
        raise M5AnomalyValidationError(
            "dbt manifest does not exist: "
            f"{path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        return json.load(
            handle
        )


def model_relation(
    manifest: dict[str, Any],
    *,
    model_name: str,
) -> Relation:
    matches = []

    for node in (
        manifest.get(
            "nodes",
            {},
        ).values()
    ):
        if (
            node.get(
                "resource_type"
            )
            != "model"
        ):
            continue

        if (
            node.get("name")
            != model_name
        ):
            continue

        matches.append(
            node
        )

    if len(matches) != 1:
        raise M5AnomalyValidationError(
            "Expected exactly one dbt "
            f"model named {model_name}, "
            f"found {len(matches)}"
        )

    node = matches[0]

    schema = node.get(
        "schema"
    )

    relation_name = (
        node.get("alias")
        or node.get("name")
    )

    if (
        not schema
        or not relation_name
    ):
        raise M5AnomalyValidationError(
            "dbt model relation metadata "
            f"is incomplete for {model_name}"
        )

    return Relation(
        schema=str(schema),
        name=str(relation_name),
    )


def validate_injection_manifest(
    source_run: SourceRun,
) -> None:
    scenario = (
        source_run.manifest.get(
            "scenario"
        )
    )

    if (
        scenario
        != "with_anomalies"
    ):
        raise M5AnomalyValidationError(
            "Expected source run scenario "
            "'with_anomalies', "
            f"found {scenario!r}"
        )

    anomaly_records = (
        source_run.manifest.get(
            "anomalies"
        )
    )

    if not isinstance(
        anomaly_records,
        list,
    ):
        raise M5AnomalyValidationError(
            "Source run manifest does not "
            "contain an anomalies list"
        )

    actual_codes = []

    for record in anomaly_records:
        if not isinstance(
            record,
            dict,
        ):
            raise M5AnomalyValidationError(
                "Anomaly manifest record "
                "must be an object"
            )

        code = record.get(
            "anomaly_code"
        )

        if not isinstance(
            code,
            str,
        ):
            raise M5AnomalyValidationError(
                "Anomaly manifest record "
                "has invalid anomaly_code"
            )

        actual_codes.append(
            code
        )

    actual_counter = Counter(
        actual_codes
    )

    expected_counter = Counter(
        EXPECTED_ANOMALY_CODES
    )

    if (
        actual_counter
        != expected_counter
    ):
        missing = sorted(
            (
                expected_counter
                - actual_counter
            ).elements()
        )

        unexpected = sorted(
            (
                actual_counter
                - expected_counter
            ).elements()
        )

        raise M5AnomalyValidationError(
            "Injected anomaly manifest "
            "does not match the frozen "
            "M5 contract. "
            f"Missing={missing}, "
            f"unexpected={unexpected}"
        )

    print(
        "Injection manifest: "
        "16 frozen anomalies found."
    )


def fetch_exception_rows(
    cursor,
    *,
    relation: Relation,
) -> list[ExceptionRow]:
    query = sql.SQL(
        """
        select
            exception_code,
            exception_status,
            severity,
            age_days,
            exception_amount_eur
        from {}.{}
        order by
            exception_code,
            entity_type,
            entity_id,
            exception_id
        """
    ).format(
        sql.Identifier(
            relation.schema
        ),
        sql.Identifier(
            relation.name
        ),
    )

    cursor.execute(
        query
    )

    rows = cursor.fetchall()

    return [
        ExceptionRow(
            exception_code=str(
                row[0]
            ),
            exception_status=str(
                row[1]
            ),
            severity=str(
                row[2]
            ),
            age_days=(
                int(row[3])
                if row[3]
                is not None
                else None
            ),
            exception_amount_eur=(
                Decimal(row[4])
                if row[4]
                is not None
                else None
            ),
        )
        for row in rows
    ]


def validate_exception_code_coverage(
    rows: list[ExceptionRow],
) -> None:
    if not rows:
        raise M5AnomalyValidationError(
            "Exception mart is empty for "
            "with_anomalies scenario"
        )

    actual_codes = {
        row.exception_code
        for row in rows
    }

    expected_codes = set(
        EXPECTED_ANOMALY_CODES
    )

    if (
        actual_codes
        != expected_codes
    ):
        missing = sorted(
            expected_codes
            - actual_codes
        )

        unexpected = sorted(
            actual_codes
            - expected_codes
        )

        raise M5AnomalyValidationError(
            "Exception code coverage "
            "does not match the frozen "
            "taxonomy. "
            f"Missing={missing}, "
            f"unexpected={unexpected}"
        )

    print(
        "Exception taxonomy: "
        "all 16 frozen codes detected."
    )


def expected_aging_policy(
    row: ExceptionRow,
) -> tuple[str, str]:
    threshold = (
        AGING_EXCEPTION_POLICY[
            row.exception_code
        ]
    )

    if row.age_days is None:
        raise M5AnomalyValidationError(
            f"{row.exception_code} "
            "has NULL age_days"
        )

    if row.age_days < 0:
        raise M5AnomalyValidationError(
            f"{row.exception_code} "
            "has negative age_days: "
            f"{row.age_days}"
        )

    if (
        row.age_days
        <= threshold
    ):
        return (
            "PENDING",
            "INFO",
        )

    return (
        "OPEN_BREAK",
        "CRITICAL",
    )


def validate_exception_policy(
    rows: list[ExceptionRow],
) -> None:
    failures = []

    for row in rows:
        if (
            row.exception_code
            in AGING_EXCEPTION_POLICY
        ):
            expected_status, (
                expected_severity
            ) = expected_aging_policy(
                row
            )
        else:
            try:
                (
                    expected_status,
                    expected_severity,
                ) = (
                    FIXED_EXCEPTION_POLICY[
                        row.exception_code
                    ]
                )
            except KeyError as exc:
                raise (
                    M5AnomalyValidationError(
                        "No policy contract for "
                        f"{row.exception_code}"
                    )
                ) from exc

        if (
            row.exception_status
            != expected_status
            or row.severity
            != expected_severity
        ):
            failures.append(
                (
                    row.exception_code,
                    row.exception_status,
                    row.severity,
                    expected_status,
                    expected_severity,
                    row.age_days,
                )
            )

    if failures:
        raise M5AnomalyValidationError(
            "Exception policy mismatch. "
            f"Failures={failures[:10]}"
        )

    print(
        "Exception policy: "
        "status and severity passed."
    )


def validate_exception_amounts(
    rows: list[ExceptionRow],
) -> None:
    negative_rows = [
        row
        for row in rows
        if (
            row.exception_amount_eur
            is not None
            and row.exception_amount_eur
            < Decimal(0)
        )
    ]

    if negative_rows:
        raise M5AnomalyValidationError(
            "exception_amount_eur must be "
            "a non-negative magnitude"
        )

    print(
        "Exception amounts: "
        "non-negative magnitude contract "
        "passed."
    )


def print_exception_summary(
    cursor,
    *,
    relation: Relation,
) -> None:
    query = sql.SQL(
        """
        select
            exception_code,
            exception_status,
            severity,
            count(*) as exception_count,
            coalesce(
                sum(exception_amount_eur),
                0
            ) as exception_amount_eur
        from {}.{}
        group by
            exception_code,
            exception_status,
            severity
        order by
            exception_code,
            exception_status,
            severity
        """
    ).format(
        sql.Identifier(
            relation.schema
        ),
        sql.Identifier(
            relation.name
        ),
    )

    cursor.execute(
        query
    )

    rows = cursor.fetchall()

    print(
        "Exception summary:"
    )

    for row in rows:
        print(
            "  "
            f"{row[0]} | "
            f"{row[1]} | "
            f"{row[2]} | "
            f"count={row[3]} | "
            f"amount_eur={row[4]}"
        )


def exception_count(
    cursor,
    *,
    relation: Relation,
) -> int:
    query = sql.SQL(
        """
        select count(*)
        from {}.{}
        """
    ).format(
        sql.Identifier(
            relation.schema
        ),
        sql.Identifier(
            relation.name
        ),
    )

    cursor.execute(
        query
    )

    row = cursor.fetchone()

    if row is None:
        raise M5AnomalyValidationError(
            "Could not read exception count"
        )

    return int(
        row[0]
    )


def validate_daily_finance_mart(
    cursor,
    *,
    daily_relation: Relation,
    exception_relation: Relation,
) -> None:
    query = sql.SQL(
        """
        select
            count(*) as daily_rows,
            coalesce(
                sum(exception_count),
                0
            ) as exception_count,
            coalesce(
                sum(unvalued_capture_count),
                0
            ) as unvalued_capture_count,
            coalesce(
                sum(valued_capture_amount_eur),
                0
            ) as valued_capture_amount_eur,
            coalesce(
                sum(reconciled_capture_amount_eur),
                0
            ) as reconciled_capture_amount_eur,
            count(*) filter (
                where
                    amount_reconciliation_rate
                    is not null
                    and
                    amount_reconciliation_rate
                    < 1
            ) as rows_below_full_reconciliation
        from {}.{}
        """
    ).format(
        sql.Identifier(
            daily_relation.schema
        ),
        sql.Identifier(
            daily_relation.name
        ),
    )

    cursor.execute(
        query
    )

    row = cursor.fetchone()

    if row is None:
        raise M5AnomalyValidationError(
            "Could not read "
            "mart_finance_daily"
        )

    (
        daily_rows,
        daily_exception_count,
        unvalued_capture_count,
        valued_capture_amount_eur,
        reconciled_capture_amount_eur,
        rows_below_full_reconciliation,
    ) = row

    mart_exception_count = (
        exception_count(
            cursor,
            relation=exception_relation,
        )
    )

    if int(daily_rows) == 0:
        raise M5AnomalyValidationError(
            "mart_finance_daily is empty"
        )

    if (
        int(daily_exception_count)
        != mart_exception_count
    ):
        raise M5AnomalyValidationError(
            "Daily exception count does "
            "not conserve exception mart "
            "volume. "
            f"Daily={daily_exception_count}, "
            f"exceptions="
            f"{mart_exception_count}"
        )

    if (
        int(unvalued_capture_count)
        < 1
    ):
        raise M5AnomalyValidationError(
            "Expected at least one "
            "unvalued capture from "
            "MISSING_FX_RATE"
        )

    valued_amount = Decimal(
        valued_capture_amount_eur
    )

    reconciled_amount = Decimal(
        reconciled_capture_amount_eur
    )

    if (
        valued_amount
        <= Decimal(0)
    ):
        raise M5AnomalyValidationError(
            "Expected positive valued "
            "capture amount"
        )

    if (
        reconciled_amount
        >= valued_amount
    ):
        raise M5AnomalyValidationError(
            "Anomaly scenario did not "
            "reduce reconciled capture "
            "amount below valued capture "
            "amount"
        )

    if (
        int(
            rows_below_full_reconciliation
        )
        < 1
    ):
        raise M5AnomalyValidationError(
            "Expected at least one daily "
            "row with reconciliation rate "
            "below 100%"
        )

    print(
        "Daily finance mart: "
        "anomaly impact passed."
    )

    print(
        "  exception_count="
        f"{mart_exception_count}"
    )

    print(
        "  unvalued_capture_count="
        f"{unvalued_capture_count}"
    )

    print(
        "  valued_capture_amount_eur="
        f"{valued_amount}"
    )

    print(
        "  reconciled_capture_amount_eur="
        f"{reconciled_amount}"
    )


def validate_m5_anomalies(
    *,
    run_dir: Path,
    dbt_manifest_path: Path,
) -> None:
    resolved_run_dir = (
        resolve_project_path(
            run_dir
        )
    )

    resolved_manifest_path = (
        resolve_project_path(
            dbt_manifest_path
        )
    )

    source_run = load_source_run(
        resolved_run_dir
    )

    validate_injection_manifest(
        source_run
    )

    dbt_manifest = (
        load_dbt_manifest(
            resolved_manifest_path
        )
    )

    exception_relation = (
        model_relation(
            dbt_manifest,
            model_name=(
                "mart_reconciliation_exceptions"
            ),
        )
    )

    daily_relation = (
        model_relation(
            dbt_manifest,
            model_name=(
                "mart_finance_daily"
            ),
        )
    )

    with (
        connect() as connection,
        connection.cursor() as cursor,
    ):
        rows = fetch_exception_rows(
            cursor,
            relation=exception_relation,
        )

        print_exception_summary(
            cursor,
            relation=exception_relation,
        )

        validate_exception_code_coverage(
            rows
        )

        validate_exception_policy(
            rows
        )

        validate_exception_amounts(
            rows
        )

        validate_daily_finance_mart(
            cursor,
            daily_relation=daily_relation,
            exception_relation=(
                exception_relation
            ),
        )

    print(
        "M5 anomaly validation passed."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate M5 reconciliation "
            "outputs for a deterministic "
            "with_anomalies source run."
        )
    )

    parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help=(
            "Generated with_anomalies "
            "source run directory."
        ),
    )

    parser.add_argument(
        "--dbt-manifest",
        type=Path,
        default=Path(
            "dbt/target/manifest.json"
        ),
        help=(
            "Path to dbt manifest.json."
        ),
    )

    args = parser.parse_args()

    validate_m5_anomalies(
        run_dir=args.run_dir,
        dbt_manifest_path=(
            args.dbt_manifest
        ),
    )


if __name__ == "__main__":
    main()