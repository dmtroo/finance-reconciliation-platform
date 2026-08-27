with captures as (

    select *
    from {{ ref('int_captures__lifecycle') }}

),

invoice_summary as (

    select *
    from {{ ref('int_invoices__payment_summary') }}

),

settlement_context as (

    select *
    from {{ ref('int_financial_events__settlement_mapping') }}

),

accounting_context as (

    select *
    from {{ ref('int_financial_events__accounting_context') }}

),

products as (

    select *
    from {{ ref('stg_billing__products') }}

),

combined as (

    select
        captures.capture_id,
        captures.payment_attempt_id,
        captures.invoice_id,

        invoice_summary.subscription_id,
        invoice_summary.customer_id,
        invoice_summary.product_id,

        products.product_name,
        products.product_family,

        (
            products.product_id is not null
        ) as is_product_mapped,

        invoice_summary.invoice_date,
        invoice_summary.due_date,
        invoice_summary.invoice_status,

        invoice_summary.invoice_currency,
        invoice_summary.total_amount
            as invoice_total_amount,

        captures.capture_at,
        captures.capture_date,

        captures.currency
            as capture_currency,

        captures.capture_amount,
        captures.capture_amount_eur,

        captures.reference_fx_rate_date,
        captures.reference_fx_rate,
        captures.reference_fx_age_days,

        invoice_summary.capture_count
            as invoice_capture_count,

        case
            when invoice_summary.invoice_id is null
                then null

            else (
                captures.currency
                = invoice_summary.invoice_currency
            )
        end as capture_currency_matches_invoice,

        case
            when
                captures.currency
                = invoice_summary.invoice_currency
                then (
                    captures.capture_amount
                    - invoice_summary.total_amount
                )::numeric(18, 2)
        end as capture_minus_invoice_amount,

        case
            when invoice_summary.invoice_id is null
                then null

            when
                captures.currency
                != invoice_summary.invoice_currency
                then false

            else
                captures.capture_amount
                = invoice_summary.total_amount
        end as capture_amount_matches_invoice,

        captures.refund_event_count,
        captures.refund_amount,
        captures.refund_amount_eur,

        captures.chargeback_event_count,
        captures.chargeback_amount,
        captures.chargeback_amount_eur,

        captures.net_capture_amount,
        captures.net_capture_amount_eur,

        captures.has_refund,
        captures.has_chargeback,

        settlement_context.settlement_item_count,
        settlement_context.settlement_count,
        settlement_context.settlement_id,

        settlement_context.settlement_date,
        settlement_context.settlement_status,
        settlement_context.settlement_delay_days,

        settlement_context.settlement_transaction_amount,
        settlement_context.settlement_gross_eur_amount,
        settlement_context.settlement_fee_eur_amount,
        settlement_context.settlement_net_eur_amount,

        settlement_context.psp_fx_rate,
        settlement_context.psp_fx_rate_variance_ratio,

        case
            when
                settlement_context.psp_fx_rate_variance_ratio
                is null
                then null

            else
                abs(
                    settlement_context.psp_fx_rate_variance_ratio
                )
                > {{ var('reconciliation_fx_outlier_ratio') }}
        end as is_fx_rate_outlier,

        accounting_context.journal_entry_match_count,
        accounting_context.posted_journal_entry_count,
        accounting_context.posted_journal_entry_id,
        accounting_context.posted_posting_date,
        accounting_context.accounting_posting_delay_days,

        accounting_context.expected_debit_account_code,
        accounting_context.expected_credit_account_code,

        accounting_context.ledger_expected_debit_eur_amount,
        accounting_context.ledger_expected_credit_eur_amount,

        accounting_context.ledger_debit_minus_expected_amount_eur,
        accounting_context.ledger_credit_minus_expected_amount_eur,

        accounting_context.posted_journal_balance_difference_eur,

        case
            when
                accounting_context.posted_journal_entry_count != 1
                or captures.capture_amount_eur is null
                then null

            else
                abs(
                    accounting_context
                        .ledger_debit_minus_expected_amount_eur
                )
                    <= {{ var('reconciliation_amount_tolerance_eur') }}

                and

                abs(
                    accounting_context
                        .ledger_credit_minus_expected_amount_eur
                )
                    <= {{ var('reconciliation_amount_tolerance_eur') }}
        end as is_ledger_amount_within_tolerance,

        case
            when
                accounting_context.posted_journal_entry_count != 1
                or accounting_context
                    .posted_journal_balance_difference_eur
                    is null
                then null

            else
                abs(
                    accounting_context
                        .posted_journal_balance_difference_eur
                )
                    <= {{ var('reconciliation_amount_tolerance_eur') }}
        end as is_journal_balanced_within_tolerance,

        captures.provider_transaction_id,

        captures._loaded_at,
        captures._batch_id

    from captures

    left join invoice_summary
        on captures.invoice_id
        = invoice_summary.invoice_id

    left join products
        on invoice_summary.product_id
        = products.product_id

    left join settlement_context
        on captures.capture_id
        = settlement_context.financial_event_id

    left join accounting_context
        on captures.capture_id
        = accounting_context.financial_event_id

)

select *
from combined