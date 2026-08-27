select
    settlement_id,
    eligible_bank_receipt_count,
    bank_amount,
    net_payout_amount,
    bank_minus_settlement_amount,
    is_bank_amount_within_tolerance

from {{ ref('fct_settlement_reconciliation') }}

where
    (
        eligible_bank_receipt_count = 1
        and bank_amount is not null

        and is_bank_amount_within_tolerance is distinct from (
            abs(
                bank_minus_settlement_amount
            ) <= {{ var('reconciliation_amount_tolerance_eur') }}
        )
    )

    or

    (
        (
            eligible_bank_receipt_count != 1
            or bank_amount is null
        )

        and is_bank_amount_within_tolerance is not null
    )