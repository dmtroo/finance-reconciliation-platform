# M3 Acceptance — Intermediate Finance Logic

M3 is complete when the normalized staging sources are connected through
reusable finance transformations without assigning final reconciliation
statuses or exception codes.

## Scope

M3 introduces cross-source finance logic using dbt `ref()` dependencies.

The intermediate layer resolves:

- as-of ECB reference FX;
- PSP capture, refund, and chargeback lifecycle;
- invoice payment summaries;
- financial-event to settlement mapping;
- settlement-header to settlement-item comparisons;
- PSP settlement to bank receipt matching context;
- accounting journal-entry aggregation;
- financial-event accounting context;
- settlement accounting context.

M3 does not assign final reconciliation statuses, severities, or
exception codes.

Those responsibilities belong to M4.

## Dependency contract

Staging models depend directly on dbt sources.

Intermediate models depend only on upstream dbt models through `ref()`.

Intermediate models must not access RAW sources directly with `source()`.

The M3 validator checks this rule against dbt's parsed manifest.

## Intermediate grains

M3 contains 9 models with explicit grains:

- one row per PSP financial event with reference FX;
- one row per PSP capture lifecycle;
- one row per Billing invoice payment summary;
- one row per PSP financial event settlement mapping;
- one row per PSP settlement bank context;
- one row per accounting journal entry;
- one row per accounting source reference;
- one row per PSP financial event accounting context;
- one row per PSP settlement accounting context.

Many-side relations are aggregated to the target grain before joining to
prevent accidental row multiplication.

## Missing data semantics

Intermediate models preserve missing and ambiguous matches.

Examples include:

- missing ECB reference FX;
- missing settlement items;
- multiple settlement matches;
- missing bank receipts;
- multiple eligible bank receipts;
- missing accounting entries;
- multiple posted accounting entries.

These conditions are represented as null values, match counts, amount
differences, and delays.

They are not treated as pipeline failures.

## Clean scenario acceptance

The clean synthetic scenario is expected to have:

- an eligible as-of reference FX rate for every financial event;
- one settlement mapping per financial event;
- settlement headers equal to aggregated settlement items;
- one eligible bank receipt per PAID settlement;
- bank receipt amounts equal to PSP net payouts;
- balanced accounting journal entries;
- one posted accounting entry per financial event and settlement;
- accounting amounts equal to the expected finance amounts.

These are clean-scenario expectations, not generic source-quality
constraints. Future anomaly scenarios are intentionally allowed to
violate them.

## Clean local acceptance

The complete M3 milestone can be reproduced with:

```bash
make postgres-reset
make postgres-wait
make m3-acceptance
```

The PostgreSQL reset remains an explicit destructive action.

## M3 exit criteria

M3 is complete when:

1. M2 acceptance succeeds;
2. all intermediate dbt models and transformation tests build;
3. exactly 9 intermediate models exist;
4. intermediate models have no direct dbt source dependencies;
5. all declared grains are preserved;
6. the clean-scenario intermediate finance invariants pass.

After M3 is complete, development proceeds to M4: reconciliation facts,
control statuses, and the finance exception mart.