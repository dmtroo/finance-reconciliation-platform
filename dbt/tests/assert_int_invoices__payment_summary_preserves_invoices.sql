with source_invoices as (

    select invoice_id
    from {{ ref('stg_billing__invoices') }}

),

payment_summary as (

    select invoice_id
    from {{ ref('int_invoices__payment_summary') }}

),

missing_from_summary as (

    select invoice_id
    from source_invoices

    except

    select invoice_id
    from payment_summary

),

unexpected_in_summary as (

    select invoice_id
    from payment_summary

    except

    select invoice_id
    from source_invoices

)

select *
from missing_from_summary

union all

select *
from unexpected_in_summary