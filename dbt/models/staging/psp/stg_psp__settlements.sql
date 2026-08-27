with source as (

    select *
    from {{ source('psp', 'settlements') }}

),

renamed as (

    select
        settlement_id::text as settlement_id,

        settlement_date::date as settlement_date,
        settlement_currency::text as settlement_currency,

        {{ minor_units_to_amount('gross_amount_minor') }}
            as gross_amount,

        {{ minor_units_to_amount('fee_amount_minor') }}
            as fee_amount,

        {{ minor_units_to_amount('net_payout_minor') }}
            as net_payout_amount,

        status::text as settlement_status,

        bank_reference::text as bank_reference,

        created_at::timestamptz as created_at,

        _loaded_at::timestamptz as _loaded_at,
        _batch_id::text as _batch_id

    from source

)

select *
from renamed