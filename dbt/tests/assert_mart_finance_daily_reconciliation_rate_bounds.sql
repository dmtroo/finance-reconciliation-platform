select
    business_date,
    product_id,
    currency,
    amount_reconciliation_rate

from {{ ref('mart_finance_daily') }}

where
    amount_reconciliation_rate is not null

    and (
        amount_reconciliation_rate < 0
        or amount_reconciliation_rate > 1
    )