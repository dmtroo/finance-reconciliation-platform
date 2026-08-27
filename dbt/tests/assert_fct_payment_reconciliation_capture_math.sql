select
    capture_id,
    invoice_total_amount,
    capture_amount,
    capture_minus_invoice_amount

from {{ ref('fct_payment_reconciliation') }}

where
    capture_currency_matches_invoice is true

    and capture_minus_invoice_amount
        != (
            capture_amount
            - invoice_total_amount
        )::numeric(18, 2)