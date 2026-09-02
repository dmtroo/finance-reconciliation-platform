# Finance Reconciliation Platform

An end-to-end Finance reconciliation platform for a multi-currency
subscription business. It connects Billing, PSP settlement, bank cash
receipts, accounting postings and ECB reference FX, then surfaces the
reconciliation exceptions Finance needs to investigate — automatically
and reproducibly.

The data is **synthetic and deterministic**: a generator builds a
complete, internally consistent source ecosystem so the reconciliation
controls can be exercised safely, repeatably, and with a known expected
answer.

## The Finance problem

> Can Finance explain every amount along the path
> **invoice → captured payment → PSP settlement → bank cash → accounting
> posting**, reconciled against a standardized management FX rate, and
> automatically identify the exceptions that need investigation?

Each of those steps lives in a different system, each system can
disagree with the others, and the disagreements are exactly what a
reconciliation function must find. This project builds that pipeline.

## Business flow

```text
Product
  └─ Subscription
       └─ Invoice
            └─ Payment Attempt
                 └─ Financial Event   (CAPTURE / REFUND / CHARGEBACK)
                      └─ Settlement Item
                           └─ Settlement Batch
                                └─ Bank Transaction        (actual cash)
                                └─ Accounting Journal      (GL postings)

ECB reference rates ─────────────────────────► management EUR value
```

## Source systems

| System | What it provides |
| --- | --- |
| **Billing** | products, subscriptions, invoices |
| **PSP** | payment attempts, financial events, settlement batches and items, PSP settlement FX and fees |
| **Bank** | the actual cash receipt for each payout |
| **Accounting** | journal postings for each event and settlement |
| **ECB** | standardized management / reference FX |

## Source of truth

| Concept | Authoritative system |
| --- | --- |
| Product / subscription / invoice | Billing |
| Payment outcome (capture / refund / chargeback) | PSP |
| PSP fee / payout / PSP FX | PSP settlement |
| Actual cash received | Bank |
| Accounting postings | Accounting |
| Standardized management FX | ECB |

**Sources never silently overwrite each other.** When two authoritative
systems disagree, the disagreement is preserved through the warehouse
and becomes a reconciliation exception rather than being smoothed away.

## Architecture

```text
Synthetic private sources          External source
Billing / PSP / Bank / Accounting  ECB extractor (fixture in CI)
                │                         │
                ▼                         ▼
        Python ingestion  (extraction + idempotent load only)
                │
                ▼
        PostgreSQL RAW   (raw_billing / raw_psp / raw_bank / raw_accounting / raw_ecb)
                │
                ▼   dbt
     staging ──► intermediate ──► facts / marts
                                     │
                                     ▼
                       Finance validation (M4 contract)
                                     │
                                     ▼
                       Excel report  (Daily Summary + Exceptions)

Airflow ─────────► orchestrates the components above (no Finance SQL)
GitHub Actions ──► validates the repository on every pull request
```

## Data layers

| Layer | Contains |
| --- | --- |
| **RAW** | exactly what the source system said, including bad-but-real rows |
| **Staging** | one cleaned, typed view per RAW table — rename/cast, minor units → `NUMERIC(18,2)`, UTC timestamps, event sign convention. Only staging may call `source()` |
| **Intermediate** | cross-system wiring and reusable Finance logic — as-of FX, capture lifecycle, payment→settlement matching, settlement→bank matching, accounting matching |
| **Facts** | the full reconciliation picture on a stable grain |
| **Marts** | Finance-facing outputs |

## Final marts

| Model | Grain | Purpose |
| --- | --- | --- |
| `fct_payment_reconciliation` | one successful capture | invoice → payment → settlement → accounting context and control outcomes |
| `fct_settlement_reconciliation` | one PSP settlement | settlement header/items → bank cash → accounting |
| `mart_reconciliation_exceptions` | one reconciliation exception | the Finance investigation queue |
| `mart_finance_daily` | business_date × product × currency | daily reconciliation KPI monitoring |

## Exception taxonomy

16 frozen control codes across six groups:

| Group | Codes |
| --- | --- |
| Payment lifecycle | `MISSING_CAPTURE`, `CAPTURE_AMOUNT_MISMATCH`, `DUPLICATE_CAPTURE`, `INVALID_REFUND`, `OVER_REFUND` |
| Settlement | `MISSING_SETTLEMENT`, `LATE_SETTLEMENT`, `SETTLEMENT_TOTAL_MISMATCH` |
| Bank | `MISSING_BANK_RECEIPT`, `BANK_AMOUNT_MISMATCH` |
| Accounting | `MISSING_LEDGER_POSTING`, `LEDGER_AMOUNT_MISMATCH`, `UNBALANCED_JOURNAL` |
| FX | `MISSING_FX_RATE`, `FX_RATE_OUTLIER` |
| Product mapping | `UNMAPPED_PRODUCT` |

Business meaning, trigger conditions and status/severity policy for each:
see [`docs/finance-reconciliation-controls.md`](docs/finance-reconciliation-controls.md).

## Deterministic anomaly testing

| Scenario | Injected anomalies | Distinct exception codes | Result |
| --- | --- | --- | --- |
| `clean` | 0 | 0 | fully reconciled, 100% amount reconciliation rate |
| `with_anomalies` | 16 deterministic source mutations | 16 | every control type triggered downstream |

**Anomalies are injected into source records, not into the exception
mart.** `with_anomalies` starts from a valid clean dataset and applies
one deterministic mutation per control, selected by stable hashing of
`(seed, anomaly_type, ordinal)`. The exception mart may hold more than
16 rows because one source mutation can legitimately trip more than one
control.

## Orchestration (Airflow)

`finance_reconciliation_pipeline` DAG:

```text
generate sources ─► load RAW + ECB ─► dbt staging ─► dbt intermediate ─►
dbt marts ─► validate reconciliation ─► export finance report ─► done
```

Airflow orchestrates the existing `finance-recon` CLI, dbt and the
validators. It contains no Finance SQL. `export finance report` runs
only after `validate reconciliation` passes, so Finance never receives a
report the pipeline already considers invalid.

## Idempotency

Same `seed` + config + catalog + FX input → the same source data.
Ingestion is idempotent on natural source keys, so repeated loads add no
duplicate business rows. Running the DAG twice with no database reset
leaves RAW row counts unchanged and the clean Finance result unchanged.

## Continuous integration

`.github/workflows/ci.yml` — one workflow, three jobs, on every pull
request and on `main`:

| Job | Proves |
| --- | --- |
| `quality` | lint, unit tests, repository contract alignment |
| `finance-integration` | full M0–M5 acceptance on a fresh PostgreSQL, plus the anomaly-state report showing all 16 exception codes |
| `airflow-integration` | the DAG runs twice on a clean runner — RAW idempotency, clean reconciliation, clean report |

See [`docs/m6-ci.md`](docs/m6-ci.md).

## Finance report

`finance-recon report-export` reads the current marts and writes
`reports/exports/finance_reconciliation_report.xlsx`:

| Sheet | Use |
| --- | --- |
| **Daily Summary** | one row per `mart_finance_daily` row — daily KPI view |
| **Exceptions** | one row per `mart_reconciliation_exceptions` row — investigation queue, with the identifiers to chase a specific invoice / payment / settlement |

The workbook is **presentation only**. All reconciliation logic stays in
dbt; the export never recomputes anything. Clean DB → clean workbook;
anomaly DB → the same export shows the exception rows. See
[`docs/m6-finance-reporting.md`](docs/m6-finance-reporting.md).

## Tech stack

Python · PostgreSQL · dbt · Apache Airflow · Docker Compose ·
GitHub Actions · `openpyxl`. The project optimizes for auditability and
maintainability, not tool count.

## How to run

Prerequisites: Docker, Python 3.13, `pip install -e ".[dbt,dev]"`,
`cp .env.example .env`, `make dbt-profile`.

**Finance reconciliation (M0–M5), clean + anomaly:**

```bash
make m5-acceptance
```

**The report, both mart states:**

```bash
make finance-report-scenarios
```

**Airflow orchestration end to end:**

```bash
make airflow-acceptance             # build + start + DAG contract
make airflow-workflow-acceptance    # run the DAG twice + all validators
```

## Demo dataset

The CI / local profile generates a ~30-day window: 6 products,
~4,700 subscriptions, ~4,200 invoices, ~4,500 payment attempts,
~4,300 financial events, 34 settlement batches, ~8,600 journal lines.
The demo profile in `generator/SPEC.md` scales to ~100k–250k invoices
over a year through customer volume, not row duplication.

## Out of scope (by design)

IFRS 15 revenue recognition, deferred revenue, a VAT engine, fraud
scoring, churn / customer analytics, a full ERP / general ledger, tax
jurisdiction handling, PSP dispute fees, PII. These are deliberate scope
controls.

## Documentation

| Topic | Document |
| --- | --- |
| Why the system is built this way | [`docs/architecture.md`](docs/architecture.md) |
| The 16 reconciliation controls | [`docs/finance-reconciliation-controls.md`](docs/finance-reconciliation-controls.md) |
| 5–10 minute walkthrough | [`docs/demo-guide.md`](docs/demo-guide.md) |
| RAW source contract | [`docs/source-data-contract.md`](docs/source-data-contract.md) |
| Generator specification | [`generator/SPEC.md`](generator/SPEC.md) |
| Anomaly injection & validation | [`docs/m5-anomaly-validation.md`](docs/m5-anomaly-validation.md) |
| Airflow workflow validation | [`docs/m6-airflow-workflow-validation.md`](docs/m6-airflow-workflow-validation.md) |
| Continuous integration | [`docs/m6-ci.md`](docs/m6-ci.md) |
| Finance reporting export | [`docs/m6-finance-reporting.md`](docs/m6-finance-reporting.md) |
| Per-milestone acceptance contracts | `docs/m1-acceptance.md` … `docs/m5-acceptance.md` |
