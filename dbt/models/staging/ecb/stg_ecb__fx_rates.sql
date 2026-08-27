with source as (

    select *
    from {{ source('ecb', 'fx_rates') }}

),

normalized as (

    select
        rate_date::date as rate_date,
        currency::text as currency,

        units_per_eur::numeric(18, 8)
            as units_per_eur,

        (
            1::numeric
            / nullif(
                units_per_eur::numeric,
                0
            )
        )::numeric(18, 8)
            as eur_per_unit,

        false as is_derived_rate,

        _loaded_at::timestamptz as _loaded_at,
        _batch_id::text as _batch_id

    from source

),

eur_rate_dates as (

    select
        rate_date,

        'EUR'::text as currency,

        1.00000000::numeric(18, 8)
            as units_per_eur,

        1.00000000::numeric(18, 8)
            as eur_per_unit,

        true as is_derived_rate,

        max(_loaded_at)::timestamptz
            as _loaded_at,

        max(_batch_id)::text
            as _batch_id

    from normalized

    group by rate_date

),

combined as (

    select *
    from normalized

    union all

    select *
    from eur_rate_dates

)

select *
from combined