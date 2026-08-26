# Architecture v1

## Goal

Build a small but production-like finance reconciliation data product for a multi-currency SaaS
business. The system explains money across Billing, PSP events, PSP settlements, Bank, and Accounting,
with ECB FX used for standardized EUR management reporting.

## Boundaries

```text
Synthetic private sources                 External source
Billing / PSP / Bank / Accounting         ECB API
            |                                |
            | Python ingestion               | ECB extractor
            v                                v
+-------------------------------------------------------------+
| PostgreSQL RAW: source-aligned schemas                       |
| raw_billing / raw_psp / raw_bank / raw_accounting / raw_ecb |
+-----------------------------+-------------------------------+
                              |
                              | dbt
                              v
                    staging -> intermediate -> marts
                              |
                              v
                 finance reconciliation outputs
```

Airflow will orchestrate extraction/load, source freshness, dbt build, controls, and report
publication in a later milestone. It will not contain finance transformation SQL.

## Layer responsibilities

### RAW

Faithful source landing. Keeps bad-but-real rows for audit. PostgreSQL enforces source identity and
ingestion metadata, not cross-system finance rules.

### Staging

Source-conformed cleanup only: rename/cast, minor units to decimal money, timestamp normalization,
and the canonical event sign convention. Only staging models may call `source()`.

### Intermediate

Reusable business logic: FX lookback, payment-event lifecycle, settlement matching, bank matching,
and accounting matching.

### Marts

Consumer-facing finance entities such as payment reconciliation, settlement reconciliation, daily
finance reporting, and reconciliation exceptions.

## Functional currency

EUR is the reporting/functional currency for this project. ECB rates create a standardized management
EUR value. PSP settlement FX remains a separate business concept and is never overwritten by ECB FX.
