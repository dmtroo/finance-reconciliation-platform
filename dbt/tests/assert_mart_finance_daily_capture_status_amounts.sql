select
    business_date,
    product_id,
    currency,

    valued_capture_amount_eur,

    reconciled_capture_amount_eur,
    pending_capture_amount_eur,
    open_break_capture_amount_eur,
    excluded_capture_amount_eur

from {{ ref('mart_finance_daily') }}

where
    abs(
        valued_capture_amount_eur
        - (
            reconciled_capture_amount_eur
            + pending_capture_amount_eur
            + open_break_capture_amount_eur
            + excluded_capture_amount_eur
        )
    ) > 0.01