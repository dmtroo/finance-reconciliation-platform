with invoices as (

    select *
    from {{ ref('stg_billing__invoices') }}

),

payment_attempts as (

    select *
    from {{ ref('stg_psp__payment_attempts') }}

),

capture_lifecycle as (

    select *
    from {{ ref('int_captures__lifecycle') }}

),

attempt_summary as (

    select
        invoice_id,

        count(*)::integer
            as payment_attempt_count,

        count(*) filter (
            where payment_status = 'SUCCEEDED'
        )::integer
            as successful_attempt_count,

        count(*) filter (
            where payment_status = 'DECLINED'
        )::integer
            as declined_attempt_count,

        count(*) filter (
            where payment_status = 'CANCELLED'
        )::integer
            as cancelled_attempt_count,

        min(attempted_at)
            as first_attempt_at,

        max(attempted_at)
            as last_attempt_at,

        min(attempted_at) filter (
            where payment_status = 'SUCCEEDED'
        ) as first_successful_attempt_at,

        max(attempted_at) filter (
            where payment_status = 'SUCCEEDED'
        ) as last_successful_attempt_at

    from payment_attempts

    group by invoice_id

),

capture_summary as (

    select
        invoice_id,

        count(*)::integer
            as capture_count,

        min(capture_at)
            as first_capture_at,

        max(capture_at)
            as last_capture_at,

        sum(
            capture_amount
        )::numeric(18, 2)
            as capture_amount,

        case
            when count(*) filter (
                where capture_amount_eur is null
            ) > 0
                then null

            else sum(
                capture_amount_eur
            )::numeric(18, 2)
        end
            as capture_amount_eur,

        sum(
            refund_event_count
        )::integer
            as refund_event_count,

        sum(
            refund_amount
        )::numeric(18, 2)
            as refund_amount,

        case
            when count(*) filter (
                where refund_amount_eur is null
            ) > 0
                then null

            else sum(
                refund_amount_eur
            )::numeric(18, 2)
        end
            as refund_amount_eur,

        sum(
            chargeback_event_count
        )::integer
            as chargeback_event_count,

        sum(
            chargeback_amount
        )::numeric(18, 2)
            as chargeback_amount,

        case
            when count(*) filter (
                where chargeback_amount_eur is null
            ) > 0
                then null

            else sum(
                chargeback_amount_eur
            )::numeric(18, 2)
        end
            as chargeback_amount_eur,

        sum(
            net_capture_amount
        )::numeric(18, 2)
            as net_payment_amount,

        case
            when count(*) filter (
                where net_capture_amount_eur is null
            ) > 0
                then null

            else sum(
                net_capture_amount_eur
            )::numeric(18, 2)
        end
            as net_payment_amount_eur

    from capture_lifecycle

    group by invoice_id

),

combined as (

    select
        invoices.invoice_id,
        invoices.subscription_id,
        invoices.customer_id,
        invoices.product_id,

        invoices.invoice_date,
        invoices.due_date,

        invoices.currency as invoice_currency,

        invoices.subtotal_amount,
        invoices.tax_amount,
        invoices.total_amount,

        invoices.invoice_status,

        coalesce(
            attempt_summary.payment_attempt_count,
            0
        )::integer
            as payment_attempt_count,

        coalesce(
            attempt_summary.successful_attempt_count,
            0
        )::integer
            as successful_attempt_count,

        coalesce(
            attempt_summary.declined_attempt_count,
            0
        )::integer
            as declined_attempt_count,

        coalesce(
            attempt_summary.cancelled_attempt_count,
            0
        )::integer
            as cancelled_attempt_count,

        attempt_summary.first_attempt_at,
        attempt_summary.last_attempt_at,
        attempt_summary.first_successful_attempt_at,
        attempt_summary.last_successful_attempt_at,

        coalesce(
            capture_summary.capture_count,
            0
        )::integer
            as capture_count,

        capture_summary.first_capture_at,
        capture_summary.last_capture_at,

        coalesce(
            capture_summary.capture_amount,
            0
        )::numeric(18, 2)
            as capture_amount,

        capture_summary.capture_amount_eur,

        coalesce(
            capture_summary.refund_event_count,
            0
        )::integer
            as refund_event_count,

        coalesce(
            capture_summary.refund_amount,
            0
        )::numeric(18, 2)
            as refund_amount,

        capture_summary.refund_amount_eur,

        coalesce(
            capture_summary.chargeback_event_count,
            0
        )::integer
            as chargeback_event_count,

        coalesce(
            capture_summary.chargeback_amount,
            0
        )::numeric(18, 2)
            as chargeback_amount,

        capture_summary.chargeback_amount_eur,

        coalesce(
            capture_summary.net_payment_amount,
            0
        )::numeric(18, 2)
            as net_payment_amount,

        capture_summary.net_payment_amount_eur,

        (
            coalesce(
                capture_summary.capture_count,
                0
            ) > 0
        ) as has_capture,

        (
            coalesce(
                capture_summary.refund_event_count,
                0
            ) > 0
        ) as has_refund,

        (
            coalesce(
                capture_summary.chargeback_event_count,
                0
            ) > 0
        ) as has_chargeback,

        invoices.created_at,
        invoices.updated_at,

        invoices._loaded_at,
        invoices._batch_id

    from invoices

    left join attempt_summary
        on invoices.invoice_id
        = attempt_summary.invoice_id

    left join capture_summary
        on invoices.invoice_id
        = capture_summary.invoice_id

)

select *
from combined