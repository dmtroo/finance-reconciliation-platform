with source as (

    select *
    from {{ source('psp', 'financial_events') }}

),

renamed as (

    select
        financial_event_id::text as financial_event_id,
        event_type::text as event_type,

        payment_attempt_id::text as payment_attempt_id,
        invoice_id::text as invoice_id,
        original_capture_id::text as original_capture_id,

        event_at::timestamptz as event_at,
        event_at::date as event_date,

        currency::text as currency,

        {{ minor_units_to_amount('amount_minor') }}
            as event_amount,

        case
            when event_type = 'CAPTURE'
                then {{ minor_units_to_amount('amount_minor') }}

            when event_type in ('REFUND', 'CHARGEBACK')
                then -1 * {{ minor_units_to_amount('amount_minor') }}

            else null
        end::numeric(18, 2)
            as signed_event_amount,

        provider_transaction_id::text as provider_transaction_id,

        _loaded_at::timestamptz as _loaded_at,
        _batch_id::text as _batch_id

    from source

)

select *
from renamed