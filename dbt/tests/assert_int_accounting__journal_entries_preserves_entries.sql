with source_entries as (

    select distinct
        journal_entry_id

    from {{ ref('stg_accounting__journal_lines') }}

),

intermediate_entries as (

    select
        journal_entry_id

    from {{ ref('int_accounting__journal_entries') }}

),

missing_entries as (

    select journal_entry_id
    from source_entries

    except

    select journal_entry_id
    from intermediate_entries

),

unexpected_entries as (

    select journal_entry_id
    from intermediate_entries

    except

    select journal_entry_id
    from source_entries

)

select *
from missing_entries

union all

select *
from unexpected_entries