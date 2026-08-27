# M4 Acceptance — Reconciliation Facts and Finance Marts

M4 is complete when the reusable M3 finance logic is converted into
consumer-facing reconciliation facts, deterministic finance-control
exceptions, and daily Finance KPIs.

## Scope

M4 contains exactly four consumer-facing models:

- `fct_payment_reconciliation`
- `fct_settlement_reconciliation`
- `mart_reconciliation_exceptions`
- `mart_finance_daily`

## Grains

The declared grains are:

- one row per successful PSP capture;
- one row per PSP settlement;
- one row per reconciliation exception;
- one row per business date, product, and currency.

The M4 validator verifies these grains independently of dbt's model
tests.

## Reconciliation policy

M4 applies the frozen Finance control policy:

- EUR amount tolerance: €0.01;
- missing settlement remains pending through 5 calendar days;
- missing bank receipt remains pending through 2 calendar days;
- PSP-vs-reference FX variance above 3% is an FX outlier;
- aging controls use a deterministic reconciliation as-of date.

The validator confirms that these dbt variables remain present and
consistent with the project contract.

## Exception semantics

`mart_reconciliation_exceptions` has one row per detected control
exception.

The supported taxonomy includes:

- missing, duplicate, and mismatched captures;
- invalid and excessive refunds;
- missing and late settlements;
- settlement-total mismatches;
- missing and mismatched bank receipts;
- missing and mismatched ledger postings;
- unbalanced journals;
- missing and outlier FX;
- unmapped products.

Finance exceptions do not fail ingestion or transformation layers.

They are surfaced as reconciliation outputs.

## Reconciliation statuses

Active controls use:

- `PENDING`
- `OPEN_BREAK`

Historical breaches that later obtained the required downstream event
may use:

- `RESOLVED`

`RECONCILED` is primarily represented by the absence of an active
exception for a finance object and is used by the reporting layer when
classifying captures.

`EXCLUDED` is reserved for explicit reconciliation-exclusion policy.

## Primary KPI

The primary reconciliation KPI is amount based:

```text
reconciled_capture_amount_eur
--------------------------------
valued_capture_amount_eur
```
Captures without a reliable EUR valuation are reported separately
through unvalued_capture_count; they are not silently treated as zero
EUR.

## Clean scenario acceptance

The deterministic clean scenario is expected to have:

- all payment reconciliation controls passing;
- all settlement, bank, and accounting controls passing;
- zero reconciliation exception rows;
- zero unvalued captures;
- all captures classified as reconciled;
- an amount reconciliation rate of 100% for every daily grain with
- valued capture volume;
- invoice, capture, exception, and EUR-valued payment totals conserved
- through the reporting layer.

These conditions are acceptance expectations for the clean synthetic
dataset, not generic constraints on future anomaly datasets.

## Clean local acceptance

Run the complete milestone from an explicit clean database:

```bash
make postgres-reset
make postgres-wait
make m4-acceptance
```

`postgres-reset` remains intentionally separate because it is a
destructive action.

## M4 exit criteria

M4 is complete when:

1. M3 acceptance succeeds;
2. all four marts build and their dbt tests pass;
3. marts have no direct dbt source dependencies;
4. all four declared grains are preserved;
5. the frozen reconciliation policy is present;
6. the clean exception mart contains zero rows;
7. all clean capture amounts are reconciled;
8. the amount-based reconciliation rate is 100% for valued captures;
9. reporting totals reconcile to their upstream finance facts.