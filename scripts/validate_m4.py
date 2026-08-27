from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from psycopg import sql

from finance_reconciliation.ingestion.database import connect
from finance_reconciliation.paths import PROJECT_ROOT

EXPECTED_MART_MODELS = {
    "fct_payment_reconciliation",
    "fct_settlement_reconciliation",
    "mart_reconciliation_exceptions",
    "mart_finance_daily",
}

EXPECTED_AMOUNT_TOLERANCE = Decimal("0.01")
EXPECTED_SETTLEMENT_PENDING_DAYS = 5
EXPECTED_BANK_PENDING_DAYS = 2
EXPECTED_FX_OUTLIER_RATIO = Decimal("0.03")


class M4ValidationError(RuntimeError):
    """Raised when the M4 reconciliation acceptance contract fails."""


def fetch_scalar(
    cursor,
    query,
    parameters: tuple[Any, ...] | None = None,
) -> Any:
    if parameters is None:
        cursor.execute(query)
    else:
        cursor.execute(
            query,
            parameters,
        )

    row = cursor.fetchone()

    if row is None:
        raise M4ValidationError(
            "Validation query returned no row"
        )

    return row[0]


def integer_scalar(
    cursor,
    query,
    parameters: tuple[Any, ...] | None = None,
) -> int:
    return int(
        fetch_scalar(
            cursor,
            query,
            parameters,
        )
    )


def relation_count(
    cursor,
    *,
    schema: str,
    relation: str,
) -> int:
    query = sql.SQL(
        "select count(*) from {}.{}"
    ).format(
        sql.Identifier(schema),
        sql.Identifier(relation),
    )

    return integer_scalar(
        cursor,
        query,
    )


def assert_equal_counts(
    *,
    label: str,
    left_count: int,
    right_count: int,
) -> None:
    if left_count != right_count:
        raise M4ValidationError(
            f"{label}: "
            f"left={left_count:,}, "
            f"right={right_count:,}"
        )

    print(
        f"PASS {label}: "
        f"{left_count:,} rows"
    )


def assert_zero(
    cursor,
    *,
    label: str,
    query,
) -> None:
    count = integer_scalar(
        cursor,
        query,
    )

    if count != 0:
        raise M4ValidationError(
            f"{label}: "
            f"found {count:,} unexpected rows"
        )

    print(
        f"PASS {label}"
    )


def validate_policy_contract() -> None:
    project_path = (
        PROJECT_ROOT
        / "dbt"
        / "dbt_project.yml"
    )

    project = yaml.safe_load(
        project_path.read_text(
            encoding="utf-8"
        )
    )

    variables = project.get(
        "vars",
        {},
    )

    required = {
        "reconciliation_amount_tolerance_eur",
        "reconciliation_settlement_pending_days",
        "reconciliation_bank_pending_days",
        "reconciliation_fx_outlier_ratio",
        "reconciliation_as_of_date",
    }

    missing = required - set(
        variables
    )

    if missing:
        raise M4ValidationError(
            "Missing reconciliation dbt vars: "
            f"{sorted(missing)}"
        )

    amount_tolerance = Decimal(
        str(
            variables[
                "reconciliation_amount_tolerance_eur"
            ]
        )
    )

    settlement_pending_days = int(
        variables[
            "reconciliation_settlement_pending_days"
        ]
    )

    bank_pending_days = int(
        variables[
            "reconciliation_bank_pending_days"
        ]
    )

    fx_outlier_ratio = Decimal(
        str(
            variables[
                "reconciliation_fx_outlier_ratio"
            ]
        )
    )

    if (
        amount_tolerance
        != EXPECTED_AMOUNT_TOLERANCE
    ):
        raise M4ValidationError(
            "Unexpected reconciliation amount tolerance: "
            f"{amount_tolerance}"
        )

    if (
        settlement_pending_days
        != EXPECTED_SETTLEMENT_PENDING_DAYS
    ):
        raise M4ValidationError(
            "Unexpected settlement pending window: "
            f"{settlement_pending_days}"
        )

    if (
        bank_pending_days
        != EXPECTED_BANK_PENDING_DAYS
    ):
        raise M4ValidationError(
            "Unexpected bank pending window: "
            f"{bank_pending_days}"
        )

    if (
        fx_outlier_ratio
        != EXPECTED_FX_OUTLIER_RATIO
    ):
        raise M4ValidationError(
            "Unexpected FX outlier ratio: "
            f"{fx_outlier_ratio}"
        )

    as_of_raw = str(
        variables[
            "reconciliation_as_of_date"
        ]
    )

    try:
        as_of_date = date.fromisoformat(
            as_of_raw
        )
    except ValueError as exc:
        raise M4ValidationError(
            "reconciliation_as_of_date must "
            f"use YYYY-MM-DD format; got {as_of_raw!r}"
        ) from exc

    print(
        "PASS reconciliation policy contract: "
        f"tolerance=€{amount_tolerance}, "
        f"settlement_pending={settlement_pending_days}d, "
        f"bank_pending={bank_pending_days}d, "
        f"fx_outlier={fx_outlier_ratio}, "
        f"as_of_date={as_of_date}"
    )


def validate_manifest(
    manifest_path: Path,
) -> None:
    if not manifest_path.exists():
        raise M4ValidationError(
            f"Missing dbt manifest: {manifest_path}. "
            "Build the marts before running M4 validation."
        )

    manifest: dict[str, Any] = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    mart_nodes: dict[str, dict[str, Any]] = {}

    for node in manifest["nodes"].values():
        if node.get(
            "resource_type"
        ) != "model":
            continue

        original_path = str(
            node.get(
                "original_file_path",
                "",
            )
        )

        if not original_path.startswith(
            "models/marts/"
        ):
            continue

        name = str(
            node.get(
                "name",
                "",
            )
        )

        mart_nodes[name] = node

    actual_models = set(
        mart_nodes
    )

    if (
        actual_models
        != EXPECTED_MART_MODELS
    ):
        raise M4ValidationError(
            "M4 mart model contract mismatch. "
            f"Missing={sorted(EXPECTED_MART_MODELS - actual_models)}; "
            f"unexpected={sorted(actual_models - EXPECTED_MART_MODELS)}"
        )

    for name, node in mart_nodes.items():
        dependencies = (
            node.get(
                "depends_on",
                {},
            ).get(
                "nodes",
                [],
            )
        )

        source_dependencies = [
            dependency
            for dependency in dependencies
            if dependency.startswith(
                "source."
            )
        ]

        model_dependencies = [
            dependency
            for dependency in dependencies
            if dependency.startswith(
                "model."
            )
        ]

        if source_dependencies:
            raise M4ValidationError(
                f"{name} must not depend directly "
                "on RAW dbt sources. "
                f"Found={source_dependencies}"
            )

        if not model_dependencies:
            raise M4ValidationError(
                f"{name} must depend on at least "
                "one upstream dbt model via ref()."
            )

    print(
        "PASS dbt manifest contract: "
        "exactly 4 ref-only reconciliation marts"
    )


def validate_relation_set(
    cursor,
    *,
    analytics_schema: str,
) -> None:
    cursor.execute(
        """
        select table_name
        from information_schema.tables
        where
            table_schema = %s
            and (
                table_name like %s
                or table_name like %s
            )
        """,
        (
            analytics_schema,
            "fct_%",
            "mart_%",
        ),
    )

    actual = {
        str(row[0])
        for row in cursor.fetchall()
    }

    if (
        actual
        != EXPECTED_MART_MODELS
    ):
        raise M4ValidationError(
            "Database M4 relation contract mismatch. "
            f"Missing={sorted(EXPECTED_MART_MODELS - actual)}; "
            f"unexpected={sorted(actual - EXPECTED_MART_MODELS)}"
        )

    print(
        "PASS database relation contract: "
        "exactly 4 reconciliation marts"
    )


def validate_primary_grains(
    cursor,
    *,
    analytics_schema: str,
) -> None:
    captures = relation_count(
        cursor,
        schema=analytics_schema,
        relation="int_captures__lifecycle",
    )

    payment_fact = relation_count(
        cursor,
        schema=analytics_schema,
        relation="fct_payment_reconciliation",
    )

    assert_equal_counts(
        label=(
            "captures → payment reconciliation grain"
        ),
        left_count=captures,
        right_count=payment_fact,
    )

    settlements = relation_count(
        cursor,
        schema=analytics_schema,
        relation="int_settlements__bank_context",
    )

    settlement_fact = relation_count(
        cursor,
        schema=analytics_schema,
        relation="fct_settlement_reconciliation",
    )

    assert_equal_counts(
        label=(
            "settlements → settlement reconciliation grain"
        ),
        left_count=settlements,
        right_count=settlement_fact,
    )

    assert_zero(
        cursor,
        label=(
            "exception mart has unique exception_id grain"
        ),
        query=sql.SQL(
            """
            select count(*)
            from (
                select
                    exception_id
                from {}.{}
                group by exception_id
                having count(*) > 1
            ) as duplicate_exceptions
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "mart_reconciliation_exceptions"
            ),
        ),
    )

    assert_zero(
        cursor,
        label=(
            "daily mart has unique "
            "business_date × product × currency grain"
        ),
        query=sql.SQL(
            """
            select count(*)
            from (
                select
                    business_date,
                    product_id,
                    currency
                from {}.{}
                group by
                    business_date,
                    product_id,
                    currency
                having count(*) > 1
            ) as duplicate_daily_grains
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "mart_finance_daily"
            ),
        ),
    )


def validate_clean_payment_fact(
    cursor,
    *,
    analytics_schema: str,
) -> None:
    assert_zero(
        cursor,
        label=(
            "clean payment reconciliation controls all pass"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where
                capture_amount_matches_invoice
                    is distinct from true

                or invoice_capture_count != 1

                or is_product_mapped
                    is distinct from true

                or reference_fx_rate is null

                or is_fx_rate_outlier
                    is distinct from false

                or settlement_count != 1

                or posted_journal_entry_count != 1

                or is_ledger_amount_within_tolerance
                    is distinct from true

                or is_journal_balanced_within_tolerance
                    is distinct from true
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "fct_payment_reconciliation"
            ),
        ),
    )


def validate_clean_settlement_fact(
    cursor,
    *,
    analytics_schema: str,
) -> None:
    assert_zero(
        cursor,
        label=(
            "clean settlement reconciliation controls all pass"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where
                is_settlement_total_within_tolerance
                    is distinct from true

                or (
                    settlement_status = 'PAID'
                    and eligible_bank_receipt_count != 1
                )

                or (
                    settlement_status = 'PAID'
                    and is_bank_amount_within_tolerance
                        is distinct from true
                )

                or posted_journal_entry_count != 1

                or is_ledger_amount_within_tolerance
                    is distinct from true

                or is_journal_balanced_within_tolerance
                    is distinct from true
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "fct_settlement_reconciliation"
            ),
        ),
    )


def validate_clean_exception_mart(
    cursor,
    *,
    analytics_schema: str,
) -> None:
    exception_count = relation_count(
        cursor,
        schema=analytics_schema,
        relation="mart_reconciliation_exceptions",
    )

    if exception_count != 0:
        raise M4ValidationError(
            "Clean scenario produced reconciliation "
            f"exceptions: {exception_count:,}"
        )

    print(
        "PASS clean exception mart: "
        "0 reconciliation exceptions"
    )


def validate_daily_volume_conservation(
    cursor,
    *,
    analytics_schema: str,
) -> None:
    invoice_count = relation_count(
        cursor,
        schema=analytics_schema,
        relation="int_invoices__payment_summary",
    )

    daily_invoice_count = integer_scalar(
        cursor,
        sql.SQL(
            """
            select coalesce(
                sum(invoice_count),
                0
            )
            from {}.{}
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "mart_finance_daily"
            ),
        ),
    )

    assert_equal_counts(
        label=(
            "invoice counts preserved in daily mart"
        ),
        left_count=invoice_count,
        right_count=daily_invoice_count,
    )

    capture_count = relation_count(
        cursor,
        schema=analytics_schema,
        relation="fct_payment_reconciliation",
    )

    daily_capture_count = integer_scalar(
        cursor,
        sql.SQL(
            """
            select coalesce(
                sum(capture_count),
                0
            )
            from {}.{}
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "mart_finance_daily"
            ),
        ),
    )

    assert_equal_counts(
        label=(
            "capture counts preserved in daily mart"
        ),
        left_count=capture_count,
        right_count=daily_capture_count,
    )

    exception_count = relation_count(
        cursor,
        schema=analytics_schema,
        relation="mart_reconciliation_exceptions",
    )

    daily_exception_count = integer_scalar(
        cursor,
        sql.SQL(
            """
            select coalesce(
                sum(exception_count),
                0
            )
            from {}.{}
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "mart_finance_daily"
            ),
        ),
    )

    assert_equal_counts(
        label=(
            "exception counts preserved in daily mart"
        ),
        left_count=exception_count,
        right_count=daily_exception_count,
    )


def validate_daily_amount_conservation(
    cursor,
    *,
    analytics_schema: str,
) -> None:
    assert_zero(
        cursor,
        label=(
            "EUR-valued capture amount preserved "
            "from payment fact to daily mart"
        ),
        query=sql.SQL(
            """
            select count(*)
            from (
                select
                    (
                        select coalesce(
                            sum(capture_amount_eur),
                            0
                        )
                        from {}.{}
                        where capture_amount_eur is not null
                    ) as payment_fact_amount,

                    (
                        select coalesce(
                            sum(valued_capture_amount_eur),
                            0
                        )
                        from {}.{}
                    ) as daily_amount
            ) as totals
            where abs(
                payment_fact_amount
                - daily_amount
            ) > 0.01
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "fct_payment_reconciliation"
            ),
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "mart_finance_daily"
            ),
        ),
    )

    assert_zero(
        cursor,
        label=(
            "clean reconciled EUR amount equals "
            "all valued capture amount"
        ),
        query=sql.SQL(
            """
            select count(*)
            from (
                select
                    coalesce(
                        sum(valued_capture_amount_eur),
                        0
                    ) as valued_amount,

                    coalesce(
                        sum(reconciled_capture_amount_eur),
                        0
                    ) as reconciled_amount
                from {}.{}
            ) as totals
            where abs(
                valued_amount
                - reconciled_amount
            ) > 0.01
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "mart_finance_daily"
            ),
        ),
    )


def validate_clean_daily_kpis(
    cursor,
    *,
    analytics_schema: str,
) -> None:
    assert_zero(
        cursor,
        label=(
            "clean daily mart has no unvalued captures"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where unvalued_capture_count != 0
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "mart_finance_daily"
            ),
        ),
    )

    assert_zero(
        cursor,
        label=(
            "clean daily mart has no active "
            "or excluded capture breaks"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where
                pending_capture_count != 0
                or open_break_capture_count != 0
                or excluded_capture_count != 0
                or reconciled_capture_count != capture_count
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "mart_finance_daily"
            ),
        ),
    )

    assert_zero(
        cursor,
        label=(
            "clean daily mart reports zero exceptions"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where
                exception_count != 0
                or pending_exception_count != 0
                or open_break_exception_count != 0
                or critical_exception_count != 0
                or warning_exception_count != 0
                or info_exception_count != 0
                or gross_exception_amount_eur != 0
                or open_break_exception_amount_eur != 0
                or pending_exception_amount_eur != 0
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "mart_finance_daily"
            ),
        ),
    )

    assert_zero(
        cursor,
        label=(
            "clean amount reconciliation rate is 100% "
            "for every valued daily grain"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where
                (
                    valued_capture_amount_eur > 0
                    and abs(
                        amount_reconciliation_rate
                        - 1
                    ) > 0.000001
                )

                or

                (
                    valued_capture_amount_eur = 0
                    and amount_reconciliation_rate
                        is not null
                )
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "mart_finance_daily"
            ),
        ),
    )


def validate_m4() -> None:
    load_dotenv(
        PROJECT_ROOT / ".env"
    )

    analytics_schema = os.getenv(
        "DBT_SCHEMA",
        "analytics_dev",
    )

    manifest_path = (
        PROJECT_ROOT
        / "dbt"
        / "target"
        / "manifest.json"
    )

    validate_policy_contract()

    validate_manifest(
        manifest_path
    )

    with connect() as connection, connection.cursor() as cursor:
        validate_relation_set(
            cursor,
            analytics_schema=analytics_schema,
        )

        validate_primary_grains(
            cursor,
            analytics_schema=analytics_schema,
        )

        validate_clean_payment_fact(
            cursor,
            analytics_schema=analytics_schema,
        )

        validate_clean_settlement_fact(
            cursor,
            analytics_schema=analytics_schema,
        )

        validate_clean_exception_mart(
            cursor,
            analytics_schema=analytics_schema,
        )

        validate_daily_volume_conservation(
            cursor,
            analytics_schema=analytics_schema,
        )

        validate_daily_amount_conservation(
            cursor,
            analytics_schema=analytics_schema,
        )

        validate_clean_daily_kpis(
            cursor,
            analytics_schema=analytics_schema,
        )

    print()
    print(
        "M4 validation passed."
    )


if __name__ == "__main__":
    validate_m4()