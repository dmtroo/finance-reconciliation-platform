# M1 Acceptance — Synthetic Sources and RAW Ingestion

M1 is complete when the repository can reproducibly generate the clean
synthetic source ecosystem, ingest all private-system extracts, ingest
ECB reference FX observations, and validate all 10 RAW source tables.

## Scope

M1 validates source generation and ingestion only.

It does not perform reconciliation, FX normalization, exception
classification, or finance mart construction. Those responsibilities
belong to later dbt layers.

## Clean local acceptance

The acceptance workflow expects a clean local PostgreSQL RAW database.

Resetting PostgreSQL destroys the local Docker volume and must therefore
remain an explicit developer action:

```bash
make postgres-reset
make postgres-wait
make m1-acceptance
```

## Acceptance flow

The workflow performs:

1. Python linting.
2. Python unit tests.
3. Repository contract validation.
4. Deterministic clean source generation.
5. Deterministic ECB fixture extraction.
6. Synthetic RAW ingestion.
7. ECB RAW ingestion.
8. Database-to-manifest validation.
9. A second identical ingestion retry.
10. Database-to-manifest validation after the retry.
11. dbt source data tests.
12. dbt source freshness checks.

The two database validations prove that ingestion retries do not create
additional business records.

## RAW source contract

The completed M1 database contains exactly 10 RAW source tables:

- 3 Billing tables
- 4 PSP tables
- 1 Bank table
- 1 Accounting table
- 1 ECB table

Synthetic financial amounts remain in integer minor units in RAW.

ECB observations preserve the source orientation:

`units_per_eur = foreign currency units per 1 EUR`

EUR=1 and the inverse EUR-per-unit representation are not created in RAW.
Those are staging-layer responsibilities.

## Source tests versus reconciliation controls

dbt source tests validate source identity, required values, accepted
domains, uniqueness, and freshness.

They intentionally do not replace finance reconciliation controls.

Business mismatches such as missing settlements, amount mismatches,
missing ledger postings, or FX outliers must be allowed to land in RAW
and will be classified by downstream finance control models.

## M1 exit criteria

M1 is complete only when:

`make m1-acceptance`

finishes successfully on a freshly reset local PostgreSQL database.

After M1 is complete, development proceeds to M2: dbt staging models.