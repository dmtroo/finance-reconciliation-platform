from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from psycopg import sql

from finance_reconciliation.ingestion.database import connect
from finance_reconciliation.paths import PROJECT_ROOT

EXPECTED_STAGING_MODELS = {
    "stg_billing__products",
    "stg_billing__subscriptions",
    "stg_billing__invoices",
    "stg_psp__payment_attempts",
    "stg_psp__financial_events",
    "stg_psp__settlements",
    "stg_psp__settlement_items",
    "stg_bank__statement_transactions",
    "stg_accounting__journal_lines",
    "stg_ecb__fx_rates",
}


ONE_TO_ONE_GRAINS = {
    "stg_billing__products": (
        "raw_billing",
        "products",
    ),
    "stg_billing__subscriptions": (
        "raw_billing",
        "subscriptions",
    ),
    "stg_billing__invoices": (
        "raw_billing",
        "invoices",
    ),
    "stg_psp__payment_attempts": (
        "raw_psp",
        "payment_attempts",
    ),
    "stg_psp__financial_events": (
        "raw_psp",
        "financial_events",
    ),
    "stg_psp__settlements": (
        "raw_psp",
        "settlements",
    ),
    "stg_psp__settlement_items": (
        "raw_psp",
        "settlement_items",
    ),
    "stg_bank__statement_transactions": (
        "raw_bank",
        "statement_transactions",
    ),
    "stg_accounting__journal_lines": (
        "raw_accounting",
        "journal_lines",
    ),
}


NUMERIC_COLUMNS = {
    ("stg_billing__products", "list_price_amount"): (18, 2),
    ("stg_billing__invoices", "subtotal_amount"): (18, 2),
    ("stg_billing__invoices", "tax_amount"): (18, 2),
    ("stg_billing__invoices", "total_amount"): (18, 2),

    ("stg_psp__payment_attempts", "attempt_amount"): (18, 2),

    ("stg_psp__financial_events", "event_amount"): (18, 2),
    ("stg_psp__financial_events", "signed_event_amount"): (18, 2),

    ("stg_psp__settlements", "gross_amount"): (18, 2),
    ("stg_psp__settlements", "fee_amount"): (18, 2),
    ("stg_psp__settlements", "net_payout_amount"): (18, 2),

    ("stg_psp__settlement_items", "transaction_amount"): (18, 2),
    ("stg_psp__settlement_items", "settlement_gross_eur_amount"): (18, 2),
    ("stg_psp__settlement_items", "fee_eur_amount"): (18, 2),
    ("stg_psp__settlement_items", "settlement_net_eur_amount"): (18, 2),
    ("stg_psp__settlement_items", "psp_fx_rate"): (18, 8),

    ("stg_bank__statement_transactions", "bank_amount"): (18, 2),

    ("stg_accounting__journal_lines", "debit_eur_amount"): (18, 2),
    ("stg_accounting__journal_lines", "credit_eur_amount"): (18, 2),

    ("stg_ecb__fx_rates", "units_per_eur"): (18, 8),
    ("stg_ecb__fx_rates", "eur_per_unit"): (18, 8),
}


class M2ValidationError(RuntimeError):
    """Raised when the M2 staging acceptance contract fails."""


def row_count(
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

    cursor.execute(query)

    row = cursor.fetchone()

    if row is None:
        raise M2ValidationError(
            f"Could not count {schema}.{relation}"
        )

    return int(row[0])


def validate_manifest(
    manifest_path: Path,
) -> None:
    if not manifest_path.exists():
        raise M2ValidationError(
            f"Missing dbt manifest: {manifest_path}. "
            "Run dbt build before M2 validation."
        )

    manifest: dict[str, Any] = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    staging_nodes = {}

    for node in manifest["nodes"].values():
        if node.get("resource_type") != "model":
            continue

        name = node.get("name", "")

        if not name.startswith("stg_"):
            continue

        staging_nodes[name] = node

    actual = set(staging_nodes)

    if actual != EXPECTED_STAGING_MODELS:
        raise M2ValidationError(
            "Staging model contract mismatch. "
            f"Missing={sorted(EXPECTED_STAGING_MODELS - actual)}; "
            f"unexpected={sorted(actual - EXPECTED_STAGING_MODELS)}"
        )

    for name, node in staging_nodes.items():
        original_path = str(
            node.get(
                "original_file_path",
                "",
            )
        )

        if not original_path.startswith(
            "models/staging/"
        ):
            raise M2ValidationError(
                f"{name} is not located under models/staging: "
                f"{original_path}"
            )

        materialized = (
            node.get(
                "config",
                {},
            ).get(
                "materialized"
            )
        )

        if materialized != "view":
            raise M2ValidationError(
                f"{name} must materialize as view; "
                f"got {materialized!r}"
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
            for dependency
            in dependencies
            if dependency.startswith(
                "source."
            )
        ]

        model_dependencies = [
            dependency
            for dependency
            in dependencies
            if dependency.startswith(
                "model."
            )
        ]

        if len(source_dependencies) != 1:
            raise M2ValidationError(
                f"{name} must depend directly on exactly "
                "one dbt source; "
                f"got {source_dependencies}"
            )

        if model_dependencies:
            raise M2ValidationError(
                f"{name} must not depend on ref() models; "
                f"got {model_dependencies}"
            )

    print(
        "PASS dbt manifest contract: "
        "10 source-only staging views"
    )


def validate_view_set(
    cursor,
    *,
    staging_schema: str,
) -> None:
    cursor.execute(
        """
        select table_name
        from information_schema.views
        where
            table_schema = %s
            and table_name like %s
        """,
        (
            staging_schema,
            "stg_%",
        ),
    )

    actual = {
        str(row[0])
        for row in cursor.fetchall()
    }

    if actual != EXPECTED_STAGING_MODELS:
        raise M2ValidationError(
            "Database staging view contract mismatch. "
            f"Missing={sorted(EXPECTED_STAGING_MODELS - actual)}; "
            f"unexpected={sorted(actual - EXPECTED_STAGING_MODELS)}"
        )

    print(
        "PASS database relation contract: "
        "exactly 10 staging views"
    )


def validate_one_to_one_grains(
    cursor,
    *,
    staging_schema: str,
) -> None:
    for staging_model, (
        raw_schema,
        raw_table,
    ) in ONE_TO_ONE_GRAINS.items():
        raw_count = row_count(
            cursor,
            schema=raw_schema,
            relation=raw_table,
        )

        staging_count = row_count(
            cursor,
            schema=staging_schema,
            relation=staging_model,
        )

        if raw_count != staging_count:
            raise M2ValidationError(
                f"{staging_model} changed source grain: "
                f"raw={raw_count}, staging={staging_count}"
            )

        print(
            f"PASS {staging_model}: "
            f"{staging_count:,} rows "
            "(1:1 source grain)"
        )


def validate_ecb_grain(
    cursor,
    *,
    staging_schema: str,
) -> None:
    raw_count = row_count(
        cursor,
        schema="raw_ecb",
        relation="fx_rates",
    )

    cursor.execute(
        """
        select count(distinct rate_date)
        from raw_ecb.fx_rates
        """
    )

    row = cursor.fetchone()

    if row is None:
        raise M2ValidationError(
            "Could not count ECB rate dates"
        )

    rate_dates = int(
        row[0]
    )

    staging_count = row_count(
        cursor,
        schema=staging_schema,
        relation="stg_ecb__fx_rates",
    )

    expected = (
        raw_count
        + rate_dates
    )

    if staging_count != expected:
        raise M2ValidationError(
            "stg_ecb__fx_rates grain mismatch: "
            f"raw={raw_count}, "
            f"rate_dates={rate_dates}, "
            f"expected_staging={expected}, "
            f"actual_staging={staging_count}"
        )

    cursor.execute(
        sql.SQL(
            """
            select count(*)
            from {}.{}
            where currency = 'EUR'
            """
        ).format(
            sql.Identifier(
                staging_schema
            ),
            sql.Identifier(
                "stg_ecb__fx_rates"
            ),
        )
    )

    eur_row = cursor.fetchone()

    eur_count = (
        int(eur_row[0])
        if eur_row
        else 0
    )

    if eur_count != rate_dates:
        raise M2ValidationError(
            "ECB staging must contain exactly "
            "one derived EUR row per rate date: "
            f"rate_dates={rate_dates}, "
            f"eur_rows={eur_count}"
        )

    print(
        "PASS stg_ecb__fx_rates: "
        f"{staging_count:,} rows "
        f"({raw_count:,} source + "
        f"{rate_dates:,} derived EUR)"
    )


def validate_numeric_types(
    cursor,
    *,
    staging_schema: str,
) -> None:
    for (
        table_name,
        column_name,
    ), (
        expected_precision,
        expected_scale,
    ) in NUMERIC_COLUMNS.items():
        cursor.execute(
            """
            select
                data_type,
                numeric_precision,
                numeric_scale
            from information_schema.columns
            where
                table_schema = %s
                and table_name = %s
                and column_name = %s
            """,
            (
                staging_schema,
                table_name,
                column_name,
            ),
        )

        row = cursor.fetchone()

        if row is None:
            raise M2ValidationError(
                f"Missing column "
                f"{table_name}.{column_name}"
            )

        (
            data_type,
            precision,
            scale,
        ) = row

        if (
            data_type != "numeric"
            or int(precision)
            != expected_precision
            or int(scale)
            != expected_scale
        ):
            raise M2ValidationError(
                f"Unexpected type for "
                f"{table_name}.{column_name}: "
                f"{data_type}({precision},{scale}); "
                f"expected numeric"
                f"({expected_precision},{expected_scale})"
            )

    print(
        "PASS canonical numeric types: "
        "money=numeric(18,2), FX=numeric(18,8)"
    )


def validate_m2() -> None:
    load_dotenv(
        PROJECT_ROOT / ".env"
    )

    staging_schema = os.getenv(
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
        validate_view_set(
            cursor,
            staging_schema=staging_schema,
        )

        validate_one_to_one_grains(
            cursor,
            staging_schema=staging_schema,
        )

        validate_ecb_grain(
            cursor,
            staging_schema=staging_schema,
        )

        validate_numeric_types(
            cursor,
            staging_schema=staging_schema,
        )

    print()
    print(
        "M2 validation passed."
    )


if __name__ == "__main__":
    validate_m2()