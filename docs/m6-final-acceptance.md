# M6 Final Acceptance

## Purpose

`make final-acceptance` proves that the complete portfolio project
passes repository quality checks, the deterministic Finance
reconciliation scenarios, Airflow orchestration, repeated-run
idempotency and Finance reporting validation — using the same
implementation components that are used throughout the project.

It is one canonical command. It defines no new checks and re-implements
no validation logic; it orchestrates the acceptance targets that already
exist.

```bash
make final-acceptance
```

## Acceptance phases

The three phases run **strictly sequentially**. The Finance and Airflow
phases each reset the business PostgreSQL, so they can never run in
parallel against one local database.

```text
1. Repository quality   →  2. Finance reconciliation  →  3. Operational Airflow workflow
   (fast, no Docker)        (m5-acceptance)               (airflow-reset → build → workflow)
```

Make stops at the first non-zero exit, so a lint failure means the
Docker and Airflow phases never start.

### Phase 1 — Repository quality (`final-quality-check`)

| Step | Proves |
| --- | --- |
| `make lint` | `ruff` over `src`, `tests`, `scripts` |
| `make test` | the `pytest` unit suite |
| `make validate-contract` | RAW DDL / dbt sources / generator config stay aligned |

### Phase 2 — Finance reconciliation (`final-finance-check`)

Runs `make m5-acceptance` — the Finance/data pipeline **without** the
orchestration layer.

- **clean**: deterministic generation → RAW → ECB → dbt
  staging/intermediate/marts → M1–M4 validation → **0 reconciliation
  exceptions, 0 unvalued captures, 100% amount reconciliation rate**.
- **with_anomalies**: the same deterministic ecosystem with **16
  deterministic source mutations** → RAW → dbt → **all 16 exception
  codes detected** and the daily Finance KPIs deteriorate.

`m5-acceptance` owns its own `postgres-reset`.

### Phase 3 — Operational Airflow workflow (`final-airflow-check`)

| Step | Proves |
| --- | --- |
| `make airflow-reset` | acceptance clean room — old DAG metadata, task states and runs are removed |
| `make airflow-build` | the Airflow image builds from repository state |
| `make airflow-init` | the Airflow metadata database migrates from empty |
| `make airflow-workflow-acceptance` | fresh business DB → run the DAG → snapshot RAW → run the DAG **again with no reset** → snapshot RAW → compare |

`airflow-workflow-acceptance` already runs `postgres-reset`,
`airflow-smoke`, `airflow-pipeline-check`, triggers the DAG twice, and
runs the M4 and report validators, so `final-airflow-check` does not
repeat them.

The DAG contract after Commit 36 is **10/10 tasks**:

```text
generate_private_sources
load_private_raw
load_ecb_reference_raw
ingestion_complete
dbt_staging
dbt_intermediate
dbt_marts
validate_reconciliation      ← clean Finance controls gate
export_finance_report
pipeline_complete
```

Because `validate_reconciliation` runs inside the DAG, a successful DAG
run means not only "the SQL executed" but "the clean Finance controls
passed". `export_finance_report` only runs after that gate, and
`validate_airflow_workflow.py` then checks that
`reports/exports/finance_reconciliation_report.xlsx` exists and that its
**Daily Summary rows = `mart_finance_daily` rows** and **Exceptions rows
= `mart_reconciliation_exceptions` rows** (0 in the clean state).

## Why run the scenarios separately

Finance acceptance checks the business / data logic independently of
Airflow. Airflow acceptance checks orchestration on top of logic that is
already proven. The failure domains are deliberately separated:

```text
Phase 2 fails            →  a Finance / data-pipeline problem
Phase 2 passes, 3 fails  →  an orchestration problem
```

## What repeated-run idempotency proves

```text
deterministic generator + idempotent ingestion + dbt rebuild safety +
Airflow retry / re-run safety  =  a stable operational pipeline
```

The DAG runs twice with no database reset between runs; RAW row counts
must be identical across both runs and the clean Finance result
unchanged.

## Database states

Acceptance deliberately moves the local database through several states:

```text
clean M5 state → reset → with_anomalies M5 state → reset → clean Airflow state
```

For that reason the individual destructive acceptance targets
(`m5-acceptance`, `airflow-workflow-acceptance`, `finance-report-scenarios`)
must not be run in parallel against one local database.

## Final state

After `make final-acceptance` succeeds:

| | State |
| --- | --- |
| Business PostgreSQL | clean reconciliation state (from the last Airflow DAG run) |
| Airflow | running (`http://localhost:8081`) |
| Latest Airflow workflow | success |
| `reports/exports/finance_reconciliation_report.xlsx` | clean report — Daily Summary populated, Exceptions 0 rows |

The with_anomalies report was already proven in Phase 2 and by the
Commit 36 report acceptance; the final operational state is intentionally
clean so the demo opens on a green DAG and a clean Finance output.

## Cleanup

`final-acceptance` deliberately leaves Airflow running so the UI can be
opened immediately. When it is no longer needed:

```bash
make airflow-reset     # stop + remove Airflow containers and volumes
make postgres-down     # stop the business PostgreSQL
```

In GitHub Actions, teardown is handled per job by the CI workflow
(`if: always()` steps), independently of this document.

## Expected evidence

| Evidence | Where |
| --- | --- |
| `Final project acceptance passed.` summary | terminal |
| green DAG | Airflow UI at `http://localhost:8081` |
| `quality` / `finance-integration` / `airflow-integration` green | GitHub Actions |
| clean Finance workbook | `reports/exports/finance_reconciliation_report.xlsx` |
| anomaly workbook (all 16 codes) | `make finance-report-scenarios` (Commit 36) |
