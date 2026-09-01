# M6 Continuous Integration

## Purpose

CI reproduces the repository's quality, Finance reconciliation
integration, and Airflow orchestration checks on a clean GitHub-hosted
runner before code is merged.

Until Commit 35 these checks only ran when a developer remembered to run
them locally. A forgotten `make test` could land a broken pipeline in a
pull request. Now every pull request — and every push to `main` — must
go green on a from-scratch Ubuntu machine first.

CI does not add any new Finance logic, dbt models, thresholds, or DAG
behaviour. It only automates the contracts that already exist.

## Workflow

`.github/workflows/ci.yml`, one workflow named **Finance Reconciliation
CI**, three jobs:

```
                    quality
                   /       \
                  v         v
       finance-integration  airflow-integration
```

`finance-integration` and `airflow-integration` both depend on
`quality` and are otherwise independent — they run in parallel on
separate runners with separate databases.

### Triggers

| Event | Why |
|---|---|
| `pull_request` | every change is checked before merge |
| `push` to `main` | re-confirm the state of the main branch after merge |
| `workflow_dispatch` | manual run from the GitHub UI |

Feature branches are covered by their pull request, so `push` is scoped
to `main` only — no double runs.

### Concurrency

A new push to a pull request cancels its still-running CI. Pushes to
`main` always run to completion. The concurrency group is keyed by
PR number (or ref), so different pull requests never block each other.

### Permissions

`contents: read` only. CI checks out, builds, and tests; it never
pushes, comments, or publishes.

## quality job

Fast, no Docker.

- `make lint` — `ruff` over `src`, `tests`, `scripts`
- `make test` — `pytest` unit suite
- `make validate-contract` — DDL / dbt sources / generator config
  alignment

Local equivalent:

```bash
make lint
make test
make validate-contract
```

## finance-integration job

`needs: quality`. Brings up the business PostgreSQL from
`docker-compose.yml` and runs the full M0-M5 acceptance:

```
make m5-acceptance
```

which does, in one chain:

- `clean` scenario: generate -> RAW load -> ECB load -> dbt
  staging/intermediate/marts -> M1-M4 validation -> 0 exceptions,
  100% reconciliation;
- `with_anomalies` scenario: 16 deterministic source mutations -> RAW ->
  dbt -> all 16 exception codes present -> Finance KPI impact -> M5
  validation.

ECB reference data comes from the committed deterministic fixture
(`generator/fixtures/ecb_raw_ci_rates.csv`). CI never calls the live ECB
feed, so a transient ECB outage cannot turn a correct pull request red.

Local equivalent:

```bash
make m5-acceptance
```

## airflow-integration job

`needs: quality`. Stands up both databases and the Airflow runtime, then
runs the Commit 34 workflow acceptance:

```
make airflow-build
make airflow-workflow-acceptance
```

`airflow-workflow-acceptance` resets only the **business** database,
then:

- `airflow-smoke` — runtime health (scheduler / DAG processor / API);
- `airflow-pipeline-check` — DAG contract: `finance-recon` and `dbt`
  available in the image, DAG imports clean, DAG discovered, all 9 tasks
  present including the `validate_reconciliation` gate;
- `airflow-workflow-validate` — triggers `finance_reconciliation_pipeline`
  twice with no database reset in between, then asserts: both runs
  `success`, RAW row counts identical across runs, RAW source identity
  unique, `mart_reconciliation_exceptions` `0`, and the clean M4
  contract still holds.

Local equivalent:

```bash
make airflow-workflow-acceptance
```

The two DAG runs prove operationally safe orchestration:

```
deterministic generator + idempotent ingestion + repeated DAG run
        =
identical RAW state, unchanged clean reconciliation
```

## Isolation and secrets

Each job runs on its own GitHub runner. The `finance-integration`
database and the `airflow-integration` databases are unrelated
instances.

**No production credentials are required.** CI uses only:

- ephemeral local PostgreSQL credentials, copied from `.env.example`
  into a runner-local `.env` that is never committed;
- committed deterministic fixtures.

No GitHub secrets, no cloud access, no external network dependency.

## Failure diagnostics

On job failure (`if: failure()`) the integration jobs print
`docker compose ps -a` and the tail of the relevant container logs into
the Actions output. Teardown (`if: always()`) brings every stack down
with `-v` and is guarded so a cleanup error never masks the real
failure. No artifacts are uploaded.

## Local / CI equivalence

| GitHub job | Local command |
|---|---|
| `quality` | `make lint && make test && make validate-contract` |
| `finance-integration` | `make m5-acceptance` |
| `airflow-integration` | `make airflow-workflow-acceptance` |

The workflow calls Make targets, not raw tool commands, so the same
step behaves identically on a laptop and on a runner.

## Out of scope for Commit 35

- production deployment / registry push;
- scheduled (cron) DAG cadence;
- coverage gates, `sqlfluff`, `mypy`, `pre-commit`;
- a Python version matrix;
- the `with_anomalies` scenario inside the Airflow DAG (M5 owns anomaly
  proof; the production DAG stays `clean`).
