with source as (

    select *
    from {{ source('billing', 'subscriptions') }}

),

renamed as (

    select
        subscription_id::text as subscription_id,
        customer_id::text as customer_id,
        product_id::text as product_id,

        subscription_status::text as subscription_status,

        started_at::timestamptz as started_at,
        cancelled_at::timestamptz as cancelled_at,

        created_at::timestamptz as created_at,
        updated_at::timestamptz as updated_at,

        _loaded_at::timestamptz as _loaded_at,
        _batch_id::text as _batch_id

    from source

)

select *
from renamed