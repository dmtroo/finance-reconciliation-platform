with financial_events as (

    select *
    from {{ ref('int_financial_events__with_reference_fx') }}

),

captures as (

    select
        financial_event_id as capture_id,
        payment_attempt_id,
        invoice_id,

        event_at as capture_at,
        event_date as capture_date,

        currency,

        event_amount as capture_amount,
        event_amount_eur as capture_amount_eur,

        reference_fx_rate_date,
        reference_fx_rate,
        reference_fx_age_days,

        provider_transaction_id,

        _loaded_at,
        _batch_id

    from financial_events

    where event_type = 'CAPTURE'

),

post_capture_events as (

    select
        original_capture_id as capture_id,

        count(*)::integer
            as post_capture_event_count,

        count(*) filter (
            where event_type = 'REFUND'
        )::integer
            as refund_event_count,

        count(*) filter (
            where event_type = 'CHARGEBACK'
        )::integer
            as chargeback_event_count,

        coalesce(
            sum(event_amount) filter (
                where event_type = 'REFUND'
            ),
            0
        )::numeric(18, 2)
            as refund_amount,

        sum(event_amount_eur) filter (
            where event_type = 'REFUND'
        )::numeric(18, 2)
            as refund_amount_eur,

        count(*) filter (
            where
                event_type = 'REFUND'
                and event_amount_eur is null
        )::integer
            as refund_missing_fx_count,

        coalesce(
            sum(event_amount) filter (
                where event_type = 'CHARGEBACK'
            ),
            0
        )::numeric(18, 2)
            as chargeback_amount,

        sum(event_amount_eur) filter (
            where event_type = 'CHARGEBACK'
        )::numeric(18, 2)
            as chargeback_amount_eur,

        count(*) filter (
            where
                event_type = 'CHARGEBACK'
                and event_amount_eur is null
        )::integer
            as chargeback_missing_fx_count,

        coalesce(
            sum(signed_event_amount),
            0
        )::numeric(18, 2)
            as post_capture_signed_amount,

        sum(
            signed_event_amount_eur
        )::numeric(18, 2)
            as post_capture_signed_amount_eur,

        count(*) filter (
            where signed_event_amount_eur is null
        )::integer
            as post_capture_missing_fx_count,

        min(event_at)
            as first_post_capture_event_at,

        max(event_at)
            as last_post_capture_event_at

    from financial_events

    where
        event_type in (
            'REFUND',
            'CHARGEBACK'
        )
        and original_capture_id is not null

    group by original_capture_id

),

combined as (

    select
        captures.capture_id,
        captures.payment_attempt_id,
        captures.invoice_id,

        captures.capture_at,
        captures.capture_date,

        captures.currency,

        captures.capture_amount,
        captures.capture_amount_eur,

        captures.reference_fx_rate_date,
        captures.reference_fx_rate,
        captures.reference_fx_age_days,

        coalesce(
            post_capture_events.post_capture_event_count,
            0
        )::integer
            as post_capture_event_count,

        coalesce(
            post_capture_events.refund_event_count,
            0
        )::integer
            as refund_event_count,

        coalesce(
            post_capture_events.refund_amount,
            0
        )::numeric(18, 2)
            as refund_amount,

        case
            when coalesce(
                post_capture_events.refund_missing_fx_count,
                0
            ) > 0
                then null

            else coalesce(
                post_capture_events.refund_amount_eur,
                0
            )::numeric(18, 2)
        end
            as refund_amount_eur,

        coalesce(
            post_capture_events.chargeback_event_count,
            0
        )::integer
            as chargeback_event_count,

        coalesce(
            post_capture_events.chargeback_amount,
            0
        )::numeric(18, 2)
            as chargeback_amount,

        case
            when coalesce(
                post_capture_events.chargeback_missing_fx_count,
                0
            ) > 0
                then null

            else coalesce(
                post_capture_events.chargeback_amount_eur,
                0
            )::numeric(18, 2)
        end
            as chargeback_amount_eur,

        coalesce(
            post_capture_events.post_capture_signed_amount,
            0
        )::numeric(18, 2)
            as post_capture_signed_amount,

        (
            captures.capture_amount
            + coalesce(
                post_capture_events.post_capture_signed_amount,
                0
            )
        )::numeric(18, 2)
            as net_capture_amount,

        case
            when captures.capture_amount_eur is null
                then null

            when coalesce(
                post_capture_events.post_capture_missing_fx_count,
                0
            ) > 0
                then null

            else (
                captures.capture_amount_eur
                + coalesce(
                    post_capture_events.post_capture_signed_amount_eur,
                    0
                )
            )::numeric(18, 2)
        end
            as net_capture_amount_eur,

        (
            coalesce(
                post_capture_events.refund_event_count,
                0
            ) > 0
        ) as has_refund,

        (
            coalesce(
                post_capture_events.chargeback_event_count,
                0
            ) > 0
        ) as has_chargeback,

        post_capture_events.first_post_capture_event_at,
        post_capture_events.last_post_capture_event_at,

        captures.provider_transaction_id,

        captures._loaded_at,
        captures._batch_id

    from captures

    left join post_capture_events
        on captures.capture_id
        = post_capture_events.capture_id

)

select *
from combined