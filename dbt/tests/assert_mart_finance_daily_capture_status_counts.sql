select
    business_date,
    product_id,
    currency,

    capture_count,

    reconciled_capture_count,
    pending_capture_count,
    open_break_capture_count,
    excluded_capture_count

from {{ ref('mart_finance_daily') }}

where
    capture_count
    != (
        reconciled_capture_count
        + pending_capture_count
        + open_break_capture_count
        + excluded_capture_count
    )