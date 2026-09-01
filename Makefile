SHELL := /bin/bash

M1_START_DATE ?= 2026-01-01
M1_END_DATE ?= 2026-01-31

M1_RUN_DIR ?= data/generated/SYN-42-2026-01-01-2026-01-31-clean

M1_ECB_RAW ?= data/external/ecb/m1_raw_fixture.csv
M1_ECB_REFERENCE ?= data/external/ecb/m1_reference_fixture.csv

M5_START_DATE ?= 2026-01-01
M5_END_DATE ?= 2026-01-31

M5_CONFIG ?= generator/config.with_anomalies.yml
M5_RUN_DIR ?= data/generated/SYN-42-2026-01-01-2026-01-31-with_anomalies

M5_ECB_RAW ?= data/external/ecb/m5_raw_fixture.csv
M5_ECB_REFERENCE ?= data/external/ecb/m5_reference_fixture.csv
M5_ANOMALY_RUN_DIR ?= data/generated/SYN-42-2026-01-01-2026-01-31-with_anomalies

.PHONY: m5-acceptance m5-validate m4-acceptance m4-validate dbt-build-marts m3-acceptance m3-validate dbt-build-intermediate m2-acceptance m2-validate dbt-build-staging m1-acceptance m1-validate dbt-build-all postgres-wait load-run help test lint validate-contract postgres-up postgres-down postgres-reset dbt-profile dbt-debug dbt-source-freshness dbt-test-sources

help:
	@echo "Available targets:"
	@echo "  validate-contract       Check DDL/dbt/generator contract alignment"
	@echo "  postgres-up            Start local PostgreSQL"
	@echo "  postgres-down          Stop local PostgreSQL"
	@echo "  postgres-reset         Destroy local DB volume and recreate RAW schemas (destructive)"
	@echo "  dbt-profile            Copy profiles.yml.example to local profiles.yml"
	@echo "  dbt-debug              Validate dbt connection"
	@echo "  dbt-source-freshness   Run source freshness checks"
	@echo "  dbt-test-sources       Run dbt data tests only on sources"
	@echo "  test                    Run Python tests"
	@echo "  lint                    Run Python lint checks"
	@echo "  dbt-build-staging       Build and test all dbt staging models"
	@echo "  m2-validate             Validate the M2 staging contract"
	@echo "  m2-acceptance           Run the complete M2 acceptance workflow"
	@echo "  dbt-build-intermediate  Build and test all dbt intermediate models"
	@echo "  m3-validate             Validate the M3 intermediate finance contract"
	@echo "  m3-acceptance           Run the complete M3 acceptance workflow"
	@echo "  dbt-build-marts         Build and test all dbt reconciliation marts"
	@echo "  m4-validate             Validate the M4 reconciliation mart contract"
	@echo "  m4-acceptance           Run the complete M4 reconciliation acceptance workflow"
	@echo "  m5-validate             Validate that injected source anomalies surface as Finance exceptions"
	@echo "  m5-acceptance           Rebuild from a clean DB with the with_anomalies scenario and validate M5"

validate-contract:
	python scripts/validate_contract.py

postgres-up:
	docker compose up -d postgres

postgres-down:
	docker compose down

postgres-reset:
	docker compose down -v
	docker compose up -d postgres

dbt-profile:
	@test ! -f dbt/profiles.yml || (echo "dbt/profiles.yml already exists" && exit 1)
	cp dbt/profiles.yml.example dbt/profiles.yml

# Run these from the dbt project directory while keeping credentials in env vars / .env.
dbt-debug:
	cd dbt && DBT_PROFILES_DIR=. dbt debug

dbt-source-freshness:
	cd dbt && DBT_PROFILES_DIR=. dbt source freshness

dbt-test-sources:
	cd dbt && DBT_PROFILES_DIR=. dbt test --select "source:*"

test:
	pytest

lint:
	ruff check src tests scripts

load-run:
	@test -n "$(RUN_DIR)" || (echo "Usage: make load-run RUN_DIR=<path>" && exit 1)
	finance-recon load --run-dir "$(RUN_DIR)"

postgres-wait:
	@echo "Waiting for PostgreSQL..."
	@until docker compose exec -T postgres sh -lc 'pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' >/dev/null 2>&1; do sleep 1; done
	@echo "PostgreSQL is ready."

m1-validate:
	python scripts/validate_m1.py \
		--run-dir "$(M1_RUN_DIR)" \
		--ecb-file "$(M1_ECB_RAW)"

m1-acceptance:
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) validate-contract
	finance-recon generate
	finance-recon ecb-extract \
		--start-date "$(M1_START_DATE)" \
		--end-date "$(M1_END_DATE)" \
		--mode fixture \
		--raw-output "$(M1_ECB_RAW)" \
		--reference-output "$(M1_ECB_REFERENCE)"
	finance-recon load \
		--run-dir "$(M1_RUN_DIR)"
	finance-recon ecb-load \
		--input "$(M1_ECB_RAW)"
	$(MAKE) m1-validate
	finance-recon load \
		--run-dir "$(M1_RUN_DIR)"
	finance-recon ecb-load \
		--input "$(M1_ECB_RAW)"
	$(MAKE) m1-validate
	$(MAKE) dbt-test-sources
	$(MAKE) dbt-source-freshness

dbt-build-staging:
	cd dbt && DBT_PROFILES_DIR=. dbt build --select "path:models/staging" --indirect-selection=buildable

m2-validate:
	python scripts/validate_m2.py

m2-acceptance:
	$(MAKE) m1-acceptance
	$(MAKE) dbt-build-staging
	$(MAKE) m2-validate

dbt-build-intermediate:
	cd dbt && DBT_PROFILES_DIR=. dbt build --select "path:models/intermediate" --indirect-selection=buildable

m3-validate:
	python scripts/validate_m3.py

m3-acceptance:
	$(MAKE) m2-acceptance
	$(MAKE) dbt-build-intermediate
	$(MAKE) m3-validate

dbt-build-marts:
	cd dbt && DBT_PROFILES_DIR=. dbt build --select "path:models/marts" --indirect-selection=buildable

m4-validate:
	python scripts/validate_m4.py

m4-acceptance:
	$(MAKE) m3-acceptance
	$(MAKE) dbt-build-marts
	$(MAKE) m4-validate

dbt-build-all:
	cd dbt && DBT_PROFILES_DIR=. dbt build --indirect-selection=buildable

m5-validate:
	python scripts/validate_m5_anomalies.py \
		--run-dir "$(M5_RUN_DIR)"

# The with_anomalies scenario mutates append-mode source tables
# (financial_events, journal_lines, ...), so it must be loaded into a
# clean raw layer. Reload onto a dirty DB keeps stale rows and hides
# anomalies (append inserts are on conflict do nothing).
m5-acceptance:
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) validate-contract
	$(MAKE) postgres-reset
	$(MAKE) postgres-wait
	finance-recon generate \
		--config "$(M5_CONFIG)"
	finance-recon ecb-extract \
		--start-date "$(M5_START_DATE)" \
		--end-date "$(M5_END_DATE)" \
		--mode fixture \
		--raw-output "$(M5_ECB_RAW)" \
		--reference-output "$(M5_ECB_REFERENCE)"
	finance-recon load \
		--run-dir "$(M5_RUN_DIR)"
	finance-recon ecb-load \
		--input "$(M5_ECB_RAW)"
	$(MAKE) dbt-build-all
	$(MAKE) m5-validate

m5-anomaly-validate:
	@test -n "$(M5_ANOMALY_RUN_DIR)" || \
		(echo "M5_ANOMALY_RUN_DIR is required"; exit 1)
	python scripts/validate_m5_anomalies.py \
		--run-dir "$(M5_ANOMALY_RUN_DIR)"