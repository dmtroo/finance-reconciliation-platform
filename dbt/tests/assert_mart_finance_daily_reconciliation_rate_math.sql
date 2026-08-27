select
    business_date,
    product_id,
    currency,

    valued_capture_amount_eur,
    reconciled_capture_amount_eur,
    amount_reconciliation_rate

from {{ ref('mart_finance_daily') }}

where
    valued_capture_amount_eur > 0

    and abs(
        amount_reconciliation_rate
        - (
            reconciled_capture_amount_eur
            / valued_capture_amount_eur
        )
    ) > 0.000001