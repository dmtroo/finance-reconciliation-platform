# Architecture

The [README](../README.md) answers *what the project is*. This document
answers *why it is built this way*.

## System boundaries

```text
Source simulation / extraction   →   Ingestion   →   Warehouse transforms
        │                              │                    │
        ▼                              ▼                    ▼
Python generator                Python ingestion           dbt
(synthetic private-system       (extraction + load          (staging → intermediate
 extracts: Billing / PSP /       only, idempotent)           → facts / marts;
 Bank / Accounting)                                          all Finance logic)
ECB extractor                                                       │
(fixture in CI)                                                     ▼
        │                                                Finance controls
        ▼                                                (M4 acceptance contract)
                        PostgreSQL                               │
                (RAW source + analytical schemas)                ▼
                                                          Reporting
                                                          (Excel downstream consumer)

                        Airflow  →  orchestration of every component above
```

### Component responsibilities

| Component | Responsibility | Explicitly not responsible for |
| --- | --- | --- |
| Python generator | create deterministic synthetic source extracts in RAW-contract shape | computing dbt statuses; the ECB source |
| Python ingestion | extraction and idempotent loading; `_loaded_at` / `_batch_id` metadata | transformation, joins, business logic |
| dbt | all transformation and Finance reconciliation logic | orchestration, scheduling |
| PostgreSQL | source landing (RAW) and analytical storage | rejecting bad-but-real source rows |
| Airflow | orchestrating the CLI, dbt and validators in order | containing Finance SQL |
| Excel export | presenting finished mart rows | recomputing anything |

## Core design rule

```text
ingestion Python   =   extraction / loading
dbt                =   transformation / business logic
Airflow            =   orchestration
reporting          =   downstream consumption
```

Nothing crosses these lines. There is no Finance SQL in Airflow, no
business logic in the loaders, no recomputation in the report.

## RAW contract

Ten tables, five source-aligned schemas. PostgreSQL enforces only source
identity and ingestion metadata — not cross-system Finance rules.

| System | Table | Grain |
| --- | --- | --- |
| Billing | `raw_billing.products` | one product |
| Billing | `raw_billing.subscriptions` | one subscription |
| Billing | `raw_billing.invoices` | one invoice |
| PSP | `raw_psp.payment_attempts` | one attempt |
| PSP | `raw_psp.financial_events` | one CAPTURE / REFUND / CHARGEBACK |
| PSP | `raw_psp.settlements` | one payout batch |
| PSP | `raw_psp.settlement_items` | one event inside a settlement |
| Bank | `raw_bank.statement_transactions` | one bank statement line |
| Accounting | `raw_accounting.journal_lines` | one journal line |
| ECB | `raw_ecb.fx_rates` | one `(rate_date, currency)` observation |

Nine synthetic private-system tables plus one ECB table. Full column
contract in [`source-data-contract.md`](source-data-contract.md).

## Money rules

| Layer | Monetary representation |
| --- | --- |
| RAW | integer minor units (`BIGINT`) |
| Staging onward | `NUMERIC(18,2)` |
| FX rates | `NUMERIC(18,8)` |

Floating point is never used for a monetary calculation anywhere in the
pipeline, including the reporting layer.

## FX rules

- **PSP FX** orientation: EUR per one unit of transaction currency.
- **Raw ECB** orientation: foreign-currency units per 1 EUR
  (the ECB source orientation, preserved).
- **Staging ECB** inverts the raw orientation to EUR per unit for
  reporting calculations.
- **As-of FX**: use the latest available rate with
  `rate_date <= event_date` (handles weekends and holidays).
- PSP settlement FX and ECB reference FX are distinct business concepts.
  ECB never overwrites PSP FX; a large divergence between them is a
  control (`FX_RATE_OUTLIER`), not a correction.

## Missing data philosophy

**Missing is not zero.** A missing settlement, missing bank receipt or
missing journal is itself the evidence a reconciliation control needs.

Intermediate and mart models therefore `LEFT JOIN` downstream systems
and keep the absence visible (`settlement_count = 0`,
`posted_journal_entry_count = 0`, `reference_fx_rate is null`) instead of
inner-joining the missing rows away.

## Finance mismatch philosophy

> A reconciliation system should surface mismatches, not crash because
> mismatches exist.

| Failure kind | Behaviour |
| --- | --- |
| Broken schema, invalid type, missing required technical field | the pipeline fails |
| Invoice vs capture mismatch, missing settlement, bank amount mismatch, unbalanced journal | flows through to `mart_reconciliation_exceptions` |

Structural problems stop the build. Business disagreements are the
product.

## dbt layering

| Layer | Input | Contains |
| --- | --- | --- |
| staging | `source()` only — one source, no joins | rename / cast, minor units → decimal, UTC, event sign convention |
| intermediate | `ref()` only | reusable cross-system business logic |
| marts | `ref()` only | Finance-facing outputs |

Only staging models may read RAW sources. `fct_*` and `mart_*` models
never depend directly on a dbt source — the M4 validator enforces this
from the dbt manifest.

## Accounting model

A deliberately small chart of accounts:
`1100 BANK`, `1200 PSP_CLEARING`, `4000 SALES_CLEARING`,
`6100 PAYMENT_PROCESSING_FEES`, `6200 CHARGEBACK_LOSS`,
`6300 CUSTOMER_REFUNDS`.

Event journals use standardized reporting EUR (reference FX):

```text
CAPTURE     Dr PSP_CLEARING        Cr SALES_CLEARING
REFUND      Dr CUSTOMER_REFUNDS    Cr PSP_CLEARING
CHARGEBACK  Dr CHARGEBACK_LOSS     Cr PSP_CLEARING
```

Settlement journals use actual PSP EUR values:

```text
Dr BANK                     = settlement net payout
Dr PAYMENT_PROCESSING_FEES  = settlement fee
Cr PSP_CLEARING             = settlement gross amount
```

Because event journals use reporting FX and settlement journals use PSP
FX, the project does **not** assert that `PSP_CLEARING` closes to zero.
FX gain/loss accounting and a full GL close are out of v1 scope;
reconciliation validates the *expected* journal for each referenced
business object.

## Airflow

Airflow does not own Finance logic. The `finance_reconciliation_pipeline`
DAG runs, in order: the `finance-recon` CLI (`generate`, `load`,
`ecb-load`, `report-export`), `dbt build` per layer, and the M4
validator. `export_finance_report` is gated behind `validate_reconciliation`.

The production DAG always runs the **clean** scenario. Deliberate
corruption (`with_anomalies`) is M5's separate acceptance framework, not
the production pipeline — production orchestration and an intentional
fault generator are different concepts.

## Airflow vs CI

Frequently conflated; they solve different problems.

| | Airflow | GitHub Actions |
| --- | --- | --- |
| Runs | the data workflow | code / repository checks |
| Trigger | manual (`schedule=None`) | every pull request, and `main` |
| Question | "does the pipeline execute and reconcile?" | "is this change safe to merge?" |
| Environment | local Docker stack | fresh GitHub-hosted runner |

## Determinism

Same seed + config + catalog + FX input → the same source records →
the same RAW state → the same marts → the same report **content**.
The `.xlsx` is content-deterministic, not byte-deterministic (openpyxl
metadata and float round-tripping vary), so money is compared on
read-back with a `0.01` export-fidelity tolerance.

## Out of scope

IFRS 15 revenue recognition, deferred revenue, a VAT engine, fraud
scoring, churn / customer analytics, a full ERP / general ledger, tax
jurisdiction handling, PSP dispute fees, PII, streaming, distributed
compute. Each exclusion is a deliberate scope control, not missing work.
