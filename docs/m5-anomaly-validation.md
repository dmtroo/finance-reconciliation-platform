# M5 Anomaly Output Validation

## Purpose

Commit 29 validates that deterministic source anomalies created by the
synthetic generator are surfaced by the reconciliation marts as Finance
exceptions.

This validation does not generate, load, or transform data. It assumes that a
`with_anomalies` source run has already been generated and loaded and that the
dbt marts have already been built.

## Validation boundary

The generator is responsible for creating deterministic source conditions.

The reconciliation models are responsible for classifying those conditions.

A Finance reconciliation exception must not be treated as a pipeline failure.

The validator therefore checks both sides independently:

1. the source-run manifest contains the frozen injected anomalies;
2. `mart_reconciliation_exceptions` contains the frozen exception taxonomy;
3. exception status and severity follow the configured Finance policy;
4. exception amounts are non-negative magnitudes;
5. `mart_finance_daily` reflects the reconciliation impact.

## Frozen anomaly taxonomy

The M5 `with_anomalies` scenario injects one deterministic source mutation for
each of the following codes:

- `MISSING_CAPTURE`
- `CAPTURE_AMOUNT_MISMATCH`
- `DUPLICATE_CAPTURE`
- `INVALID_REFUND`
- `OVER_REFUND`
- `MISSING_SETTLEMENT`
- `LATE_SETTLEMENT`
- `SETTLEMENT_TOTAL_MISMATCH`
- `MISSING_BANK_RECEIPT`
- `BANK_AMOUNT_MISMATCH`
- `MISSING_LEDGER_POSTING`
- `LEDGER_AMOUNT_MISMATCH`
- `UNBALANCED_JOURNAL`
- `MISSING_FX_RATE`
- `FX_RATE_OUTLIER`
- `UNMAPPED_PRODUCT`

The source-run manifest must contain exactly one injected mutation for every
code.

The exception mart may contain more than sixteen rows because one source
mutation can legitimately trigger more than one reconciliation control.

## Aging policy

`MISSING_SETTLEMENT` uses the frozen five-calendar-day settlement window:

- age up to and including five days: `PENDING / INFO`
- age greater than five days: `OPEN_BREAK / CRITICAL`

`MISSING_BANK_RECEIPT` uses the frozen two-calendar-day bank window:

- age up to and including two days: `PENDING / INFO`
- age greater than two days: `OPEN_BREAK / CRITICAL`

`LATE_SETTLEMENT` represents an already received late settlement and is
therefore `RESOLVED / WARNING`.

## Daily Finance validation

The anomaly scenario must no longer look like the clean M4 scenario.

The validator requires:

- exception volume in `mart_finance_daily` to reconcile to the exception mart;
- at least one unvalued capture because of `MISSING_FX_RATE`;
- positive valued capture volume;
- reconciled capture amount below valued capture amount;
- at least one daily row with amount reconciliation rate below 100%.

## Running

The validator does not build anything. It requires:

- PostgreSQL running;
- a `with_anomalies` source run loaded into a **clean** raw layer;
- ECB reference rates loaded into `raw_ecb.fx_rates` covering the run window;
- staging, intermediate, and mart models built from that source run;
- a current dbt `manifest.json`.

The one-shot workflow that satisfies all of the above:

```bash
make m5-acceptance
```

`m5-acceptance` runs `postgres-reset`, generates the `with_anomalies`
scenario, extracts and loads the ECB fixture, loads the source run,
runs `dbt build`, and finally runs `m5-validate`.

To run only the validator against an already-built database:

```bash
python scripts/validate_m5_anomalies.py \
  --run-dir data/generated/SYN-42-2026-01-01-2026-01-31-with_anomalies
```

## Prerequisites that are easy to miss

### ECB reference rates must be loaded

The FX controls depend on `int_financial_events__with_reference_fx`,
which reads `raw_ecb.fx_rates`. That table is **not** produced by the
synthetic generator; it is loaded separately with `finance-recon
ecb-extract` + `finance-recon ecb-load`.

If `raw_ecb.fx_rates` is empty (or does not cover the run window),
`reference_fx_rate` and `event_amount_eur` are `NULL` for every event
and the taxonomy check fails with:

```
Missing=['FX_RATE_OUTLIER', 'LEDGER_AMOUNT_MISMATCH']
```

with `MISSING_FX_RATE` reported for the full event volume instead of the
single injected event. `FX_RATE_OUTLIER` needs a reference rate to
compute the variance ratio, and `LEDGER_AMOUNT_MISMATCH` compares ledger
postings against `event_amount_eur`.

### The raw layer must be clean

`raw_psp.financial_events`, `raw_accounting.journal_lines`, and the other
append-mode source tables are loaded with `insert ... on conflict do
nothing`. Re-loading a regenerated `with_anomalies` run on top of a
previous load keeps the stale rows, so field-level mutations
(for example the `DUPLICATE_CAPTURE` invoice re-pointing) never reach
the marts. Always `make postgres-reset` before loading this scenario.