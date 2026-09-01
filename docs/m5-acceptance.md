# M5 Acceptance — Deterministic Reconciliation Anomalies

## Purpose

M5 proves that the Finance reconciliation platform behaves correctly under both clean and intentionally inconsistent source data.

The milestone has two required scenarios:

1. `clean`
2. `with_anomalies`

The clean scenario proves that valid source data continues to reconcile successfully.

The anomaly scenario proves that Finance mismatches flow through the data platform and are classified as reconciliation exceptions instead of causing the pipeline to fail.

## Milestone principle

A reconciliation system must not fail simply because the systems being reconciled disagree.

Source disagreements are business facts.

The pipeline must preserve those facts, connect the relevant systems, measure the differences, and expose them as Finance controls.

Therefore M5 requires:

```text
Finance mismatch
→ pipeline remains operational
→ reconciliation exception is surfaced
```

and not:

```text
Finance mismatch
→ ingestion or dbt pipeline fails
```

## Frozen anomaly taxonomy

The `with_anomalies` scenario contains one deterministic injected source mutation for each frozen reconciliation control:

* `MISSING_CAPTURE`
* `CAPTURE_AMOUNT_MISMATCH`
* `DUPLICATE_CAPTURE`
* `INVALID_REFUND`
* `OVER_REFUND`
* `MISSING_SETTLEMENT`
* `LATE_SETTLEMENT`
* `SETTLEMENT_TOTAL_MISMATCH`
* `MISSING_BANK_RECEIPT`
* `BANK_AMOUNT_MISMATCH`
* `MISSING_LEDGER_POSTING`
* `LEDGER_AMOUNT_MISMATCH`
* `UNBALANCED_JOURNAL`
* `MISSING_FX_RATE`
* `FX_RATE_OUTLIER`
* `UNMAPPED_PRODUCT`

The generator manifest must contain exactly sixteen injected anomaly records.

The downstream exception mart may contain more than sixteen rows because one source mutation can legitimately trigger more than one control.

## Scenario invariants

Both generator scenarios use the same deterministic seed, catalog, date range, and reference FX fixture.

The number of rows in all nine synthetic private-system source tables must be identical between the clean and anomaly scenarios.

The anomaly layer changes business values, relationships, or references rather than changing the scale of the generated dataset.

The nine tables are:

* `billing/products`
* `billing/subscriptions`
* `billing/invoices`
* `psp/payment_attempts`
* `psp/financial_events`
* `psp/settlements`
* `psp/settlement_items`
* `bank/statement_transactions`
* `accounting/journal_lines`

## Clean acceptance

The clean phase reuses the M4 acceptance workflow.

It requires:

* deterministic clean source generation;
* successful RAW ingestion;
* successful ECB fixture loading;
* successful staging build;
* successful intermediate build;
* successful mart build;
* zero reconciliation exceptions;
* clean payment controls passing;
* clean settlement controls passing;
* amount-based reconciliation rate equal to 100% where a valued denominator exists.

## Anomaly acceptance

The anomaly phase starts from a fresh PostgreSQL database.

It requires:

* successful deterministic `with_anomalies` generation;
* exactly sixteen anomaly records in `_manifest.json`;
* successful RAW ingestion;
* successful ECB fixture loading;
* successful staging build;
* successful intermediate build;
* successful mart build;
* all sixteen frozen exception codes present in `mart_reconciliation_exceptions`;
* valid status and severity policy;
* non-negative `exception_amount_eur`;
* at least one unvalued capture from `MISSING_FX_RATE`;
* reconciled valued capture amount below total valued capture amount;
* at least one daily Finance row below 100% amount reconciliation.

## Database isolation

The clean and anomaly scenarios must not be loaded into the same existing RAW database.

Append-like RAW tables use idempotent conflict handling, so loading anomalous rows over existing clean rows with the same identifiers would preserve the earlier clean records.

The acceptance workflow therefore uses separate clean-room database states:

```text
reset
→ clean
→ validate

reset
→ with_anomalies
→ validate
```

## Validators

M5 uses two complementary validators.

### `scripts/validate_m5_anomalies.py`

Validates the anomaly scenario after RAW loading and dbt transformation.

It checks:

* the sixteen injected manifest codes;
* the sixteen frozen downstream exception codes;
* exception status and severity;
* exception amount magnitude semantics;
* Finance daily reconciliation impact.

### `scripts/validate_m5.py`

Validates the relationship between the two generated scenarios.

It checks:

* `clean` contains zero injected anomalies;
* `with_anomalies` contains exactly sixteen;
* anomaly injection order matches the frozen M5 contract;
* all nine private-system source tables exist in both manifests;
* row counts are identical between scenarios.

## Running M5 acceptance

Run from the repository root:

```bash
make m5-acceptance
```

A successful run must complete both scenario pipelines and end with:

```text
M5 anomaly validation passed.
M5 scenario validation passed.
```

## Expected result

After M5, the platform demonstrates both sides of reconciliation behavior:

```text
clean source systems
→ reconciled Finance outputs

inconsistent source systems
→ operational pipeline
→ measured differences
→ classified Finance exceptions
```

