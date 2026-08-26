# Development workflow

## Repository strategy

The project is developed in small vertical milestones rather than as one large code dump. Every
milestone should leave the repository in a coherent state and include validation appropriate to the
layer being added.

Recommended workflow:

1. Branch from `main` with a focused branch name, for example `feat/raw-source-contract`.
2. Make one conceptual change at a time.
3. Run local validation before opening a pull request.
4. Open a PR with business context, implementation notes, and evidence of tests.
5. Merge only after CI checks pass.

Do not develop directly on `main` once the remote repository is created.

## Planned milestones

### M0 — bootstrap and source contract

- Repository structure.
- Local PostgreSQL.
- Versioned RAW DDL.
- dbt project shell and source declarations.
- Source-level contract tests and freshness.
- Machine-readable generator specification.

### M1 — synthetic sources and ingestion

- Implement deterministic generator.
- Add ECB extractor with CI fixture mode.
- Add idempotent loaders and load audit metadata.
- Prove retry safety.

### M2 — dbt staging

- One staging model per RAW table.
- Currency/minor-unit conversion.
- Event sign convention.
- Source-local conditional data tests.

### M3 — intermediate finance logic

- FX as-of lookup.
- Invoice/payment lifecycle.
- Payment-to-settlement matching.
- Settlement-to-bank matching.
- Accounting matching.

### M4 — marts and controls

- `fct_payment_reconciliation`.
- `fct_settlement_reconciliation`.
- `mart_reconciliation_exceptions`.
- `mart_finance_daily`.
- Data tests, unit tests, contracts, and stored failures where useful.

### M5 — Airflow

- Extraction/load DAG.
- Source freshness before transformations.
- `dbt build` orchestration.
- Retry/backfill behavior.
- Critical-failure path and reporting.

### M6 — CI/CD

- GitHub Actions.
- PR checks.
- SQL/Python linting.
- Clean + anomaly integration test profiles.
- Architecture/lineage screenshots and final README narrative.

## Commit examples

Keep commits useful to reviewers rather than narrating every keystroke:

```text
chore: bootstrap local development environment
feat: define raw source schemas and tables
feat: declare dbt sources and freshness SLAs
docs: specify deterministic synthetic source generator
```

## Pull request principle

A PR should explain **why** the data behavior changes. A schema change without a corresponding source
contract/documentation update is incomplete.
