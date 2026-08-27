with bank_context as (

    select *
    from {{ ref('int_settlements__bank_context') }}

),

accounting_context as (

    select *
    from {{ ref('int_settlements__accounting_context') }}

),

combined as (

    select
        bank_context.settlement_id,

        bank_context.settlement_date,
        bank_context.settlement_currency,

        bank_context.gross_amount,
        bank_context.fee_amount,
        bank_context.net_payout_amount,

        bank_context.settlement_status,
        bank_context.bank_reference,

        bank_context.settlement_item_count,
        bank_context.settled_financial_event_count,

        bank_context.item_gross_eur_amount,
        bank_context.item_fee_eur_amount,
        bank_context.item_net_eur_amount,

        bank_context.gross_header_minus_items_amount,
        bank_context.fee_header_minus_items_amount,
        bank_context.net_header_minus_items_amount,

        (
            abs(
                bank_context.gross_header_minus_items_amount
            ) <= {{ var('reconciliation_amount_tolerance_eur') }}

            and

            abs(
                bank_context.fee_header_minus_items_amount
            ) <= {{ var('reconciliation_amount_tolerance_eur') }}

            and

            abs(
                bank_context.net_header_minus_items_amount
            ) <= {{ var('reconciliation_amount_tolerance_eur') }}
        ) as is_settlement_total_within_tolerance,

        bank_context.bank_reference_match_count,
        bank_context.eligible_bank_receipt_count,

        bank_context.bank_transaction_id,
        bank_context.bank_booking_date,
        bank_context.bank_value_date,
        bank_context.bank_amount,

        bank_context.bank_delay_days,
        bank_context.bank_minus_settlement_amount,

        case
            when
                bank_context.eligible_bank_receipt_count != 1
                or bank_context.bank_amount is null
                then null

            else
                abs(
                    bank_context.bank_minus_settlement_amount
                ) <= {{ var('reconciliation_amount_tolerance_eur') }}
        end as is_bank_amount_within_tolerance,

        accounting_context.journal_entry_match_count,
        accounting_context.posted_journal_entry_count,

        accounting_context.posted_journal_entry_id,
        accounting_context.posted_posting_date,
        accounting_context.accounting_posting_delay_days,

        accounting_context.posted_total_debit_eur_amount,
        accounting_context.posted_total_credit_eur_amount,

        accounting_context.posted_journal_balance_difference_eur,

        accounting_context.ledger_bank_debit_eur_amount,
        accounting_context.ledger_fee_debit_eur_amount,
        accounting_context.ledger_psp_clearing_credit_eur_amount,

        accounting_context.ledger_bank_minus_expected_amount_eur,
        accounting_context.ledger_fee_minus_expected_amount_eur,
        accounting_context.ledger_clearing_minus_expected_amount_eur,

        case
            when
                accounting_context.posted_journal_entry_count != 1
                then null

            else
                abs(
                    accounting_context
                        .ledger_bank_minus_expected_amount_eur
                ) <= {{ var('reconciliation_amount_tolerance_eur') }}

                and

                abs(
                    accounting_context
                        .ledger_fee_minus_expected_amount_eur
                ) <= {{ var('reconciliation_amount_tolerance_eur') }}

                and

                abs(
                    accounting_context
                        .ledger_clearing_minus_expected_amount_eur
                ) <= {{ var('reconciliation_amount_tolerance_eur') }}
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
                ) <= {{ var('reconciliation_amount_tolerance_eur') }}
        end as is_journal_balanced_within_tolerance,

        bank_context.created_at,

        bank_context._loaded_at,
        bank_context._batch_id

    from bank_context

    left join accounting_context
        on bank_context.settlement_id
        = accounting_context.settlement_id

)

select *
from combined