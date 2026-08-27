with financial_events as (

    select *
    from {{ ref('int_financial_events__with_reference_fx') }}

),

accounting_references as (

    select *
    from {{ ref('int_accounting__source_reference_summary') }}

    where source_reference_type = 'FINANCIAL_EVENT'

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

        financial_events.event_amount_eur,
        financial_events.signed_event_amount_eur,

        coalesce(
            accounting_references.journal_entry_match_count,
            0
        )::integer
            as journal_entry_match_count,

        coalesce(
            accounting_references.posted_journal_entry_count,
            0
        )::integer
            as posted_journal_entry_count,

        accounting_references.posted_journal_entry_id,
        accounting_references.posted_posting_date,

        case
            when accounting_references.posted_posting_date is not null
                then (
                    accounting_references.posted_posting_date
                    - financial_events.event_date
                )::integer
        end as accounting_posting_delay_days,

        accounting_references.posted_total_debit_eur_amount,
        accounting_references.posted_total_credit_eur_amount,

        accounting_references.posted_journal_balance_difference_eur,

        case financial_events.event_type
            when 'CAPTURE'
                then '1200'
            when 'REFUND'
                then '6300'
            when 'CHARGEBACK'
                then '6200'
        end as expected_debit_account_code,

        case financial_events.event_type
            when 'CAPTURE'
                then '4000'
            when 'REFUND'
                then '1200'
            when 'CHARGEBACK'
                then '1200'
        end as expected_credit_account_code,

        case financial_events.event_type
            when 'CAPTURE'
                then accounting_references
                    .posted_psp_clearing_debit_eur_amount

            when 'REFUND'
                then accounting_references
                    .posted_customer_refund_debit_eur_amount

            when 'CHARGEBACK'
                then accounting_references
                    .posted_chargeback_loss_debit_eur_amount
        end::numeric(18, 2)
            as ledger_expected_debit_eur_amount,

        case financial_events.event_type
            when 'CAPTURE'
                then accounting_references
                    .posted_sales_clearing_credit_eur_amount

            when 'REFUND'
                then accounting_references
                    .posted_psp_clearing_credit_eur_amount

            when 'CHARGEBACK'
                then accounting_references
                    .posted_psp_clearing_credit_eur_amount
        end::numeric(18, 2)
            as ledger_expected_credit_eur_amount,

        case
            when financial_events.event_amount_eur is not null
                then (
                    coalesce(
                        case financial_events.event_type
                            when 'CAPTURE'
                                then accounting_references
                                    .posted_psp_clearing_debit_eur_amount

                            when 'REFUND'
                                then accounting_references
                                    .posted_customer_refund_debit_eur_amount

                            when 'CHARGEBACK'
                                then accounting_references
                                    .posted_chargeback_loss_debit_eur_amount
                        end,
                        0
                    )
                    - financial_events.event_amount_eur
                )::numeric(18, 2)
        end as ledger_debit_minus_expected_amount_eur,

        case
            when financial_events.event_amount_eur is not null
                then (
                    coalesce(
                        case financial_events.event_type
                            when 'CAPTURE'
                                then accounting_references
                                    .posted_sales_clearing_credit_eur_amount

                            when 'REFUND'
                                then accounting_references
                                    .posted_psp_clearing_credit_eur_amount

                            when 'CHARGEBACK'
                                then accounting_references
                                    .posted_psp_clearing_credit_eur_amount
                        end,
                        0
                    )
                    - financial_events.event_amount_eur
                )::numeric(18, 2)
        end as ledger_credit_minus_expected_amount_eur,

        financial_events.provider_transaction_id,

        financial_events._loaded_at,
        financial_events._batch_id

    from financial_events

    left join accounting_references
        on financial_events.financial_event_id
        = accounting_references.source_reference

)

select *
from combined