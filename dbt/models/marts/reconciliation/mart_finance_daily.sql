with parameters as (

    select
        '{{ var("reconciliation_as_of_date") }}'::date
            as as_of_date

),

products as (

    select *
    from {{ ref('stg_billing__products') }}

),

invoices as (

    select *
    from {{ ref('int_invoices__payment_summary') }}

),

payment_fact as (

    select *
    from {{ ref('fct_payment_reconciliation') }}

),

financial_events as (

    select *
    from {{ ref('int_financial_events__with_reference_fx') }}

),

exceptions as (

    select *
    from {{ ref('mart_reconciliation_exceptions') }}

),

financial_event_to_capture as (

    select
        financial_event_id,

        case
            when event_type = 'CAPTURE'
                then financial_event_id
            else original_capture_id
        end as capture_id

    from financial_events

    where event_type in (
        'CAPTURE',
        'REFUND',
        'CHARGEBACK'
    )

),

capture_exception_links as (

    select
        payment.capture_id,
        exceptions.exception_id,
        exceptions.exception_status,
        exceptions.severity

    from exceptions

    inner join payment_fact as payment
        on exceptions.entity_type = 'CAPTURE'
        and exceptions.entity_id = payment.capture_id

    union all

    select
        payment.capture_id,
        exceptions.exception_id,
        exceptions.exception_status,
        exceptions.severity

    from exceptions

    inner join payment_fact as payment
        on exceptions.entity_type = 'INVOICE'
        and exceptions.entity_id = payment.invoice_id

    union all

    select
        payment.capture_id,
        exceptions.exception_id,
        exceptions.exception_status,
        exceptions.severity

    from exceptions

    inner join financial_event_to_capture as event_mapping
        on exceptions.entity_type = 'FINANCIAL_EVENT'
        and exceptions.entity_id
        = event_mapping.financial_event_id

    inner join payment_fact as payment
        on event_mapping.capture_id
        = payment.capture_id

    union all

    select
        payment.capture_id,
        exceptions.exception_id,
        exceptions.exception_status,
        exceptions.severity

    from exceptions

    inner join payment_fact as payment
        on exceptions.entity_type = 'SETTLEMENT'
        and exceptions.entity_id = payment.settlement_id

),

capture_exception_summary as (

    select
        capture_id,

        count(
            distinct exception_id
        )::integer
            as linked_exception_count,

        count(
            distinct exception_id
        ) filter (
            where exception_status = 'PENDING'
        )::integer
            as pending_exception_count,

        count(
            distinct exception_id
        ) filter (
            where exception_status = 'OPEN_BREAK'
        )::integer
            as open_break_exception_count,

        count(
            distinct exception_id
        ) filter (
            where exception_status = 'RESOLVED'
        )::integer
            as resolved_exception_count,

        count(
            distinct exception_id
        ) filter (
            where exception_status = 'EXCLUDED'
        )::integer
            as excluded_exception_count,

        count(
            distinct exception_id
        ) filter (
            where severity = 'CRITICAL'
        )::integer
            as critical_exception_count

    from capture_exception_links

    group by capture_id

),

capture_classified as (

    select
        payment.*,

        coalesce(
            exception_summary.linked_exception_count,
            0
        )::integer
            as linked_exception_count,

        coalesce(
            exception_summary.pending_exception_count,
            0
        )::integer
            as pending_exception_count,

        coalesce(
            exception_summary.open_break_exception_count,
            0
        )::integer
            as open_break_exception_count,

        coalesce(
            exception_summary.resolved_exception_count,
            0
        )::integer
            as resolved_exception_count,

        coalesce(
            exception_summary.excluded_exception_count,
            0
        )::integer
            as excluded_exception_count,

        coalesce(
            exception_summary.critical_exception_count,
            0
        )::integer
            as critical_exception_count,

        case
            when coalesce(
                exception_summary.excluded_exception_count,
                0
            ) > 0
                then 'EXCLUDED'

            when coalesce(
                exception_summary.open_break_exception_count,
                0
            ) > 0
                then 'OPEN_BREAK'

            when coalesce(
                exception_summary.pending_exception_count,
                0
            ) > 0
                then 'PENDING'

            else 'RECONCILED'
        end::text
            as capture_reconciliation_status

    from payment_fact as payment

    left join capture_exception_summary as exception_summary
        on payment.capture_id
        = exception_summary.capture_id

),

invoice_daily as (

    select
        invoices.invoice_date
            as business_date,

        invoices.product_id,

        invoices.invoice_currency
            as currency,

        count(*)::integer
            as invoice_count,

        count(*) filter (
            where invoice_status = 'PAID'
        )::integer
            as paid_invoice_count,

        count(*) filter (
            where invoice_status = 'UNCOLLECTIBLE'
        )::integer
            as uncollectible_invoice_count,

        count(*) filter (
            where capture_count > 0
        )::integer
            as invoice_with_capture_count,

        sum(
            total_amount
        )::numeric(18, 2)
            as invoice_total_amount

    from invoices

    cross join parameters

    where invoices.invoice_date
        <= parameters.as_of_date

    group by
        invoices.invoice_date,
        invoices.product_id,
        invoices.invoice_currency

),

payment_daily_base as (

    select
        captures.capture_date
            as business_date,

        captures.product_id,

        captures.capture_currency
            as currency,

        count(*)::integer
            as capture_count,

        sum(
            captures.capture_amount
        )::numeric(18, 2)
            as capture_amount,

        sum(
            captures.capture_amount_eur
        ) filter (
            where captures.capture_amount_eur is not null
        )::numeric(18, 2)
            as valued_capture_amount_eur,

        count(*) filter (
            where captures.capture_amount_eur is null
        )::integer
            as unvalued_capture_count,

        sum(
            captures.refund_amount
        )::numeric(18, 2)
            as refund_amount,

        sum(
            captures.refund_amount_eur
        ) filter (
            where captures.refund_amount_eur is not null
        )::numeric(18, 2)
            as valued_refund_amount_eur,

        sum(
            captures.chargeback_amount
        )::numeric(18, 2)
            as chargeback_amount,

        sum(
            captures.chargeback_amount_eur
        ) filter (
            where captures.chargeback_amount_eur is not null
        )::numeric(18, 2)
            as valued_chargeback_amount_eur,

        sum(
            captures.net_capture_amount
        )::numeric(18, 2)
            as net_payment_amount,

        sum(
            captures.net_capture_amount_eur
        ) filter (
            where captures.net_capture_amount_eur is not null
        )::numeric(18, 2)
            as valued_net_payment_amount_eur,

        count(*) filter (
            where
                captures.capture_reconciliation_status
                = 'RECONCILED'
        )::integer
            as reconciled_capture_count,

        count(*) filter (
            where
                captures.capture_reconciliation_status
                = 'PENDING'
        )::integer
            as pending_capture_count,

        count(*) filter (
            where
                captures.capture_reconciliation_status
                = 'OPEN_BREAK'
        )::integer
            as open_break_capture_count,

        count(*) filter (
            where
                captures.capture_reconciliation_status
                = 'EXCLUDED'
        )::integer
            as excluded_capture_count,

        sum(
            captures.capture_amount_eur
        ) filter (
            where
                captures.capture_reconciliation_status
                = 'RECONCILED'
                and captures.capture_amount_eur is not null
        )::numeric(18, 2)
            as reconciled_capture_amount_eur,

        sum(
            captures.capture_amount_eur
        ) filter (
            where
                captures.capture_reconciliation_status
                = 'PENDING'
                and captures.capture_amount_eur is not null
        )::numeric(18, 2)
            as pending_capture_amount_eur,

        sum(
            captures.capture_amount_eur
        ) filter (
            where
                captures.capture_reconciliation_status
                = 'OPEN_BREAK'
                and captures.capture_amount_eur is not null
        )::numeric(18, 2)
            as open_break_capture_amount_eur,

        sum(
            captures.capture_amount_eur
        ) filter (
            where
                captures.capture_reconciliation_status
                = 'EXCLUDED'
                and captures.capture_amount_eur is not null
        )::numeric(18, 2)
            as excluded_capture_amount_eur

    from capture_classified as captures

    cross join parameters

    where captures.capture_date
        <= parameters.as_of_date

    group by
        captures.capture_date,
        captures.product_id,
        captures.capture_currency

),

payment_daily as (

    select
        *,

        case
            when
                valued_capture_amount_eur is null
                or valued_capture_amount_eur = 0
                then null

            else (
                coalesce(
                    reconciled_capture_amount_eur,
                    0
                )
                / valued_capture_amount_eur
            )::numeric(18, 6)
        end as amount_reconciliation_rate

    from payment_daily_base

),

exception_daily as (

    select
        exceptions.business_date,
        exceptions.product_id,
        exceptions.currency,

        count(*)::integer
            as exception_count,

        count(*) filter (
            where exception_status = 'PENDING'
        )::integer
            as pending_exception_count,

        count(*) filter (
            where exception_status = 'OPEN_BREAK'
        )::integer
            as open_break_exception_count,

        count(*) filter (
            where exception_status = 'RESOLVED'
        )::integer
            as resolved_exception_count,

        count(*) filter (
            where severity = 'CRITICAL'
        )::integer
            as critical_exception_count,

        count(*) filter (
            where severity = 'WARNING'
        )::integer
            as warning_exception_count,

        count(*) filter (
            where severity = 'INFO'
        )::integer
            as info_exception_count,

        sum(
            exception_amount_eur
        )::numeric(18, 2)
            as gross_exception_amount_eur,

        sum(
            exception_amount_eur
        ) filter (
            where exception_status = 'OPEN_BREAK'
        )::numeric(18, 2)
            as open_break_exception_amount_eur,

        sum(
            exception_amount_eur
        ) filter (
            where exception_status = 'PENDING'
        )::numeric(18, 2)
            as pending_exception_amount_eur

    from exceptions

    cross join parameters

    where exceptions.business_date
        <= parameters.as_of_date

    group by
        exceptions.business_date,
        exceptions.product_id,
        exceptions.currency

),

daily_keys as (

    select
        business_date,
        product_id,
        currency
    from invoice_daily

    union

    select
        business_date,
        product_id,
        currency
    from payment_daily

    union

    select
        business_date,
        product_id,
        currency
    from exception_daily

),

final as (

    select
        daily_keys.business_date,

        daily_keys.product_id,

        products.product_name,
        products.product_family,

        daily_keys.currency,

        coalesce(
            invoice_daily.invoice_count,
            0
        )::integer
            as invoice_count,

        coalesce(
            invoice_daily.paid_invoice_count,
            0
        )::integer
            as paid_invoice_count,

        coalesce(
            invoice_daily.uncollectible_invoice_count,
            0
        )::integer
            as uncollectible_invoice_count,

        coalesce(
            invoice_daily.invoice_with_capture_count,
            0
        )::integer
            as invoice_with_capture_count,

        coalesce(
            invoice_daily.invoice_total_amount,
            0
        )::numeric(18, 2)
            as invoice_total_amount,

        coalesce(
            payment_daily.capture_count,
            0
        )::integer
            as capture_count,

        coalesce(
            payment_daily.capture_amount,
            0
        )::numeric(18, 2)
            as capture_amount,

        coalesce(
            payment_daily.valued_capture_amount_eur,
            0
        )::numeric(18, 2)
            as valued_capture_amount_eur,

        coalesce(
            payment_daily.unvalued_capture_count,
            0
        )::integer
            as unvalued_capture_count,

        coalesce(
            payment_daily.refund_amount,
            0
        )::numeric(18, 2)
            as refund_amount,

        coalesce(
            payment_daily.valued_refund_amount_eur,
            0
        )::numeric(18, 2)
            as valued_refund_amount_eur,

        coalesce(
            payment_daily.chargeback_amount,
            0
        )::numeric(18, 2)
            as chargeback_amount,

        coalesce(
            payment_daily.valued_chargeback_amount_eur,
            0
        )::numeric(18, 2)
            as valued_chargeback_amount_eur,

        coalesce(
            payment_daily.net_payment_amount,
            0
        )::numeric(18, 2)
            as net_payment_amount,

        coalesce(
            payment_daily.valued_net_payment_amount_eur,
            0
        )::numeric(18, 2)
            as valued_net_payment_amount_eur,

        coalesce(
            payment_daily.reconciled_capture_count,
            0
        )::integer
            as reconciled_capture_count,

        coalesce(
            payment_daily.pending_capture_count,
            0
        )::integer
            as pending_capture_count,

        coalesce(
            payment_daily.open_break_capture_count,
            0
        )::integer
            as open_break_capture_count,

        coalesce(
            payment_daily.excluded_capture_count,
            0
        )::integer
            as excluded_capture_count,

        coalesce(
            payment_daily.reconciled_capture_amount_eur,
            0
        )::numeric(18, 2)
            as reconciled_capture_amount_eur,

        coalesce(
            payment_daily.pending_capture_amount_eur,
            0
        )::numeric(18, 2)
            as pending_capture_amount_eur,

        coalesce(
            payment_daily.open_break_capture_amount_eur,
            0
        )::numeric(18, 2)
            as open_break_capture_amount_eur,

        coalesce(
            payment_daily.excluded_capture_amount_eur,
            0
        )::numeric(18, 2)
            as excluded_capture_amount_eur,

        payment_daily.amount_reconciliation_rate,

        coalesce(
            exception_daily.exception_count,
            0
        )::integer
            as exception_count,

        coalesce(
            exception_daily.pending_exception_count,
            0
        )::integer
            as pending_exception_count,

        coalesce(
            exception_daily.open_break_exception_count,
            0
        )::integer
            as open_break_exception_count,

        coalesce(
            exception_daily.resolved_exception_count,
            0
        )::integer
            as resolved_exception_count,

        coalesce(
            exception_daily.critical_exception_count,
            0
        )::integer
            as critical_exception_count,

        coalesce(
            exception_daily.warning_exception_count,
            0
        )::integer
            as warning_exception_count,

        coalesce(
            exception_daily.info_exception_count,
            0
        )::integer
            as info_exception_count,

        coalesce(
            exception_daily.gross_exception_amount_eur,
            0
        )::numeric(18, 2)
            as gross_exception_amount_eur,

        coalesce(
            exception_daily.open_break_exception_amount_eur,
            0
        )::numeric(18, 2)
            as open_break_exception_amount_eur,

        coalesce(
            exception_daily.pending_exception_amount_eur,
            0
        )::numeric(18, 2)
            as pending_exception_amount_eur

    from daily_keys

    left join products
        on daily_keys.product_id
        = products.product_id

    left join invoice_daily
        on daily_keys.business_date
        = invoice_daily.business_date

        and daily_keys.product_id
        is not distinct from invoice_daily.product_id

        and daily_keys.currency
        = invoice_daily.currency

    left join payment_daily
        on daily_keys.business_date
        = payment_daily.business_date

        and daily_keys.product_id
        is not distinct from payment_daily.product_id

        and daily_keys.currency
        = payment_daily.currency

    left join exception_daily
        on daily_keys.business_date
        = exception_daily.business_date

        and daily_keys.product_id
        is not distinct from exception_daily.product_id

        and daily_keys.currency
        = exception_daily.currency

)

select *
from final