# M2 Acceptance — dbt Staging Layer

M2 is complete when all 10 RAW source relations are exposed through a
tested and reproducible dbt staging layer.

## Scope

M2 standardizes source data for downstream finance transformations.

Staging models may:

- reference exactly one dbt source relation;
- rename and cast source fields;
- convert integer minor-unit money into decimal major-unit amounts;
- derive source-local fields such as PSP financial-event signs;
- normalize ECB FX orientation;
- add the derived EUR=1 ECB rate.

Staging models must not:

- join different source systems;
- reconcile invoices, payments, settlements, bank cash, or accounting;
- perform ECB as-of date matching;
- classify finance exceptions;
- aggregate finance marts.

## Models

M2 contains exactly 10 staging views:

- 3 Billing models
- 4 PSP models
- 1 Bank model
- 1 Accounting model
- 1 ECB model

## Canonical money representation

RAW monetary values remain integer minor units.

Staging converts monetary values into:

`numeric(18,2)`

while retaining their transaction or reporting currency semantics.

## PSP event signs

PSP financial-event source amounts remain positive in RAW.

Staging derives:

- CAPTURE: positive
- REFUND: negative
- CHARGEBACK: negative

through `signed_event_amount`.

## ECB FX orientation

RAW ECB observations preserve the source orientation:

`foreign currency units per 1 EUR`

Staging additionally derives:

`EUR per 1 foreign currency unit`

as `eur_per_unit`.

A derived EUR=1 observation is added for every available ECB rate date.

Weekend and holiday as-of matching is not a staging responsibility and
will be implemented in the intermediate layer.

## Grain contract

Nine staging models preserve their RAW source grain one-to-one.

ECB is the only intentional exception:

`staging ECB rows = RAW ECB rows + distinct ECB rate dates`

because one EUR=1 row is added per rate date.

## Dependency contract

Every staging model must depend directly on exactly one dbt source.

Staging models must not depend on other dbt models via `ref()`.

The M2 acceptance validator checks this rule against dbt's parsed
`manifest.json`.

## Clean local acceptance

The full M2 milestone can be reproduced with:

```bash
make postgres-reset
make postgres-wait
make m2-acceptance
```

The database reset is deliberately explicit because it destroys the local
PostgreSQL Docker volume.

## M2 exit criteria

M2 is complete when the clean acceptance workflow:

1. completes M1 acceptance;
2. builds and tests all staging models;
3. confirms exactly 10 staging views;
4. confirms source-only staging lineage;
5. confirms one-to-one source grain where required;
6. confirms ECB derived-row grain;
7. confirms canonical money and FX numeric types.

After M2 is complete, development proceeds to M3: reusable intermediate
finance logic.