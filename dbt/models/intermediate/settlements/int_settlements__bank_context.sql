with settlements as (

    select *
    from {{ ref('stg_psp__settlements') }}

),

settlement_items as (

    select *
    from {{ ref('stg_psp__settlement_items') }}

),

bank_transactions as (

    select *
    from {{ ref('stg_bank__statement_transactions') }}

),

item_summary as (

    select
        settlement_id,

        count(*)::integer
            as settlement_item_count,

        count(
            distinct financial_event_id
        )::integer
            as settled_financial_event_count,

        sum(
            settlement_gross_eur_amount
        )::numeric(18, 2)
            as item_gross_eur_amount,

        sum(
            fee_eur_amount
        )::numeric(18, 2)
            as item_fee_eur_amount,

        sum(
            settlement_net_eur_amount
        )::numeric(18, 2)
            as item_net_eur_amount

    from settlement_items

    group by settlement_id

),

bank_reference_summary as (

    select
        payment_reference as bank_reference,

        count(*)::integer
            as bank_reference_match_count,

        count(*) filter (
            where
                bank_status = 'BOOKED'
                and direction = 'CREDIT'
                and currency = 'EUR'
        )::integer
            as eligible_bank_receipt_count,

        case
            when count(*) filter (
                where
                    bank_status = 'BOOKED'
                    and direction = 'CREDIT'
                    and currency = 'EUR'
            ) = 1
                then min(
                    bank_transaction_id
                ) filter (
                    where
                        bank_status = 'BOOKED'
                        and direction = 'CREDIT'
                        and currency = 'EUR'
                )
        end as bank_transaction_id,

        case
            when count(*) filter (
                where
                    bank_status = 'BOOKED'
                    and direction = 'CREDIT'
                    and currency = 'EUR'
            ) = 1
                then min(
                    booking_date
                ) filter (
                    where
                        bank_status = 'BOOKED'
                        and direction = 'CREDIT'
                        and currency = 'EUR'
                )
        end as bank_booking_date,

        case
            when count(*) filter (
                where
                    bank_status = 'BOOKED'
                    and direction = 'CREDIT'
                    and currency = 'EUR'
            ) = 1
                then min(
                    value_date
                ) filter (
                    where
                        bank_status = 'BOOKED'
                        and direction = 'CREDIT'
                        and currency = 'EUR'
                )
        end as bank_value_date,

        case
            when count(*) filter (
                where
                    bank_status = 'BOOKED'
                    and direction = 'CREDIT'
                    and currency = 'EUR'
            ) = 1
                then min(
                    bank_amount
                ) filter (
                    where
                        bank_status = 'BOOKED'
                        and direction = 'CREDIT'
                        and currency = 'EUR'
                )
        end::numeric(18, 2)
            as bank_amount

    from bank_transactions

    where payment_reference is not null

    group by payment_reference

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
            item_summary.settlement_item_count,
            0
        )::integer
            as settlement_item_count,

        coalesce(
            item_summary.settled_financial_event_count,
            0
        )::integer
            as settled_financial_event_count,

        coalesce(
            item_summary.item_gross_eur_amount,
            0
        )::numeric(18, 2)
            as item_gross_eur_amount,

        coalesce(
            item_summary.item_fee_eur_amount,
            0
        )::numeric(18, 2)
            as item_fee_eur_amount,

        coalesce(
            item_summary.item_net_eur_amount,
            0
        )::numeric(18, 2)
            as item_net_eur_amount,

        (
            settlements.gross_amount
            - coalesce(
                item_summary.item_gross_eur_amount,
                0
            )
        )::numeric(18, 2)
            as gross_header_minus_items_amount,

        (
            settlements.fee_amount
            - coalesce(
                item_summary.item_fee_eur_amount,
                0
            )
        )::numeric(18, 2)
            as fee_header_minus_items_amount,

        (
            settlements.net_payout_amount
            - coalesce(
                item_summary.item_net_eur_amount,
                0
            )
        )::numeric(18, 2)
            as net_header_minus_items_amount,

        coalesce(
            bank_reference_summary.bank_reference_match_count,
            0
        )::integer
            as bank_reference_match_count,

        coalesce(
            bank_reference_summary.eligible_bank_receipt_count,
            0
        )::integer
            as eligible_bank_receipt_count,

        bank_reference_summary.bank_transaction_id,
        bank_reference_summary.bank_booking_date,
        bank_reference_summary.bank_value_date,
        bank_reference_summary.bank_amount,

        case
            when bank_reference_summary.bank_booking_date
                is not null
                then (
                    bank_reference_summary.bank_booking_date
                    - settlements.settlement_date
                )::integer
        end as bank_delay_days,

        case
            when bank_reference_summary.bank_amount
                is not null
                then (
                    bank_reference_summary.bank_amount
                    - settlements.net_payout_amount
                )::numeric(18, 2)
        end as bank_minus_settlement_amount,

        settlements.created_at,

        settlements._loaded_at,
        settlements._batch_id

    from settlements

    left join item_summary
        on settlements.settlement_id
        = item_summary.settlement_id

    left join bank_reference_summary
        on settlements.bank_reference
        = bank_reference_summary.bank_reference

)

select *
from combined