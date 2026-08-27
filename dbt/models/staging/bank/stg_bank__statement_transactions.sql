with source as (

    select *
    from {{ source('bank', 'statement_transactions') }}

),

renamed as (

    select
        bank_transaction_id::text as bank_transaction_id,

        booking_date::date as booking_date,
        value_date::date as value_date,

        direction::text as direction,
        currency::text as currency,

        {{ minor_units_to_amount('amount_minor') }}
            as bank_amount,

        counterparty::text as counterparty,
        payment_reference::text as payment_reference,

        status::text as bank_status,

        _loaded_at::timestamptz as _loaded_at,
        _batch_id::text as _batch_id

    from source

)

select *
from renamed