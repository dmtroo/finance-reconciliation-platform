# M6 Airflow Workflow Validation

## Purpose

Commit 34 checks the **operational correctness** of the Airflow
reconciliation pipeline, not any new Finance logic.

Commit 33 already proved the pipeline is *structurally* correct: the DAG
exists, imports cleanly, and has the expected tasks. Commit 34 proves two
runtime properties:

1. A successful DAG run means the clean Finance reconciliation is
   genuinely valid — Finance validation is a task inside the DAG, not an
   external afterthought.
2. Running the same DAG again, with no clean-up in between, does not
   create duplicates and does not change the deterministic clean result.

No new dbt models, no generator changes, no ingestion changes, no change
to the M4/M5 Finance policy, and no anomaly scenario in the production
DAG.

## Pipeline

```
generate_private_sources
        |
        v
load_private_raw  +  load_ecb_reference_raw
        |
        v
ingestion_complete
        |
        v
dbt_staging  ->  dbt_intermediate  ->  dbt_marts
        |
        v
validate_reconciliation      <- clean Finance contract gate
        |
        v
pipeline_complete
```

`validate_reconciliation` runs `scripts/validate_m4.py` — the exact same
validator as `make m4-validate`. The DAG re-implements none of its SQL;
it only runs it, with the database host rewritten for in-container access
via `airflow/runtime_env.py`. `pipeline_complete` therefore means
ingestion succeeded **and** dbt succeeded **and** Finance validation
succeeded.

## Retry / rerun contract

```
same deterministic input        (seed 42, config, date range, catalog, FX fixture)
        +
idempotent ingestion            (ON CONFLICT DO NOTHING on natural source ids)
        +
deterministic dbt rebuild
        =
identical RAW state after a repeated DAG run
```

Commit 34 does not artificially fail a task to demonstrate the DAG's
`retries=2` / `retry_delay=1m` / `max_active_runs=1` policy — that would
be a bad production DAG. Retry safety is shown the honest way: a second
full DAG run is the logical equivalent of a retry / re-run, and it must
leave RAW and the clean marts unchanged.

## What is validated

`scripts/validate_airflow_workflow.py`, against an already-running
Airflow runtime and the business PostgreSQL:

1. Airflow runtime is healthy (delegates to
   `scripts/validate_airflow_runtime.py`).
2. Trigger `finance_reconciliation_pipeline` with a known run id; wait for
   that specific run to reach `success` (never `sleep`-and-assume).
3. Snapshot the 10 RAW tables (`count(*)`) and the
   `mart_reconciliation_exceptions` count.
4. Trigger the same DAG again with a second run id — **no**
   `postgres-reset`, no `truncate`, no file deletion.
5. Snapshot again.
6. Assert exact equality of the two RAW snapshots.
7. Assert source-identity uniqueness (`count(*) = count(distinct pk)`) for
   every RAW table.
8. Assert `mart_reconciliation_exceptions` is `0` after both runs.
9. Run `scripts/validate_m4.py` once more for the full clean contract.

The frozen RAW contract is exactly 10 tables — 9 synthetic
private-system tables plus `raw_ecb.fx_rates`:

```
raw_billing.products              raw_psp.settlements
raw_billing.subscriptions         raw_psp.settlement_items
raw_billing.invoices              raw_bank.statement_transactions
raw_psp.payment_attempts          raw_accounting.journal_lines
raw_psp.financial_events          raw_ecb.fx_rates
```

The validator is **not destructive** — it never resets or truncates the
database. Clean-room preparation is done explicitly by a Makefile target
or by the user.

## What is not tested here

- the `with_anomalies` scenario (M5 owns that);
- scheduler-based recurring production cadence (`schedule` stays `None`);
- failure-notification integrations;
- CI;
- reporting / export.

Those are out of scope for Commit 34.

## Running

Requires: the business PostgreSQL running, the Airflow stack built and
running, and the repo bind-mounted into the Airflow image at
`/opt/airflow/project`.

```bash
make airflow-workflow-validate       # just the twice-run workflow validator
make airflow-reconciliation-check    # smoke + pipeline-check + workflow-validate
make airflow-workflow-acceptance     # postgres-reset, then airflow-reconciliation-check
```

`airflow-workflow-acceptance` resets only the **business** database.
Airflow metadata is deliberately kept — the workflow validator addresses
runs by the ids it created, never "the latest run".

Tuning: `--timeout-seconds` (default 900) and `--poll-seconds`
(default 5). On timeout or failure the validator prints the `dag_id`,
`run_id`, last known state, and the per-task states for that run.

### Expected output

```
Airflow runtime: healthy.
Airflow pipeline run 1: success.
RAW snapshot after run 1: 10 tables captured.

Airflow pipeline run 2: success.
RAW snapshot after run 2: 10 tables captured.

RAW idempotency: row counts unchanged.
RAW source identity: uniqueness checks passed.
Clean reconciliation validation: passed.

Airflow reconciliation workflow validation passed.
```

## What this proves

```
M1 deterministic generator
        +
M1 idempotent ingestion
        +
M6 retries / re-runs
        =
operationally safe orchestration
```
