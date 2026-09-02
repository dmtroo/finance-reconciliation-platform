# Demo guide

How to walk through the project in 5–10 minutes.

Prerequisites: Docker running, Python 3.13, `pip install -e ".[dbt,dev]"`,
`cp .env.example .env`, `make dbt-profile`. If port 5432 is taken by
another project, set `POSTGRES_PORT` in `.env`.

**Before the demo**, run the full acceptance once so the environment is
built and green:

```bash
make final-acceptance
```

It leaves the business DB in the clean state, Airflow running, and a
clean `finance_reconciliation_report.xlsx` on disk — exactly the state
the walkthrough below assumes. See
[`m6-final-acceptance.md`](m6-final-acceptance.md).

---

## Step 1 — Architecture (1 min)

Open the [README](../README.md) architecture and business-flow diagrams.

The story: **invoice → captured payment → PSP settlement → bank cash →
accounting posting**, reconciled against ECB reference FX. Five source
systems, each authoritative for something, none allowed to silently
overwrite another. Disagreement becomes a reconciliation exception.

Layers: RAW (what the source said) → staging (one clean view per
source) → intermediate (cross-system wiring) → facts → marts (Finance
outputs).

---

## Step 2 — Clean scenario (2 min)

```bash
make m5-acceptance
```

This builds the whole pipeline for the `clean` scenario first. The M4
acceptance contract requires, for clean:

- **0 reconciliation exceptions**;
- **0 unvalued captures**;
- a **100% amount reconciliation rate** for valued capture volume.

Then export the report and show it:

```bash
finance-recon report-export
open reports/exports/finance_reconciliation_report.xlsx
```

- **Daily Summary** — one row per `business_date × product × currency`,
  reconciliation rate 100%.
- **Exceptions** — header row, **0 data rows**.

---

## Step 3 — Anomaly scenario (2–3 min)

`make m5-acceptance` also runs `with_anomalies`, so the marts are
already in the anomaly state. Re-export and open the workbook:

```bash
finance-recon report-export
python scripts/validate_finance_report.py --scenario with_anomalies
open reports/exports/finance_reconciliation_report.xlsx
```

- 16 deterministic source mutations were injected — one per control
  type, chosen by stable hashing.
- **All 16 exception codes** appear in the **Exceptions** sheet (the
  reference dataset produces 18 rows: two mutations legitimately trip a
  second control).
- Each row carries the `entity_type` / `entity_id`, `business_date`,
  `exception_amount_eur`, `age_days` and `control_source` needed to
  investigate a specific object.

The key point to say out loud: **the anomalies were injected into source
records, not into the exception mart.** The controls found them.

`make finance-report-scenarios` runs both states back to back if you
want to show the transition live.

---

## Step 4 — Airflow (1–2 min)

```bash
make airflow-acceptance
```

Open the `finance_reconciliation_pipeline` DAG:

```text
generate_private_sources → load_private_raw + load_ecb_reference_raw →
ingestion_complete → dbt_staging → dbt_intermediate → dbt_marts →
validate_reconciliation → export_finance_report → pipeline_complete
```

Points to make: Airflow orchestrates the existing CLI, dbt and
validators — no Finance SQL lives in the DAG. `export_finance_report`
is gated behind `validate_reconciliation`, so a report is never
published for a run the pipeline considers invalid.

```bash
make airflow-workflow-acceptance
```

runs the DAG **twice with no database reset** and checks that RAW row
counts are unchanged, the clean reconciliation still holds, and the
report is still valid — operational idempotency.

Skip the Airflow metadata database; it is not interesting.

---

## Step 5 — CI (1 min)

Open the repository's **Actions** tab (or `.github/workflows/ci.yml`):

| Job | Proves |
| --- | --- |
| `quality` | lint + unit tests + contract alignment |
| `finance-integration` | full M0–M5 acceptance on a fresh PostgreSQL + the anomaly report with all 16 codes |
| `airflow-integration` | the DAG runs twice on a clean runner |

Every pull request must go green on a from-scratch Ubuntu machine before
merge.

---

## Talking points

**Why dbt?** All reconciliation logic is versioned SQL with lineage,
tests, and contracts. Business rules are reviewable and reproducible, not
hidden in scripts.

**Why Airflow?** To orchestrate the existing components in order with
retries and idempotency — and to keep orchestration cleanly separate
from Finance logic.

**Why anomaly injection?** It gives every control a known expected
answer. `clean` must produce 0 exceptions; `with_anomalies` must produce
all 16. That makes the pipeline testable end to end, deterministically,
in CI.

**Why Excel?** The real downstream consumer for an operational Finance
team is a spreadsheet, not another app. It is presentation only —
recomputing nothing — which keeps the system-of-record in dbt.

**Why deterministic synthetic data?** Real Finance data cannot go in a
portfolio repo. A deterministic synthetic ecosystem, built specifically
to exercise the controls, is a strength: same inputs → same outputs →
CI can assert exact results.

**Why no Kafka / Spark / Kubernetes?** The problem is batch-oriented,
moderate-scale Finance reconciliation. Streaming or distributed compute
would add complexity without solving a real requirement here. Scale is
handled by customer / subscription volume in the generator, not by
pretending to be big data.

**Honest framing.** This is a portfolio project on synthetic data. It is
not production-deployed and processes no real company data. The scope
exclusions (IFRS 15, VAT, fraud, full GL close, …) are deliberate.
