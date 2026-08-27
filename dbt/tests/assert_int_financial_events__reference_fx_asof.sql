with enriched_events as (

    select *
    from {{ ref('int_financial_events__with_reference_fx') }}

),

available_later_rates as (

    select
        events.financial_event_id,
        events.reference_fx_rate_date,
        fx.rate_date as later_eligible_rate_date

    from enriched_events as events

    inner join {{ ref('stg_ecb__fx_rates') }} as fx
        on fx.currency = events.currency
        and fx.rate_date <= events.event_date
        and (
            events.reference_fx_rate_date is null
            or fx.rate_date > events.reference_fx_rate_date
        )

)

select *
from available_later_rates