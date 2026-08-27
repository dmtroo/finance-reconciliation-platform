with journal_entries as (

    select *
    from {{ ref('int_accounting__journal_entries') }}

),

valid_references as (

    select *
    from journal_entries

    where
        source_reference_type is not null
        and source_reference is not null

),

aggregated as (

    select
        source_reference_type,
        source_reference,

        count(*)::integer
            as journal_entry_match_count,

        count(*) filter (
            where journal_status = 'POSTED'
        )::integer
            as posted_journal_entry_count,

        case
            when count(*) filter (
                where journal_status = 'POSTED'
            ) = 1
                then min(journal_entry_id) filter (
                    where journal_status = 'POSTED'
                )
        end as posted_journal_entry_id,

        case
            when count(*) filter (
                where journal_status = 'POSTED'
            ) = 1
                then min(posting_date) filter (
                    where journal_status = 'POSTED'
                )
        end as posted_posting_date,

        min(posting_date) filter (
            where journal_status = 'POSTED'
        ) as first_posted_date,

        max(posting_date) filter (
            where journal_status = 'POSTED'
        ) as last_posted_date,

        coalesce(
            sum(total_debit_eur_amount) filter (
                where journal_status = 'POSTED'
            ),
            0
        )::numeric(18, 2)
            as posted_total_debit_eur_amount,

        coalesce(
            sum(total_credit_eur_amount) filter (
                where journal_status = 'POSTED'
            ),
            0
        )::numeric(18, 2)
            as posted_total_credit_eur_amount,

        case
            when count(*) filter (
                where journal_status = 'POSTED'
            ) > 0
                then sum(
                    journal_balance_difference_eur
                ) filter (
                    where journal_status = 'POSTED'
                )::numeric(18, 2)
        end as posted_journal_balance_difference_eur,

        coalesce(
            sum(bank_debit_eur_amount) filter (
                where journal_status = 'POSTED'
            ),
            0
        )::numeric(18, 2)
            as posted_bank_debit_eur_amount,

        coalesce(
            sum(psp_clearing_debit_eur_amount) filter (
                where journal_status = 'POSTED'
            ),
            0
        )::numeric(18, 2)
            as posted_psp_clearing_debit_eur_amount,

        coalesce(
            sum(psp_clearing_credit_eur_amount) filter (
                where journal_status = 'POSTED'
            ),
            0
        )::numeric(18, 2)
            as posted_psp_clearing_credit_eur_amount,

        coalesce(
            sum(sales_clearing_credit_eur_amount) filter (
                where journal_status = 'POSTED'
            ),
            0
        )::numeric(18, 2)
            as posted_sales_clearing_credit_eur_amount,

        coalesce(
            sum(payment_processing_fee_debit_eur_amount) filter (
                where journal_status = 'POSTED'
            ),
            0
        )::numeric(18, 2)
            as posted_processing_fee_debit_eur_amount,

        coalesce(
            sum(chargeback_loss_debit_eur_amount) filter (
                where journal_status = 'POSTED'
            ),
            0
        )::numeric(18, 2)
            as posted_chargeback_loss_debit_eur_amount,

        coalesce(
            sum(customer_refund_debit_eur_amount) filter (
                where journal_status = 'POSTED'
            ),
            0
        )::numeric(18, 2)
            as posted_customer_refund_debit_eur_amount

    from valid_references

    group by
        source_reference_type,
        source_reference

)

select *
from aggregated