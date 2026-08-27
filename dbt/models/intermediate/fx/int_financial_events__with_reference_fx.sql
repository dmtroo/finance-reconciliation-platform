with financial_events as (

    select *
    from {{ ref('stg_psp__financial_events') }}

),

reference_fx as (

    select *
    from {{ ref('stg_ecb__fx_rates') }}

),

candidate_rates as (

    select
        financial_events.financial_event_id,
        financial_events.event_type,
        financial_events.payment_attempt_id,
        financial_events.invoice_id,
        financial_events.original_capture_id,

        financial_events.event_at,
        financial_events.event_date,

        financial_events.currency,

        financial_events.event_amount,
        financial_events.signed_event_amount,

        financial_events.provider_transaction_id,

        reference_fx.rate_date
            as reference_fx_rate_date,

        reference_fx.eur_per_unit
            as reference_fx_rate,

        row_number() over (
            partition by financial_events.financial_event_id
            order by reference_fx.rate_date desc nulls last
        ) as fx_candidate_rank,

        financial_events._loaded_at,
        financial_events._batch_id

    from financial_events

    left join reference_fx
        on reference_fx.currency = financial_events.currency
        and reference_fx.rate_date <= financial_events.event_date

),

matched as (

    select
        financial_event_id,
        event_type,
        payment_attempt_id,
        invoice_id,
        original_capture_id,

        event_at,
        event_date,

        currency,

        event_amount,
        signed_event_amount,

        reference_fx_rate_date,
        reference_fx_rate,

        case
            when reference_fx_rate is not null
                then (
                    event_amount
                    * reference_fx_rate
                )::numeric(18, 2)
        end as event_amount_eur,

        case
            when reference_fx_rate is not null
                then (
                    signed_event_amount
                    * reference_fx_rate
                )::numeric(18, 2)
        end as signed_event_amount_eur,

        case
            when reference_fx_rate_date is not null
                then (
                    event_date
                    - reference_fx_rate_date
                )::integer
        end as reference_fx_age_days,

        provider_transaction_id,

        _loaded_at,
        _batch_id

    from candidate_rates

    where fx_candidate_rank = 1

)

select *
from matched