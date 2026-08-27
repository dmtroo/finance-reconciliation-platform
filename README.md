# Finance Reconciliation Platform

A production-like data project for automating finance reconciliation in a multi-currency
subscription business.

The project is designed around a real finance question:

> Can Finance explain the path from invoice, to captured payment, to PSP settlement, to bank cash,
> and to accounting posting — and automatically identify the exceptions that need investigation?

## Current milestone: M0 — bootstrap and source contract

Implemented now:

- source-aligned PostgreSQL RAW schemas;
- 10-table source data contract;
- dbt project shell with source documentation, source tests, and freshness SLAs;
- deterministic synthetic-generator specification and machine-readable configuration schema;
- local Docker Compose PostgreSQL environment;
- staged development roadmap.

Not implemented yet by design:

- synthetic-data generator code;
- loaders / ECB extractor;
- dbt staging/intermediate/marts SQL;
- Airflow DAGs;
- GitHub Actions.

Those are subsequent milestones so each layer is built against a stable upstream contract.

## Architecture

```text
Billing ─┐
PSP ─────┼──> Python ingestion ──> PostgreSQL RAW ──> dbt ──> Finance marts / controls
Bank ────┤
Accounting┘

ECB API ─────> ECB extractor ────> raw_ecb ─────────^ 
```

Transformation layering follows `staging -> intermediate -> marts`. Only staging models may read
RAW sources directly.

## Repository layout

```text
.
├── infra/postgres/init/       # versioned local RAW DDL
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml.example
│   ├── models/staging/*       # source declarations now; SQL follows in M2
│   └── tests/generic/
├── generator/                 # exact synthetic-source specification
├── ingestion/                 # implementation starts in M1
├── airflow/dags/              # implementation starts in M5
├── docs/
└── data/generated/            # generated files are gitignored
```

## Local bootstrap

1. Create the local environment file:

```bash
cp .env.example .env
```

2. Start PostgreSQL:

```bash
make postgres-up
```

On the first creation of the Docker volume, PostgreSQL executes the numbered scripts in
`infra/postgres/init/` and creates the five RAW schemas and ten source tables.

3. Create a local dbt profile:

```bash
make dbt-profile
```

4. After installing the Python/dbt dependencies, validate connectivity:

```bash
make dbt-debug
```

`dbt source freshness` and source tests become meaningful after M1 loads data:

```bash
make dbt-source-freshness
make dbt-test-sources
```

## Destructive local reset

The Docker init scripts run only when the PostgreSQL volume is first initialized. During early schema
development, apply a clean rebuild with:

```bash
make postgres-reset
```

This is intentionally destructive and is for local development only. Schema changes must still be
added as new numbered SQL files rather than editing a deployed migration in place once history matters.

## Engineering principles

- RAW preserves upstream truth, including business-quality problems.
- Source tests validate shape and controlled vocabularies; reconciliation controls validate business behavior.
- Money is never stored as floating point.
- Technical timestamps are UTC; business dates remain explicit dates.
- ECB reporting FX and PSP settlement FX are distinct concepts.
- Synthetic data is deterministic and includes natural finance behavior before injected anomalies.
- The project optimizes for auditability and maintainability, not maximum tool count.

See `docs/source-data-contract.md`, `docs/architecture.md`, and `generator/SPEC.md` for the frozen M0 design.

## Local M1 acceptance

The complete synthetic-source and RAW-ingestion milestone can be
validated locally with:

```bash
make postgres-reset
make postgres-wait
make m1-acceptance
```

See `docs/m1-acceptance.md` for the acceptance contract and scope.

## Local M2 acceptance

The complete RAW-to-staging milestone can be reproduced with:

```bash
make postgres-reset
make postgres-wait
make m2-acceptance
```

M2 builds 10 dbt staging views and validates their grain, numeric types,
and source-only lineage.

See `docs/m2-acceptance.md` for the staging contract.

## Local M3 acceptance

The complete staging-to-intermediate finance milestone can be reproduced
with:

```bash
make postgres-reset
make postgres-wait
make m3-acceptance
```

M3 validates as-of FX, payment lifecycle, settlement and bank matching,
and accounting matching foundations without assigning final
reconciliation exception codes.

See `docs/m3-acceptance.md` for the intermediate-layer contract.