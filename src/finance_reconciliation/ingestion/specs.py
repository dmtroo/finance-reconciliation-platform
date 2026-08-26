from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

LoadMode = Literal[
    "snapshot",
    "append",
]


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    kind: str


@dataclass(frozen=True)
class TableSpec:
    key: str
    relative_path: Path

    schema: str
    table: str

    primary_key: tuple[str, ...]

    mode: LoadMode

    columns: tuple[
        ColumnSpec,
        ...,
    ]


def col(
    name: str,
    kind: str = "text",
) -> ColumnSpec:
    return ColumnSpec(
        name=name,
        kind=kind,
    )


TABLE_SPECS = (
    TableSpec(
        key="billing/products",
        relative_path=Path(
            "billing/products.csv"
        ),
        schema="raw_billing",
        table="products",
        primary_key=("product_id",),
        mode="snapshot",
        columns=(
            col("product_id"),
            col("product_name"),
            col("product_family"),
            col("billing_interval"),
            col(
                "list_price_minor",
                "integer",
            ),
            col("currency"),
            col(
                "is_active",
                "boolean",
            ),
            col(
                "created_at",
                "timestamp",
            ),
            col(
                "updated_at",
                "timestamp",
            ),
        ),
    ),

    TableSpec(
        key="billing/subscriptions",
        relative_path=Path(
            "billing/subscriptions.csv"
        ),
        schema="raw_billing",
        table="subscriptions",
        primary_key=(
            "subscription_id",
        ),
        mode="snapshot",
        columns=(
            col("subscription_id"),
            col("customer_id"),
            col("product_id"),
            col(
                "subscription_status"
            ),
            col(
                "started_at",
                "timestamp",
            ),
            col(
                "cancelled_at",
                "timestamp",
            ),
            col(
                "created_at",
                "timestamp",
            ),
            col(
                "updated_at",
                "timestamp",
            ),
        ),
    ),

    TableSpec(
        key="billing/invoices",
        relative_path=Path(
            "billing/invoices.csv"
        ),
        schema="raw_billing",
        table="invoices",
        primary_key=("invoice_id",),
        mode="snapshot",
        columns=(
            col("invoice_id"),
            col("subscription_id"),
            col("customer_id"),
            col("product_id"),
            col(
                "invoice_date",
                "date",
            ),
            col(
                "due_date",
                "date",
            ),
            col("currency"),
            col(
                "subtotal_minor",
                "integer",
            ),
            col(
                "tax_minor",
                "integer",
            ),
            col(
                "total_minor",
                "integer",
            ),
            col("invoice_status"),
            col(
                "created_at",
                "timestamp",
            ),
            col(
                "updated_at",
                "timestamp",
            ),
        ),
    ),

    TableSpec(
        key="psp/payment_attempts",
        relative_path=Path(
            "psp/payment_attempts.csv"
        ),
        schema="raw_psp",
        table="payment_attempts",
        primary_key=(
            "payment_attempt_id",
        ),
        mode="append",
        columns=(
            col("payment_attempt_id"),
            col("invoice_id"),
            col(
                "provider_customer_id"
            ),
            col(
                "attempted_at",
                "timestamp",
            ),
            col("currency"),
            col(
                "amount_minor",
                "integer",
            ),
            col(
                "payment_method_type"
            ),
            col("status"),
            col("failure_code"),
            col(
                "provider_transaction_id"
            ),
        ),
    ),

    TableSpec(
        key="psp/financial_events",
        relative_path=Path(
            "psp/financial_events.csv"
        ),
        schema="raw_psp",
        table="financial_events",
        primary_key=(
            "financial_event_id",
        ),
        mode="append",
        columns=(
            col(
                "financial_event_id"
            ),
            col("event_type"),
            col(
                "payment_attempt_id"
            ),
            col("invoice_id"),
            col(
                "original_capture_id"
            ),
            col(
                "event_at",
                "timestamp",
            ),
            col("currency"),
            col(
                "amount_minor",
                "integer",
            ),
            col(
                "provider_transaction_id"
            ),
        ),
    ),

    TableSpec(
        key="psp/settlements",
        relative_path=Path(
            "psp/settlements.csv"
        ),
        schema="raw_psp",
        table="settlements",
        primary_key=(
            "settlement_id",
        ),
        mode="snapshot",
        columns=(
            col("settlement_id"),
            col(
                "settlement_date",
                "date",
            ),
            col(
                "settlement_currency"
            ),
            col(
                "gross_amount_minor",
                "integer",
            ),
            col(
                "fee_amount_minor",
                "integer",
            ),
            col(
                "net_payout_minor",
                "integer",
            ),
            col("status"),
            col("bank_reference"),
            col(
                "created_at",
                "timestamp",
            ),
        ),
    ),

    TableSpec(
        key="psp/settlement_items",
        relative_path=Path(
            "psp/settlement_items.csv"
        ),
        schema="raw_psp",
        table="settlement_items",
        primary_key=(
            "settlement_item_id",
        ),
        mode="append",
        columns=(
            col(
                "settlement_item_id"
            ),
            col("settlement_id"),
            col(
                "financial_event_id"
            ),
            col(
                "transaction_currency"
            ),
            col(
                "transaction_amount_minor",
                "integer",
            ),
            col(
                "settlement_gross_eur_minor",
                "integer",
            ),
            col(
                "fee_eur_minor",
                "integer",
            ),
            col(
                "settlement_net_eur_minor",
                "integer",
            ),
            col(
                "psp_fx_rate",
                "decimal",
            ),
        ),
    ),

    TableSpec(
        key="bank/statement_transactions",
        relative_path=Path(
            "bank/statement_transactions.csv"
        ),
        schema="raw_bank",
        table="statement_transactions",
        primary_key=(
            "bank_transaction_id",
        ),
        mode="append",
        columns=(
            col(
                "bank_transaction_id"
            ),
            col(
                "booking_date",
                "date",
            ),
            col(
                "value_date",
                "date",
            ),
            col("direction"),
            col("currency"),
            col(
                "amount_minor",
                "integer",
            ),
            col("counterparty"),
            col(
                "payment_reference"
            ),
            col("status"),
        ),
    ),

    TableSpec(
        key="accounting/journal_lines",
        relative_path=Path(
            "accounting/journal_lines.csv"
        ),
        schema="raw_accounting",
        table="journal_lines",
        primary_key=(
            "journal_line_id",
        ),
        mode="append",
        columns=(
            col("journal_line_id"),
            col("journal_entry_id"),
            col(
                "posting_date",
                "date",
            ),
            col("account_code"),
            col("account_name"),
            col(
                "debit_eur_minor",
                "integer",
            ),
            col(
                "credit_eur_minor",
                "integer",
            ),
            col("source_system"),
            col(
                "source_reference_type"
            ),
            col(
                "source_reference"
            ),
            col("journal_status"),
            col(
                "created_at",
                "timestamp",
            ),
        ),
    ),
)