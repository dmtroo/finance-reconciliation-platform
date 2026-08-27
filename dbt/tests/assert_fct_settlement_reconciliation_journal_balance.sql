select
    settlement_id,
    posted_journal_entry_count,
    posted_journal_balance_difference_eur,
    is_journal_balanced_within_tolerance

from {{ ref('fct_settlement_reconciliation') }}

where
    (
        posted_journal_entry_count = 1
        and posted_journal_balance_difference_eur is not null

        and is_journal_balanced_within_tolerance is distinct from (
            abs(
                posted_journal_balance_difference_eur
            ) <= {{ var('reconciliation_amount_tolerance_eur') }}
        )
    )

    or

    (
        (
            posted_journal_entry_count != 1
            or posted_journal_balance_difference_eur is null
        )

        and is_journal_balanced_within_tolerance is not null
    )