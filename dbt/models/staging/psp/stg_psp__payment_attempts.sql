with source as (

    select *
    from {{ source('psp', 'payment_attempts') }}

),

renamed as (

    select
        payment_attempt_id::text as payment_attempt_id,
        invoice_id::text as invoice_id,
        provider_customer_id::text as provider_customer_id,

        attempted_at::timestamptz as attempted_at,

        currency::text as currency,

        {{ minor_units_to_amount('amount_minor') }}
            as attempt_amount,

        payment_method_type::text as payment_method,
        status::text as payment_status,

        failure_code::text as failure_code,
        provider_transaction_id::text as provider_transaction_id,

        _loaded_at::timestamptz as _loaded_at,
        _batch_id::text as _batch_id

    from source

)

select *
from renamed