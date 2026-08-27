select
    capture_id,
    capture_amount,
    refund_amount,
    chargeback_amount,
    net_capture_amount

from {{ ref('int_captures__lifecycle') }}

where
    abs(
        net_capture_amount
        - (
            capture_amount
            - refund_amount
            - chargeback_amount
        )
    ) > 0.01