with source as (

    select *
    from {{ source('psp', 'settlement_items') }}

),

renamed as (

    select
        settlement_item_id::text as settlement_item_id,
        settlement_id::text as settlement_id,
        financial_event_id::text as financial_event_id,

        transaction_currency::text as transaction_currency,

        {{ minor_units_to_amount('transaction_amount_minor') }}
            as transaction_amount,

        {{ minor_units_to_amount('settlement_gross_eur_minor') }}
            as settlement_gross_eur_amount,

        {{ minor_units_to_amount('fee_eur_minor') }}
            as fee_eur_amount,

        {{ minor_units_to_amount('settlement_net_eur_minor') }}
            as settlement_net_eur_amount,

        psp_fx_rate::numeric(18, 8) as psp_fx_rate,

        _loaded_at::timestamptz as _loaded_at,
        _batch_id::text as _batch_id

    from source

)

select *
from renamed