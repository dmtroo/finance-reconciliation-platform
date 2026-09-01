from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from psycopg import sql

from finance_reconciliation.ingestion.database import connect
from finance_reconciliation.paths import PROJECT_ROOT

EXPECTED_INTERMEDIATE_MODELS = {
    "int_financial_events__with_reference_fx",
    "int_captures__lifecycle",
    "int_invoices__payment_summary",
    "int_financial_events__settlement_mapping",
    "int_settlements__bank_context",
    "int_accounting__journal_entries",
    "int_accounting__source_reference_summary",
    "int_financial_events__accounting_context",
    "int_settlements__accounting_context",
}


class M3ValidationError(RuntimeError):
    """Raised when the M3 intermediate acceptance contract fails."""


def scalar(
    cursor,
    query,
    parameters: tuple[Any, ...] | None = None,
) -> int:
    if parameters is None:
        cursor.execute(query)
    else:
        cursor.execute(
            query,
            parameters,
        )

    row = cursor.fetchone()

    if row is None:
        raise M3ValidationError(
            "Validation query returned no row"
        )

    return int(row[0])


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

    return scalar(
        cursor,
        query,
    )


def validate_manifest(
    manifest_path: Path,
) -> None:
    if not manifest_path.exists():
        raise M3ValidationError(
            f"Missing dbt manifest: {manifest_path}. "
            "Run the intermediate dbt build before M3 validation."
        )

    manifest: dict[str, Any] = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    intermediate_nodes = {}

    for node in manifest["nodes"].values():
        if node.get("resource_type") != "model":
            continue

        name = str(
            node.get(
                "name",
                "",
            )
        )

        if not name.startswith(
            "int_"
        ):
            continue

        intermediate_nodes[
            name
        ] = node

    actual_models = set(
        intermediate_nodes
    )

    if (
        actual_models
        != EXPECTED_INTERMEDIATE_MODELS
    ):
        raise M3ValidationError(
            "Intermediate model contract mismatch. "
            f"Missing={sorted(EXPECTED_INTERMEDIATE_MODELS - actual_models)}; "
            f"unexpected={sorted(actual_models - EXPECTED_INTERMEDIATE_MODELS)}"
        )

    for name, node in (
        intermediate_nodes.items()
    ):
        original_path = str(
            node.get(
                "original_file_path",
                "",
            )
        )

        if not original_path.startswith(
            "models/intermediate/"
        ):
            raise M3ValidationError(
                f"{name} is outside models/intermediate: "
                f"{original_path}"
            )

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
            raise M3ValidationError(
                f"{name} must not depend directly "
                "on dbt sources. "
                f"Found={source_dependencies}"
            )

        if not model_dependencies:
            raise M3ValidationError(
                f"{name} must depend on at least "
                "one upstream dbt model via ref()."
            )

    print(
        "PASS dbt manifest contract: "
        "9 ref-only intermediate models"
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
        where table_schema = %s
        """,
        (
            analytics_schema,
        ),
    )

    actual = {
        str(row[0])
        for row in cursor.fetchall()
        if str(
            row[0]
        ).startswith(
            "int_"
        )
    }

    if (
        actual
        != EXPECTED_INTERMEDIATE_MODELS
    ):
        raise M3ValidationError(
            "Database intermediate relation "
            "contract mismatch. "
            f"Missing={sorted(EXPECTED_INTERMEDIATE_MODELS - actual)}; "
            f"unexpected={sorted(actual - EXPECTED_INTERMEDIATE_MODELS)}"
        )

    print(
        "PASS database relation contract: "
        "exactly 9 intermediate relations"
    )


def assert_equal_counts(
    *,
    label: str,
    left_count: int,
    right_count: int,
) -> None:
    if left_count != right_count:
        raise M3ValidationError(
            f"{label}: "
            f"left={left_count}, "
            f"right={right_count}"
        )

    print(
        f"PASS {label}: "
        f"{left_count:,} rows"
    )


def validate_primary_grains(
    cursor,
    *,
    analytics_schema: str,
) -> None:
    staging_events = relation_count(
        cursor,
        schema=analytics_schema,
        relation=(
            "stg_psp__financial_events"
        ),
    )

    fx_events = relation_count(
        cursor,
        schema=analytics_schema,
        relation=(
            "int_financial_events__with_reference_fx"
        ),
    )

    assert_equal_counts(
        label=(
            "financial events → "
            "reference FX grain"
        ),
        left_count=staging_events,
        right_count=fx_events,
    )

    source_captures = scalar(
        cursor,
        sql.SQL(
            """
            select count(*)
            from {}.{}
            where event_type = 'CAPTURE'
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "int_financial_events__with_reference_fx"
            ),
        ),
    )

    capture_lifecycle = relation_count(
        cursor,
        schema=analytics_schema,
        relation=(
            "int_captures__lifecycle"
        ),
    )

    assert_equal_counts(
        label=(
            "captures → lifecycle grain"
        ),
        left_count=source_captures,
        right_count=capture_lifecycle,
    )

    staging_invoices = relation_count(
        cursor,
        schema=analytics_schema,
        relation="stg_billing__invoices",
    )

    invoice_summary = relation_count(
        cursor,
        schema=analytics_schema,
        relation=(
            "int_invoices__payment_summary"
        ),
    )

    assert_equal_counts(
        label=(
            "invoices → payment summary grain"
        ),
        left_count=staging_invoices,
        right_count=invoice_summary,
    )

    settlement_mapping = relation_count(
        cursor,
        schema=analytics_schema,
        relation=(
            "int_financial_events__settlement_mapping"
        ),
    )

    assert_equal_counts(
        label=(
            "financial events → "
            "settlement mapping grain"
        ),
        left_count=staging_events,
        right_count=settlement_mapping,
    )

    staging_settlements = relation_count(
        cursor,
        schema=analytics_schema,
        relation=(
            "stg_psp__settlements"
        ),
    )

    bank_context = relation_count(
        cursor,
        schema=analytics_schema,
        relation=(
            "int_settlements__bank_context"
        ),
    )

    assert_equal_counts(
        label=(
            "settlements → bank context grain"
        ),
        left_count=staging_settlements,
        right_count=bank_context,
    )

    source_journal_entries = scalar(
        cursor,
        sql.SQL(
            """
            select count(
                distinct journal_entry_id
            )
            from {}.{}
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "stg_accounting__journal_lines"
            ),
        ),
    )

    journal_entries = relation_count(
        cursor,
        schema=analytics_schema,
        relation=(
            "int_accounting__journal_entries"
        ),
    )

    assert_equal_counts(
        label=(
            "journal lines → "
            "journal entry grain"
        ),
        left_count=source_journal_entries,
        right_count=journal_entries,
    )

    event_accounting = relation_count(
        cursor,
        schema=analytics_schema,
        relation=(
            "int_financial_events__accounting_context"
        ),
    )

    assert_equal_counts(
        label=(
            "financial events → "
            "accounting context grain"
        ),
        left_count=staging_events,
        right_count=event_accounting,
    )

    settlement_accounting = relation_count(
        cursor,
        schema=analytics_schema,
        relation=(
            "int_settlements__accounting_context"
        ),
    )

    assert_equal_counts(
        label=(
            "settlements → "
            "accounting context grain"
        ),
        left_count=staging_settlements,
        right_count=settlement_accounting,
    )


def validate_source_reference_summary_grain(
    cursor,
    *,
    analytics_schema: str,
) -> None:
    expected = scalar(
        cursor,
        sql.SQL(
            """
            select count(*)
            from (
                select distinct
                    source_reference_type,
                    source_reference
                from {}.{}
                where
                    source_reference_type
                        is not null
                    and source_reference
                        is not null
            ) source_references
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "int_accounting__journal_entries"
            ),
        ),
    )

    actual = relation_count(
        cursor,
        schema=analytics_schema,
        relation=(
            "int_accounting__source_reference_summary"
        ),
    )

    assert_equal_counts(
        label=(
            "accounting source-reference "
            "summary grain"
        ),
        left_count=expected,
        right_count=actual,
    )


def assert_clean_zero(
    cursor,
    *,
    label: str,
    query,
) -> None:
    count = scalar(
        cursor,
        query,
    )

    if count != 0:
        raise M3ValidationError(
            f"{label}: "
            f"found {count} unexpected rows "
            "in the clean scenario"
        )

    print(
        f"PASS clean scenario: {label}"
    )


def validate_clean_fx(
    cursor,
    *,
    analytics_schema: str,
) -> None:
    assert_clean_zero(
        cursor,
        label="all financial events have reference FX",
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where reference_fx_rate is null
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "int_financial_events__with_reference_fx"
            ),
        ),
    )

    assert_clean_zero(
        cursor,
        label="no financial event uses future FX",
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where
                reference_fx_rate_date
                > event_date
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "int_financial_events__with_reference_fx"
            ),
        ),
    )


def validate_clean_settlement_matching(
    cursor,
    *,
    analytics_schema: str,
) -> None:
    assert_clean_zero(
        cursor,
        label=(
            "every financial event has one "
            "settlement item and one settlement"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where
                settlement_item_count != 1
                or settlement_count != 1
                or settlement_id is null
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "int_financial_events__settlement_mapping"
            ),
        ),
    )

    assert_clean_zero(
        cursor,
        label=(
            "settlement headers equal "
            "aggregated settlement items"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where
                gross_header_minus_items_amount != 0
                or fee_header_minus_items_amount != 0
                or net_header_minus_items_amount != 0
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "int_settlements__bank_context"
            ),
        ),
    )

    assert_clean_zero(
        cursor,
        label=(
            "every PAID settlement has exactly "
            "one eligible bank receipt"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where
                settlement_status = 'PAID'
                and eligible_bank_receipt_count != 1
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "int_settlements__bank_context"
            ),
        ),
    )

    assert_clean_zero(
        cursor,
        label=(
            "bank receipts equal PSP "
            "net payout amounts"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where
                eligible_bank_receipt_count = 1
                and bank_minus_settlement_amount != 0
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "int_settlements__bank_context"
            ),
        ),
    )


def validate_clean_accounting(
    cursor,
    *,
    analytics_schema: str,
) -> None:
    assert_clean_zero(
        cursor,
        label="all journal entries are balanced",
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where journal_balance_difference_eur != 0
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "int_accounting__journal_entries"
            ),
        ),
    )

    assert_clean_zero(
        cursor,
        label=(
            "every financial event has exactly "
            "one posted accounting entry"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where posted_journal_entry_count != 1
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "int_financial_events__accounting_context"
            ),
        ),
    )

    assert_clean_zero(
        cursor,
        label=(
            "financial-event ledger amounts "
            "equal expected EUR amounts"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where
                ledger_debit_minus_expected_amount_eur != 0
                or ledger_credit_minus_expected_amount_eur != 0
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "int_financial_events__accounting_context"
            ),
        ),
    )

    assert_clean_zero(
        cursor,
        label=(
            "every settlement has exactly "
            "one posted accounting entry"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where posted_journal_entry_count != 1
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "int_settlements__accounting_context"
            ),
        ),
    )

    assert_clean_zero(
        cursor,
        label=(
            "settlement ledger legs equal "
            "expected PSP amounts"
        ),
        query=sql.SQL(
            """
            select count(*)
            from {}.{}
            where
                ledger_bank_minus_expected_amount_eur != 0
                or ledger_fee_minus_expected_amount_eur != 0
                or ledger_clearing_minus_expected_amount_eur != 0
            """
        ).format(
            sql.Identifier(
                analytics_schema
            ),
            sql.Identifier(
                "int_settlements__accounting_context"
            ),
        ),
    )


def validate_m3() -> None:
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

        validate_source_reference_summary_grain(
            cursor,
            analytics_schema=analytics_schema,
        )

        validate_clean_fx(
            cursor,
            analytics_schema=analytics_schema,
        )

        validate_clean_settlement_matching(
            cursor,
            analytics_schema=analytics_schema,
        )

        validate_clean_accounting(
            cursor,
            analytics_schema=analytics_schema,
        )

    print()
    print(
        "M3 validation passed."
    )


if __name__ == "__main__":
    validate_m3()