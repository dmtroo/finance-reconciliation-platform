with settlements as (

    select *
    from {{ ref('stg_psp__settlements') }}

),

accounting_references as (

    select *
    from {{ ref('int_accounting__source_reference_summary') }}

    where source_reference_type = 'SETTLEMENT'

),

combined as (

    select
        settlements.settlement_id,

        settlements.settlement_date,
        settlements.settlement_currency,

        settlements.gross_amount,
        settlements.fee_amount,
        settlements.net_payout_amount,

        settlements.settlement_status,
        settlements.bank_reference,

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
                    - settlements.settlement_date
                )::integer
        end as accounting_posting_delay_days,

        accounting_references.posted_total_debit_eur_amount,
        accounting_references.posted_total_credit_eur_amount,

        accounting_references.posted_journal_balance_difference_eur,

        coalesce(
            accounting_references.posted_bank_debit_eur_amount,
            0
        )::numeric(18, 2)
            as ledger_bank_debit_eur_amount,

        coalesce(
            accounting_references.posted_processing_fee_debit_eur_amount,
            0
        )::numeric(18, 2)
            as ledger_fee_debit_eur_amount,

        coalesce(
            accounting_references.posted_psp_clearing_credit_eur_amount,
            0
        )::numeric(18, 2)
            as ledger_psp_clearing_credit_eur_amount,

        (
            coalesce(
                accounting_references.posted_bank_debit_eur_amount,
                0
            )
            - settlements.net_payout_amount
        )::numeric(18, 2)
            as ledger_bank_minus_expected_amount_eur,

        (
            coalesce(
                accounting_references.posted_processing_fee_debit_eur_amount,
                0
            )
            - settlements.fee_amount
        )::numeric(18, 2)
            as ledger_fee_minus_expected_amount_eur,

        (
            coalesce(
                accounting_references.posted_psp_clearing_credit_eur_amount,
                0
            )
            - settlements.gross_amount
        )::numeric(18, 2)
            as ledger_clearing_minus_expected_amount_eur,

        settlements.created_at,

        settlements._loaded_at,
        settlements._batch_id

    from settlements

    left join accounting_references
        on settlements.settlement_id
        = accounting_references.source_reference

)

select *
from combined