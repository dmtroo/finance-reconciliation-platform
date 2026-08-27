with source as (

    select *
    from {{ source('billing', 'products') }}

),

renamed as (

    select
        product_id::text as product_id,
        product_name::text as product_name,
        product_family::text as product_family,
        billing_interval::text as billing_interval,

        {{ minor_units_to_amount('list_price_minor') }}
            as list_price_amount,

        currency::text as currency,
        is_active::boolean as is_active,

        created_at::timestamptz as created_at,
        updated_at::timestamptz as updated_at,

        _loaded_at::timestamptz as _loaded_at,
        _batch_id::text as _batch_id

    from source

)

select *
from renamed