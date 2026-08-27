with source_settlements as (

    select settlement_id
    from {{ ref('int_settlements__bank_context') }}

),

reconciliation_fact as (

    select settlement_id
    from {{ ref('fct_settlement_reconciliation') }}

),

missing_from_fact as (

    select settlement_id
    from source_settlements

    except

    select settlement_id
    from reconciliation_fact

),

unexpected_in_fact as (

    select settlement_id
    from reconciliation_fact

    except

    select settlement_id
    from source_settlements

)

select *
from missing_from_fact

union all

select *
from unexpected_in_fact