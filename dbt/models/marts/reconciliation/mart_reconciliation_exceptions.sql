with parameters as (

    select
        '{{ var("reconciliation_as_of_date") }}'::date
            as as_of_date

),

invoice_summary as (

    select *
    from {{ ref('int_invoices__payment_summary') }}

),

products as (

    select *
    from {{ ref('stg_billing__products') }}

),

invoice_context as (

    select
        invoice_summary.*,

        products.product_name,
        products.product_family,

        (
            products.product_id is not null
        ) as is_product_mapped

    from invoice_summary

    left join products
        on invoice_summary.product_id
        = products.product_id

),

financial_events as (

    select *
    from {{ ref('int_financial_events__with_reference_fx') }}

),

event_context as (

    select
        financial_events.*,

        invoice_context.product_id,
        invoice_context.product_name,
        invoice_context.product_family

    from financial_events

    left join invoice_context
        on financial_events.invoice_id
        = invoice_context.invoice_id

),

captures as (

    select *
    from {{ ref('int_captures__lifecycle') }}

),

capture_context as (

    select
        captures.*,

        invoice_context.product_id,
        invoice_context.product_name,
        invoice_context.product_family

    from captures

    left join invoice_context
        on captures.invoice_id
        = invoice_context.invoice_id

),

payment_fact as (

    select *
    from {{ ref('fct_payment_reconciliation') }}

),

settlement_mapping as (

    select *
    from {{ ref('int_financial_events__settlement_mapping') }}

),

settlement_event_context as (

    select
        settlement_mapping.*,

        invoice_context.product_id,
        invoice_context.product_name,
        invoice_context.product_family

    from settlement_mapping

    left join invoice_context
        on settlement_mapping.invoice_id
        = invoice_context.invoice_id

),

settlement_fact as (

    select *
    from {{ ref('fct_settlement_reconciliation') }}

),

event_accounting as (

    select *
    from {{ ref('int_financial_events__accounting_context') }}

),

event_accounting_context as (

    select
        event_accounting.*,

        invoice_context.product_id,
        invoice_context.product_name,
        invoice_context.product_family

    from event_accounting

    left join invoice_context
        on event_accounting.invoice_id
        = invoice_context.invoice_id

),

missing_capture as (

    select
        'MISSING_CAPTURE'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'INVOICE'::text
            as entity_type,

        invoices.invoice_id::text
            as entity_id,

        invoices.invoice_date
            as business_date,

        parameters.as_of_date,

        invoices.product_id,
        invoices.product_name,
        invoices.product_family,

        invoices.invoice_currency
            as currency,

        case
            when invoices.invoice_currency = 'EUR'
                then abs(
                    invoices.total_amount
                )::numeric(18, 2)
        end as exception_amount_eur,

        null::integer
            as age_days,

        case
            when invoices.invoice_currency = 'EUR'
                then 0::numeric(18, 2)
        end as observed_amount_eur,

        case
            when invoices.invoice_currency = 'EUR'
                then invoices.total_amount::numeric(18, 2)
        end as expected_amount_eur,

        case
            when invoices.invoice_currency = 'EUR'
                then (
                    0 - invoices.total_amount
                )::numeric(18, 2)
        end as difference_amount_eur,

        'invoice_payment_summary'::text
            as control_source,

        invoices._loaded_at,
        invoices._batch_id

    from invoice_context as invoices

    cross join parameters

    where
        invoices.invoice_date
            <= parameters.as_of_date

        and invoices.capture_count = 0

        and (
            invoices.invoice_status = 'PAID'
            or invoices.successful_attempt_count > 0
        )

),

capture_amount_mismatch as (

    select
        'CAPTURE_AMOUNT_MISMATCH'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'CAPTURE'::text
            as entity_type,

        payment.capture_id::text
            as entity_id,

        payment.capture_date
            as business_date,

        parameters.as_of_date,

        payment.product_id,
        payment.product_name,
        payment.product_family,

        payment.capture_currency
            as currency,

        case
            when
                payment.capture_currency_matches_invoice is true
                and payment.reference_fx_rate is not null
                then abs(
                    payment.capture_minus_invoice_amount
                    * payment.reference_fx_rate
                )::numeric(18, 2)
        end as exception_amount_eur,

        null::integer
            as age_days,

        payment.capture_amount_eur
            as observed_amount_eur,

        case
            when
                payment.capture_currency_matches_invoice is true
                and payment.reference_fx_rate is not null
                then (
                    payment.invoice_total_amount
                    * payment.reference_fx_rate
                )::numeric(18, 2)
        end as expected_amount_eur,

        case
            when
                payment.capture_currency_matches_invoice is true
                and payment.reference_fx_rate is not null
                then (
                    payment.capture_minus_invoice_amount
                    * payment.reference_fx_rate
                )::numeric(18, 2)
        end as difference_amount_eur,

        'payment_reconciliation_fact'::text
            as control_source,

        payment._loaded_at,
        payment._batch_id

    from payment_fact as payment

    cross join parameters

    where
        payment.capture_date
            <= parameters.as_of_date

        and payment.capture_amount_matches_invoice
            is false

),

duplicate_capture as (

    select
        'DUPLICATE_CAPTURE'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'INVOICE'::text
            as entity_type,

        invoices.invoice_id::text
            as entity_id,

        invoices.invoice_date
            as business_date,

        parameters.as_of_date,

        invoices.product_id,
        invoices.product_name,
        invoices.product_family,

        invoices.invoice_currency
            as currency,

        case
            when invoices.capture_amount_eur is not null
                then abs(
                    invoices.capture_amount_eur
                )::numeric(18, 2)

            when invoices.invoice_currency = 'EUR'
                then abs(
                    invoices.capture_amount
                )::numeric(18, 2)
        end as exception_amount_eur,

        null::integer
            as age_days,

        case
            when invoices.invoice_currency = 'EUR'
                then invoices.capture_amount::numeric(18, 2)
        end as observed_amount_eur,

        case
            when invoices.invoice_currency = 'EUR'
                then invoices.total_amount::numeric(18, 2)
        end as expected_amount_eur,

        case
            when invoices.invoice_currency = 'EUR'
                then (
                    invoices.capture_amount
                    - invoices.total_amount
                )::numeric(18, 2)
        end as difference_amount_eur,

        'invoice_payment_summary'::text
            as control_source,

        invoices._loaded_at,
        invoices._batch_id

    from invoice_context as invoices

    cross join parameters

    where
        invoices.invoice_date
            <= parameters.as_of_date

        and invoices.capture_count > 1

),

invalid_refund as (

    select
        'INVALID_REFUND'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'FINANCIAL_EVENT'::text
            as entity_type,

        events.financial_event_id::text
            as entity_id,

        events.event_date
            as business_date,

        parameters.as_of_date,

        events.product_id,
        events.product_name,
        events.product_family,

        events.currency,

        abs(
            events.event_amount_eur
        )::numeric(18, 2)
            as exception_amount_eur,

        null::integer
            as age_days,

        events.event_amount_eur::numeric(18, 2)
            as observed_amount_eur,

        0::numeric(18, 2)
            as expected_amount_eur,

        events.event_amount_eur::numeric(18, 2)
            as difference_amount_eur,

        'financial_event_reference'::text
            as control_source,

        events._loaded_at,
        events._batch_id

    from event_context as events

    cross join parameters

    left join captures
        on events.original_capture_id
        = captures.capture_id

    where
        events.event_date
            <= parameters.as_of_date

        and events.event_type = 'REFUND'

        and (
            events.original_capture_id is null
            or captures.capture_id is null
        )

),

over_refund as (

    select
        'OVER_REFUND'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'CAPTURE'::text
            as entity_type,

        captures.capture_id::text
            as entity_id,

        captures.capture_date
            as business_date,

        parameters.as_of_date,

        captures.product_id,
        captures.product_name,
        captures.product_family,

        captures.currency,

        case
            when
                captures.refund_amount_eur is not null
                and captures.capture_amount_eur is not null
                then abs(
                    captures.refund_amount_eur
                    - captures.capture_amount_eur
                )::numeric(18, 2)
        end as exception_amount_eur,

        null::integer
            as age_days,

        captures.refund_amount_eur
            as observed_amount_eur,

        captures.capture_amount_eur
            as expected_amount_eur,

        case
            when
                captures.refund_amount_eur is not null
                and captures.capture_amount_eur is not null
                then (
                    captures.refund_amount_eur
                    - captures.capture_amount_eur
                )::numeric(18, 2)
        end as difference_amount_eur,

        'capture_lifecycle'::text
            as control_source,

        captures._loaded_at,
        captures._batch_id

    from capture_context as captures

    cross join parameters

    where
        captures.capture_date
            <= parameters.as_of_date

        and captures.refund_amount
            > captures.capture_amount

),

missing_settlement as (

    select
        'MISSING_SETTLEMENT'::text
            as exception_code,

        case
            when (
                parameters.as_of_date
                - events.event_date
            ) <= {{ var('reconciliation_settlement_pending_days') }}
                then 'PENDING'
            else 'OPEN_BREAK'
        end::text as exception_status,

        case
            when (
                parameters.as_of_date
                - events.event_date
            ) <= {{ var('reconciliation_settlement_pending_days') }}
                then 'INFO'
            else 'CRITICAL'
        end::text as severity,

        'FINANCIAL_EVENT'::text
            as entity_type,

        events.financial_event_id::text
            as entity_id,

        events.event_date
            as business_date,

        parameters.as_of_date,

        events.product_id,
        events.product_name,
        events.product_family,

        events.currency,

        abs(
            events.event_amount_eur
        )::numeric(18, 2)
            as exception_amount_eur,

        (
            parameters.as_of_date
            - events.event_date
        )::integer
            as age_days,

        null::numeric(18, 2)
            as observed_amount_eur,

        null::numeric(18, 2)
            as expected_amount_eur,

        null::numeric(18, 2)
            as difference_amount_eur,

        'financial_event_settlement_mapping'::text
            as control_source,

        events._loaded_at,
        events._batch_id

    from settlement_event_context as events

    cross join parameters

    where
        events.event_date
            <= parameters.as_of_date

        and events.settlement_count = 0

),

late_settlement as (

    select
        'LATE_SETTLEMENT'::text
            as exception_code,

        'RESOLVED'::text
            as exception_status,

        'WARNING'::text
            as severity,

        'FINANCIAL_EVENT'::text
            as entity_type,

        events.financial_event_id::text
            as entity_id,

        events.event_date
            as business_date,

        parameters.as_of_date,

        events.product_id,
        events.product_name,
        events.product_family,

        events.currency,

        abs(
            events.event_amount_eur
        )::numeric(18, 2)
            as exception_amount_eur,

        events.settlement_delay_days::integer
            as age_days,

        null::numeric(18, 2)
            as observed_amount_eur,

        null::numeric(18, 2)
            as expected_amount_eur,

        null::numeric(18, 2)
            as difference_amount_eur,

        'financial_event_settlement_mapping'::text
            as control_source,

        events._loaded_at,
        events._batch_id

    from settlement_event_context as events

    cross join parameters

    where
        events.settlement_count = 1

        and events.settlement_date
            <= parameters.as_of_date

        and events.settlement_delay_days
            > {{ var('reconciliation_settlement_pending_days') }}

),

settlement_total_mismatch as (

    select
        'SETTLEMENT_TOTAL_MISMATCH'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'SETTLEMENT'::text
            as entity_type,

        settlements.settlement_id::text
            as entity_id,

        settlements.settlement_date
            as business_date,

        parameters.as_of_date,

        null::text as product_id,
        null::text as product_name,
        null::text as product_family,

        settlements.settlement_currency
            as currency,

        greatest(
            abs(
                settlements.gross_header_minus_items_amount
            ),
            abs(
                settlements.fee_header_minus_items_amount
            ),
            abs(
                settlements.net_header_minus_items_amount
            )
        )::numeric(18, 2)
            as exception_amount_eur,

        null::integer
            as age_days,

        null::numeric(18, 2)
            as observed_amount_eur,

        null::numeric(18, 2)
            as expected_amount_eur,

        null::numeric(18, 2)
            as difference_amount_eur,

        'settlement_reconciliation_fact'::text
            as control_source,

        settlements._loaded_at,
        settlements._batch_id

    from settlement_fact as settlements

    cross join parameters

    where
        settlements.settlement_date
            <= parameters.as_of_date

        and settlements.is_settlement_total_within_tolerance
            is false

),

missing_bank_receipt as (

    select
        'MISSING_BANK_RECEIPT'::text
            as exception_code,

        case
            when (
                parameters.as_of_date
                - settlements.settlement_date
            ) <= {{ var('reconciliation_bank_pending_days') }}
                then 'PENDING'
            else 'OPEN_BREAK'
        end::text as exception_status,

        case
            when (
                parameters.as_of_date
                - settlements.settlement_date
            ) <= {{ var('reconciliation_bank_pending_days') }}
                then 'INFO'
            else 'CRITICAL'
        end::text as severity,

        'SETTLEMENT'::text
            as entity_type,

        settlements.settlement_id::text
            as entity_id,

        settlements.settlement_date
            as business_date,

        parameters.as_of_date,

        null::text as product_id,
        null::text as product_name,
        null::text as product_family,

        settlements.settlement_currency
            as currency,

        abs(
            settlements.net_payout_amount
        )::numeric(18, 2)
            as exception_amount_eur,

        (
            parameters.as_of_date
            - settlements.settlement_date
        )::integer
            as age_days,

        null::numeric(18, 2)
            as observed_amount_eur,

        settlements.net_payout_amount
            as expected_amount_eur,

        null::numeric(18, 2)
            as difference_amount_eur,

        'settlement_reconciliation_fact'::text
            as control_source,

        settlements._loaded_at,
        settlements._batch_id

    from settlement_fact as settlements

    cross join parameters

    where
        settlements.settlement_date
            <= parameters.as_of_date

        and settlements.settlement_status = 'PAID'

        and settlements.eligible_bank_receipt_count = 0

),

bank_amount_mismatch as (

    select
        'BANK_AMOUNT_MISMATCH'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'SETTLEMENT'::text
            as entity_type,

        settlements.settlement_id::text
            as entity_id,

        settlements.settlement_date
            as business_date,

        parameters.as_of_date,

        null::text as product_id,
        null::text as product_name,
        null::text as product_family,

        settlements.settlement_currency
            as currency,

        abs(
            settlements.bank_minus_settlement_amount
        )::numeric(18, 2)
            as exception_amount_eur,

        settlements.bank_delay_days::integer
            as age_days,

        settlements.bank_amount
            as observed_amount_eur,

        settlements.net_payout_amount
            as expected_amount_eur,

        settlements.bank_minus_settlement_amount
            as difference_amount_eur,

        'settlement_reconciliation_fact'::text
            as control_source,

        settlements._loaded_at,
        settlements._batch_id

    from settlement_fact as settlements

    cross join parameters

    where
        settlements.settlement_date
            <= parameters.as_of_date

        and settlements.eligible_bank_receipt_count = 1

        and settlements.is_bank_amount_within_tolerance
            is false

),

missing_event_ledger_posting as (

    select
        'MISSING_LEDGER_POSTING'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'FINANCIAL_EVENT'::text
            as entity_type,

        events.financial_event_id::text
            as entity_id,

        events.event_date
            as business_date,

        parameters.as_of_date,

        events.product_id,
        events.product_name,
        events.product_family,

        events.currency,

        abs(
            events.event_amount_eur
        )::numeric(18, 2)
            as exception_amount_eur,

        null::integer
            as age_days,

        null::numeric(18, 2)
            as observed_amount_eur,

        events.event_amount_eur
            as expected_amount_eur,

        null::numeric(18, 2)
            as difference_amount_eur,

        'financial_event_accounting_context'::text
            as control_source,

        events._loaded_at,
        events._batch_id

    from event_accounting_context as events

    cross join parameters

    where
        events.event_date
            <= parameters.as_of_date

        and events.posted_journal_entry_count = 0

),

event_ledger_amount_mismatch as (

    select
        'LEDGER_AMOUNT_MISMATCH'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'FINANCIAL_EVENT'::text
            as entity_type,

        events.financial_event_id::text
            as entity_id,

        events.event_date
            as business_date,

        parameters.as_of_date,

        events.product_id,
        events.product_name,
        events.product_family,

        events.currency,

        greatest(
            abs(
                events.ledger_debit_minus_expected_amount_eur
            ),
            abs(
                events.ledger_credit_minus_expected_amount_eur
            )
        )::numeric(18, 2)
            as exception_amount_eur,

        null::integer
            as age_days,

        null::numeric(18, 2)
            as observed_amount_eur,

        events.event_amount_eur
            as expected_amount_eur,

        null::numeric(18, 2)
            as difference_amount_eur,

        'financial_event_accounting_context'::text
            as control_source,

        events._loaded_at,
        events._batch_id

    from event_accounting_context as events

    cross join parameters

    where
        events.event_date
            <= parameters.as_of_date

        and events.posted_journal_entry_count = 1

        and (
            abs(
                events.ledger_debit_minus_expected_amount_eur
            ) > {{ var('reconciliation_amount_tolerance_eur') }}

            or

            abs(
                events.ledger_credit_minus_expected_amount_eur
            ) > {{ var('reconciliation_amount_tolerance_eur') }}
        )

),

unbalanced_event_journal as (

    select
        'UNBALANCED_JOURNAL'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'FINANCIAL_EVENT'::text
            as entity_type,

        events.financial_event_id::text
            as entity_id,

        events.event_date
            as business_date,

        parameters.as_of_date,

        events.product_id,
        events.product_name,
        events.product_family,

        events.currency,

        abs(
            events.posted_journal_balance_difference_eur
        )::numeric(18, 2)
            as exception_amount_eur,

        null::integer
            as age_days,

        null::numeric(18, 2)
            as observed_amount_eur,

        null::numeric(18, 2)
            as expected_amount_eur,

        events.posted_journal_balance_difference_eur
            as difference_amount_eur,

        'financial_event_accounting_context'::text
            as control_source,

        events._loaded_at,
        events._batch_id

    from event_accounting_context as events

    cross join parameters

    where
        events.event_date
            <= parameters.as_of_date

        and events.posted_journal_entry_count = 1

        and abs(
            events.posted_journal_balance_difference_eur
        ) > {{ var('reconciliation_amount_tolerance_eur') }}

),

missing_settlement_ledger_posting as (

    select
        'MISSING_LEDGER_POSTING'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'SETTLEMENT'::text
            as entity_type,

        settlements.settlement_id::text
            as entity_id,

        settlements.settlement_date
            as business_date,

        parameters.as_of_date,

        null::text as product_id,
        null::text as product_name,
        null::text as product_family,

        settlements.settlement_currency
            as currency,

        abs(
            settlements.gross_amount
        )::numeric(18, 2)
            as exception_amount_eur,

        null::integer
            as age_days,

        null::numeric(18, 2)
            as observed_amount_eur,

        settlements.gross_amount
            as expected_amount_eur,

        null::numeric(18, 2)
            as difference_amount_eur,

        'settlement_reconciliation_fact'::text
            as control_source,

        settlements._loaded_at,
        settlements._batch_id

    from settlement_fact as settlements

    cross join parameters

    where
        settlements.settlement_date
            <= parameters.as_of_date

        and settlements.posted_journal_entry_count = 0

),

settlement_ledger_amount_mismatch as (

    select
        'LEDGER_AMOUNT_MISMATCH'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'SETTLEMENT'::text
            as entity_type,

        settlements.settlement_id::text
            as entity_id,

        settlements.settlement_date
            as business_date,

        parameters.as_of_date,

        null::text as product_id,
        null::text as product_name,
        null::text as product_family,

        settlements.settlement_currency
            as currency,

        greatest(
            abs(
                settlements.ledger_bank_minus_expected_amount_eur
            ),
            abs(
                settlements.ledger_fee_minus_expected_amount_eur
            ),
            abs(
                settlements.ledger_clearing_minus_expected_amount_eur
            )
        )::numeric(18, 2)
            as exception_amount_eur,

        null::integer
            as age_days,

        null::numeric(18, 2)
            as observed_amount_eur,

        null::numeric(18, 2)
            as expected_amount_eur,

        null::numeric(18, 2)
            as difference_amount_eur,

        'settlement_reconciliation_fact'::text
            as control_source,

        settlements._loaded_at,
        settlements._batch_id

    from settlement_fact as settlements

    cross join parameters

    where
        settlements.settlement_date
            <= parameters.as_of_date

        and settlements.posted_journal_entry_count = 1

        and settlements.is_ledger_amount_within_tolerance
            is false

),

unbalanced_settlement_journal as (

    select
        'UNBALANCED_JOURNAL'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'SETTLEMENT'::text
            as entity_type,

        settlements.settlement_id::text
            as entity_id,

        settlements.settlement_date
            as business_date,

        parameters.as_of_date,

        null::text as product_id,
        null::text as product_name,
        null::text as product_family,

        settlements.settlement_currency
            as currency,

        abs(
            settlements.posted_journal_balance_difference_eur
        )::numeric(18, 2)
            as exception_amount_eur,

        null::integer
            as age_days,

        null::numeric(18, 2)
            as observed_amount_eur,

        null::numeric(18, 2)
            as expected_amount_eur,

        settlements.posted_journal_balance_difference_eur
            as difference_amount_eur,

        'settlement_reconciliation_fact'::text
            as control_source,

        settlements._loaded_at,
        settlements._batch_id

    from settlement_fact as settlements

    cross join parameters

    where
        settlements.settlement_date
            <= parameters.as_of_date

        and settlements.posted_journal_entry_count = 1

        and settlements.is_journal_balanced_within_tolerance
            is false

),

missing_fx_rate as (

    select
        'MISSING_FX_RATE'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'CRITICAL'::text
            as severity,

        'FINANCIAL_EVENT'::text
            as entity_type,

        events.financial_event_id::text
            as entity_id,

        events.event_date
            as business_date,

        parameters.as_of_date,

        events.product_id,
        events.product_name,
        events.product_family,

        events.currency,

        null::numeric(18, 2)
            as exception_amount_eur,

        null::integer
            as age_days,

        null::numeric(18, 2)
            as observed_amount_eur,

        null::numeric(18, 2)
            as expected_amount_eur,

        null::numeric(18, 2)
            as difference_amount_eur,

        'reference_fx_enrichment'::text
            as control_source,

        events._loaded_at,
        events._batch_id

    from event_context as events

    cross join parameters

    where
        events.event_date
            <= parameters.as_of_date

        and events.reference_fx_rate is null

),

fx_rate_outlier as (

    select
        'FX_RATE_OUTLIER'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'WARNING'::text
            as severity,

        'FINANCIAL_EVENT'::text
            as entity_type,

        events.financial_event_id::text
            as entity_id,

        events.event_date
            as business_date,

        parameters.as_of_date,

        events.product_id,
        events.product_name,
        events.product_family,

        events.currency,

        case
            when events.event_amount_eur is not null
                then abs(
                    events.event_amount_eur
                    * events.psp_fx_rate_variance_ratio
                )::numeric(18, 2)
        end as exception_amount_eur,

        null::integer
            as age_days,

        null::numeric(18, 2)
            as observed_amount_eur,

        null::numeric(18, 2)
            as expected_amount_eur,

        null::numeric(18, 2)
            as difference_amount_eur,

        'financial_event_settlement_mapping'::text
            as control_source,

        events._loaded_at,
        events._batch_id

    from settlement_event_context as events

    cross join parameters

    where
        events.event_date
            <= parameters.as_of_date

        and events.psp_fx_rate_variance_ratio
            is not null

        and abs(
            events.psp_fx_rate_variance_ratio
        ) > {{ var('reconciliation_fx_outlier_ratio') }}

),

unmapped_product as (

    select
        'UNMAPPED_PRODUCT'::text
            as exception_code,

        'OPEN_BREAK'::text
            as exception_status,

        'WARNING'::text
            as severity,

        'INVOICE'::text
            as entity_type,

        invoices.invoice_id::text
            as entity_id,

        invoices.invoice_date
            as business_date,

        parameters.as_of_date,

        invoices.product_id,

        null::text
            as product_name,

        null::text
            as product_family,

        invoices.invoice_currency
            as currency,

        case
            when invoices.capture_amount_eur is not null
                then abs(
                    invoices.capture_amount_eur
                )::numeric(18, 2)

            when invoices.invoice_currency = 'EUR'
                then abs(
                    invoices.total_amount
                )::numeric(18, 2)
        end as exception_amount_eur,

        null::integer
            as age_days,

        null::numeric(18, 2)
            as observed_amount_eur,

        null::numeric(18, 2)
            as expected_amount_eur,

        null::numeric(18, 2)
            as difference_amount_eur,

        'invoice_product_mapping'::text
            as control_source,

        invoices._loaded_at,
        invoices._batch_id

    from invoice_context as invoices

    cross join parameters

    where
        invoices.invoice_date
            <= parameters.as_of_date

        and invoices.product_id is not null

        and invoices.is_product_mapped is false

),

all_exceptions as (

    select * from missing_capture

    union all

    select * from capture_amount_mismatch

    union all

    select * from duplicate_capture

    union all

    select * from invalid_refund

    union all

    select * from over_refund

    union all

    select * from missing_settlement

    union all

    select * from late_settlement

    union all

    select * from settlement_total_mismatch

    union all

    select * from missing_bank_receipt

    union all

    select * from bank_amount_mismatch

    union all

    select * from missing_event_ledger_posting

    union all

    select * from event_ledger_amount_mismatch

    union all

    select * from unbalanced_event_journal

    union all

    select * from missing_settlement_ledger_posting

    union all

    select * from settlement_ledger_amount_mismatch

    union all

    select * from unbalanced_settlement_journal

    union all

    select * from missing_fx_rate

    union all

    select * from fx_rate_outlier

    union all

    select * from unmapped_product

),

final as (

    select
        (
            exception_code
            || ':'
            || entity_type
            || ':'
            || entity_id
        )::text as exception_id,

        exception_code,
        exception_status,
        severity,

        entity_type,
        entity_id,

        business_date,
        as_of_date,

        product_id,
        product_name,
        product_family,

        currency,

        exception_amount_eur,

        age_days,

        observed_amount_eur,
        expected_amount_eur,
        difference_amount_eur,

        control_source,

        _loaded_at,
        _batch_id

    from all_exceptions

)

select *
from final