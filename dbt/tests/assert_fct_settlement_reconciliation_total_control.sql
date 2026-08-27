select
    settlement_id,

    gross_header_minus_items_amount,
    fee_header_minus_items_amount,
    net_header_minus_items_amount,

    is_settlement_total_within_tolerance

from {{ ref('fct_settlement_reconciliation') }}

where
    is_settlement_total_within_tolerance
    is distinct from (
        abs(
            gross_header_minus_items_amount
        ) <= {{ var('reconciliation_amount_tolerance_eur') }}

        and

        abs(
            fee_header_minus_items_amount
        ) <= {{ var('reconciliation_amount_tolerance_eur') }}

        and

        abs(
            net_header_minus_items_amount
        ) <= {{ var('reconciliation_amount_tolerance_eur') }}
    )