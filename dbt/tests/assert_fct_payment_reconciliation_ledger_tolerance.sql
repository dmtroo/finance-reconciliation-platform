select
    capture_id,
    ledger_debit_minus_expected_amount_eur,
    ledger_credit_minus_expected_amount_eur,
    is_ledger_amount_within_tolerance

from {{ ref('fct_payment_reconciliation') }}

where
    posted_journal_entry_count = 1
    and capture_amount_eur is not null

    and is_ledger_amount_within_tolerance is distinct from (
        abs(
            ledger_debit_minus_expected_amount_eur
        ) <= {{ var('reconciliation_amount_tolerance_eur') }}

        and

        abs(
            ledger_credit_minus_expected_amount_eur
        ) <= {{ var('reconciliation_amount_tolerance_eur') }}
    )