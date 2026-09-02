# M6 Finance Reporting Export

## Purpose

The dbt marts are the system-of-record analytical output. The Excel
export is a **downstream Finance consumer** of those marts - not another
transformation layer.

`reports/exports/finance_reconciliation_report.xlsx` presents what
`mart_finance_daily` and `mart_reconciliation_exceptions` already
computed. The reporting layer performs no reconciliation: no rate
calculation, no exception classification, no amount differencing, no
Excel formulas for Finance logic. Every number is read from a mart and
laid out for reading.

## Report contents

### Daily Summary

One row per `mart_finance_daily` row - grain `business_date x product x
currency`, unchanged. For daily reconciliation monitoring: capture
volume and amounts, valued vs reconciled EUR, `amount_reconciliation_rate`,
unvalued captures, and per-day exception counts / amounts.

### Exceptions

One row per `mart_reconciliation_exceptions` row. The Finance
investigation queue: `exception_code`, status, severity, the
`entity_type` / `entity_id` and `business_date` needed to chase a
specific invoice / payment / settlement, plus `age_days`, observed /
expected / difference amounts, and `control_source`.

Rows are ordered worst-severity first (`CRITICAL` -> `WARNING` ->
`INFO`), then by code, date and entity - a presentation order only, not
a new classification.

## Source marts

| Sheet | Mart |
|---|---|
| Daily Summary | `mart_finance_daily` |
| Exceptions | `mart_reconciliation_exceptions` |

The reporting layer does not read `fct_payment_reconciliation` or
`fct_settlement_reconciliation` directly - the marts exist precisely so
downstream consumers do not have to.

## Publishing gate

```
dbt marts
    |
    v
validate_reconciliation   (clean Finance contract, M4)
    |
    v
export_finance_report
```

In the Airflow DAG `export_finance_report` runs **after**
`validate_reconciliation`. If the clean reconciliation contract breaks,
the export never runs and Finance does not receive a report the pipeline
already considers invalid. `finance-recon report-export` itself assumes
the marts already exist - it never runs dbt.

## Determinism

Same mart state -> same explicit `ORDER BY` -> same sheet contents. The
export is **content-deterministic**, not byte-deterministic: openpyxl
may vary workbook metadata between writes, and it round-trips numeric
cells through float, so money is compared on read-back with the usual
`0.01` tolerance (an export-fidelity tolerance, not a reconciliation
threshold).

The output filename is fixed (`finance_reconciliation_report.xlsx`, no
timestamp) so an Airflow retry / re-run overwrites the same artifact.
The write is atomic - a temp file is saved then `os.replace`d - so a
failed export never leaves a half-written workbook. The `.xlsx` is a
runtime artifact and is git-ignored; only `reports/exports/.gitkeep` is
tracked.

## One mechanism, both mart states

`finance-recon report-export` always reads whatever is in the marts now:

- DB in the **clean** state -> Excel is clean (Exceptions sheet: 0 data
  rows);
- DB in the **with_anomalies** state -> the same export shows the
  exception rows.

The output filename never changes, so every run overwrites
`reports/exports/finance_reconciliation_report.xlsx`.

## Local use

```bash
# marts must already be built (make m4-acceptance / m5-acceptance)
make finance-report-export       # or: finance-recon report-export
make finance-report-validate
# or both:
make finance-report-acceptance

# full proof of both mart states (builds clean then anomaly marts):
make finance-report-scenarios
```

`finance-recon report-export --output <path>` overrides the destination.

## What `validate_finance_report.py` checks

It compares the workbook against the live marts - nothing more:

- file exists, is non-empty, opens; both sheets present;
- Daily Summary data rows `==` `mart_finance_daily` row count;
- Exceptions data rows `==` `mart_reconciliation_exceptions` row count;
- distinct `exception_code` set in the Exceptions sheet `==` the mart's;
- `sum(exception_count)` and `sum(unvalued_capture_count)` match exactly;
- `sum(valued_capture_amount_eur)` and
  `sum(reconciled_capture_amount_eur)` match within `0.01`.

`--scenario` adds one assertion on top:

| `--scenario` | extra check |
|---|---|
| `any` (default) | none - report vs marts only |
| `clean` | Exceptions sheet has 0 data rows |
| `with_anomalies` | Exceptions rows present **and** all 16 frozen anomaly codes are in the report |

It never re-checks reconciliation rate, exception status, or timing
policy - `validate_m4.py` / `validate_m5_anomalies.py` own those. Row and
code counts are read from the database, never hardcoded.

## Acceptance - both scenarios

`make finance-report-scenarios`:

1. clean pipeline (`m4-acceptance`) -> `report-export` ->
   `validate_finance_report.py --scenario clean` (Exceptions = 0);
2. anomaly pipeline (`m5-anomaly-pipeline`) -> `report-export` (same
   file, overwritten) -> `--scenario with_anomalies`
   (Exceptions rows `==` mart, all 16 codes present).

## CI coverage

- `finance-integration`: after `make m5-acceptance` the marts are in the
  with_anomalies state, then `make finance-report-export` +
  `validate_finance_report.py --scenario with_anomalies` proves the
  Exceptions sheet exports every frozen anomaly code.
- `airflow-integration`: `make airflow-workflow-acceptance` runs the DAG
  (clean) twice; `export_finance_report` publishes the report and
  `validate_airflow_workflow.py` runs
  `validate_finance_report.py --scenario clean` after the second run -
  proving the report overwrites safely and stays valid with 0 exception
  rows.

Between the two jobs CI exercises both the anomaly report and the clean
report from the one export mechanism.

## What this is not

Not a dashboard, not Streamlit / Power BI / Tableau, not charts, not a
pivot workbook, no pandas. A small operational Finance export is the
point: warehouse -> controlled Finance marts -> Excel-ready output.
