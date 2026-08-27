with financial_events as (

    select *
    from {{ ref('int_financial_events__with_reference_fx') }}

),

settlement_items as (

    select *
    from {{ ref('stg_psp__settlement_items') }}

),

settlements as (

    select *
    from {{ ref('stg_psp__settlements') }}

),

settlement_item_summary as (

    select
        financial_event_id,

        count(*)::integer
            as settlement_item_count,

        count(
            distinct settlement_id
        )::integer
            as settlement_count,

        case
            when count(
                distinct settlement_id
            ) = 1
                then min(settlement_id)
        end as settlement_id,

        sum(
            transaction_amount
        )::numeric(18, 2)
            as settlement_transaction_amount,

        sum(
            settlement_gross_eur_amount
        )::numeric(18, 2)
            as settlement_gross_eur_amount,

        sum(
            fee_eur_amount
        )::numeric(18, 2)
            as settlement_fee_eur_amount,

        sum(
            settlement_net_eur_amount
        )::numeric(18, 2)
            as settlement_net_eur_amount,

        case
            when count(
                distinct psp_fx_rate
            ) = 1
                then min(
                    psp_fx_rate
                )::numeric(18, 8)
        end as psp_fx_rate

    from settlement_items

    group by financial_event_id

),

combined as (

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

        financial_events.reference_fx_rate_date,
        financial_events.reference_fx_rate,
        financial_events.reference_fx_age_days,

        financial_events.event_amount_eur,
        financial_events.signed_event_amount_eur,

        coalesce(
            settlement_item_summary.settlement_item_count,
            0
        )::integer
            as settlement_item_count,

        coalesce(
            settlement_item_summary.settlement_count,
            0
        )::integer
            as settlement_count,

        settlement_item_summary.settlement_id,

        settlements.settlement_date,
        settlements.settlement_status,
        settlements.bank_reference,

        case
            when settlements.settlement_date is not null
                then (
                    settlements.settlement_date
                    - financial_events.event_date
                )::integer
        end as settlement_delay_days,

        settlement_item_summary.settlement_transaction_amount,
        settlement_item_summary.settlement_gross_eur_amount,
        settlement_item_summary.settlement_fee_eur_amount,
        settlement_item_summary.settlement_net_eur_amount,

        settlement_item_summary.psp_fx_rate,

        case
            when
                settlement_item_summary.psp_fx_rate is not null
                and financial_events.reference_fx_rate is not null
                and financial_events.reference_fx_rate != 0
                then (
                    (
                        settlement_item_summary.psp_fx_rate
                        - financial_events.reference_fx_rate
                    )
                    / financial_events.reference_fx_rate
                )::numeric(18, 8)
        end as psp_fx_rate_variance_ratio,

        financial_events.provider_transaction_id,

        financial_events._loaded_at,
        financial_events._batch_id

    from financial_events

    left join settlement_item_summary
        on financial_events.financial_event_id
        = settlement_item_summary.financial_event_id

    left join settlements
        on settlement_item_summary.settlement_id
        = settlements.settlement_id

)

select *
from combined