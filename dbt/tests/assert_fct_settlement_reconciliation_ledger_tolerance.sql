select
    settlement_id,

    posted_journal_entry_count,

    ledger_bank_minus_expected_amount_eur,
    ledger_fee_minus_expected_amount_eur,
    ledger_clearing_minus_expected_amount_eur,

    is_ledger_amount_within_tolerance

from {{ ref('fct_settlement_reconciliation') }}

where
    (
        posted_journal_entry_count = 1

        and is_ledger_amount_within_tolerance is distinct from (
            abs(
                ledger_bank_minus_expected_amount_eur
            ) <= {{ var('reconciliation_amount_tolerance_eur') }}

            and

            abs(
                ledger_fee_minus_expected_amount_eur
            ) <= {{ var('reconciliation_amount_tolerance_eur') }}

            and

            abs(
                ledger_clearing_minus_expected_amount_eur
            ) <= {{ var('reconciliation_amount_tolerance_eur') }}
        )
    )

    or

    (
        posted_journal_entry_count != 1
        and is_ledger_amount_within_tolerance is not null
    )