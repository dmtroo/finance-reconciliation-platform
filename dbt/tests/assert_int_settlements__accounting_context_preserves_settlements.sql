with source_settlements as (

    select settlement_id
    from {{ ref('stg_psp__settlements') }}

),

accounting_context as (

    select settlement_id
    from {{ ref('int_settlements__accounting_context') }}

),

missing_from_context as (

    select settlement_id
    from source_settlements

    except

    select settlement_id
    from accounting_context

),

unexpected_in_context as (

    select settlement_id
    from accounting_context

    except

    select settlement_id
    from source_settlements

)

select *
from missing_from_context

union all

select *
from unexpected_in_context