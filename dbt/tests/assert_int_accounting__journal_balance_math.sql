select
    journal_entry_id,
    total_debit_eur_amount,
    total_credit_eur_amount,
    journal_balance_difference_eur

from {{ ref('int_accounting__journal_entries') }}

where
    journal_balance_difference_eur
    != (
        total_debit_eur_amount
        - total_credit_eur_amount
    )