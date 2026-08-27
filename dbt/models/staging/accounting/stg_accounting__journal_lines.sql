with source as (

    select *
    from {{ source('accounting', 'journal_lines') }}

),

renamed as (

    select
        journal_line_id::text as journal_line_id,
        journal_entry_id::text as journal_entry_id,

        posting_date::date as posting_date,

        account_code::text as account_code,
        account_name::text as account_name,

        {{ minor_units_to_amount('debit_eur_minor') }}
            as debit_eur_amount,

        {{ minor_units_to_amount('credit_eur_minor') }}
            as credit_eur_amount,

        source_system::text as source_system,
        source_reference_type::text as source_reference_type,
        source_reference::text as source_reference,

        journal_status::text as journal_status,

        created_at::timestamptz as created_at,

        _loaded_at::timestamptz as _loaded_at,
        _batch_id::text as _batch_id

    from source

)

select *
from renamed