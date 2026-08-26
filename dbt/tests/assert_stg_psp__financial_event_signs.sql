select
    financial_event_id,
    event_type,
    event_amount,
    signed_event_amount

from {{ ref('stg_psp__financial_events') }}

where
    event_amount < 0

    or (
        event_type = 'CAPTURE'
        and signed_event_amount != event_amount
    )

    or (
        event_type in ('REFUND', 'CHARGEBACK')
        and signed_event_amount != -1 * event_amount
    )