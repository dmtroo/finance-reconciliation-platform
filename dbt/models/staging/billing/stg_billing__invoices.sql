with source as (

    select *
    from {{ source('billing', 'invoices') }}

),

renamed as (

    select
        invoice_id::text as invoice_id,
        subscription_id::text as subscription_id,
        customer_id::text as customer_id,
        product_id::text as product_id,

        invoice_date::date as invoice_date,
        due_date::date as due_date,

        currency::text as currency,

        {{ minor_units_to_amount('subtotal_minor') }}
            as subtotal_amount,

        {{ minor_units_to_amount('tax_minor') }}
            as tax_amount,

        {{ minor_units_to_amount('total_minor') }}
            as total_amount,

        invoice_status::text as invoice_status,

        created_at::timestamptz as created_at,
        updated_at::timestamptz as updated_at,

        _loaded_at::timestamptz as _loaded_at,
        _batch_id::text as _batch_id

    from source

)

select *
from renamed