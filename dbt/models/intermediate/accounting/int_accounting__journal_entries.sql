with journal_lines as (

    select *
    from {{ ref('stg_accounting__journal_lines') }}

),

aggregated as (

    select
        journal_entry_id,

        count(*)::integer
            as journal_line_count,

        count(*) filter (
            where debit_eur_amount > 0
        )::integer
            as debit_line_count,

        count(*) filter (
            where credit_eur_amount > 0
        )::integer
            as credit_line_count,

        count(
            distinct posting_date
        )::integer
            as posting_date_count,

        case
            when count(
                distinct posting_date
            ) = 1
                then min(posting_date)
        end as posting_date,

        count(
            distinct source_system
        )::integer
            as source_system_count,

        case
            when count(
                distinct source_system
            ) = 1
                then min(source_system)
        end as source_system,

        count(
            distinct source_reference_type
        )::integer
            as source_reference_type_count,

        case
            when count(
                distinct source_reference_type
            ) = 1
                then min(source_reference_type)
        end as source_reference_type,

        count(
            distinct source_reference
        )::integer
            as source_reference_count,

        case
            when count(
                distinct source_reference
            ) = 1
                then min(source_reference)
        end as source_reference,

        count(
            distinct journal_status
        )::integer
            as journal_status_count,

        case
            when count(
                distinct journal_status
            ) = 1
                then min(journal_status)
        end as journal_status,

        coalesce(
            sum(debit_eur_amount),
            0
        )::numeric(18, 2)
            as total_debit_eur_amount,

        coalesce(
            sum(credit_eur_amount),
            0
        )::numeric(18, 2)
            as total_credit_eur_amount,

        coalesce(
            sum(debit_eur_amount) filter (
                where account_code = '1100'
            ),
            0
        )::numeric(18, 2)
            as bank_debit_eur_amount,

        coalesce(
            sum(debit_eur_amount) filter (
                where account_code = '1200'
            ),
            0
        )::numeric(18, 2)
            as psp_clearing_debit_eur_amount,

        coalesce(
            sum(credit_eur_amount) filter (
                where account_code = '1200'
            ),
            0
        )::numeric(18, 2)
            as psp_clearing_credit_eur_amount,

        coalesce(
            sum(credit_eur_amount) filter (
                where account_code = '4000'
            ),
            0
        )::numeric(18, 2)
            as sales_clearing_credit_eur_amount,

        coalesce(
            sum(debit_eur_amount) filter (
                where account_code = '6100'
            ),
            0
        )::numeric(18, 2)
            as payment_processing_fee_debit_eur_amount,

        coalesce(
            sum(debit_eur_amount) filter (
                where account_code = '6200'
            ),
            0
        )::numeric(18, 2)
            as chargeback_loss_debit_eur_amount,

        coalesce(
            sum(debit_eur_amount) filter (
                where account_code = '6300'
            ),
            0
        )::numeric(18, 2)
            as customer_refund_debit_eur_amount,

        min(created_at)
            as first_created_at,

        max(created_at)
            as last_created_at,

        max(_loaded_at)
            as _loaded_at,

        count(
            distinct _batch_id
        )::integer
            as batch_id_count,

        case
            when count(
                distinct _batch_id
            ) = 1
                then min(_batch_id)
        end as _batch_id

    from journal_lines

    group by journal_entry_id

),

final as (

    select
        *,

        (
            total_debit_eur_amount
            - total_credit_eur_amount
        )::numeric(18, 2)
            as journal_balance_difference_eur

    from aggregated

)

select *
from final