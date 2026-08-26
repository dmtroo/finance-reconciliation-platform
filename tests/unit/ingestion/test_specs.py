from finance_reconciliation.ingestion.specs import (
    TABLE_SPECS,
)


def test_exactly_nine_synthetic_tables_are_loaded() -> None:
    assert len(
        TABLE_SPECS
    ) == 9


def test_snapshot_table_modes() -> None:
    modes = {
        spec.key: spec.mode
        for spec in TABLE_SPECS
    }

    assert modes[
        "billing/products"
    ] == "snapshot"

    assert modes[
        "billing/subscriptions"
    ] == "snapshot"

    assert modes[
        "billing/invoices"
    ] == "snapshot"

    assert modes[
        "psp/settlements"
    ] == "snapshot"


def test_event_tables_are_append_like() -> None:
    modes = {
        spec.key: spec.mode
        for spec in TABLE_SPECS
    }

    append_tables = {
        "psp/payment_attempts",
        "psp/financial_events",
        "psp/settlement_items",
        "bank/statement_transactions",
        "accounting/journal_lines",
    }

    for key in append_tables:
        assert modes[key] == "append"