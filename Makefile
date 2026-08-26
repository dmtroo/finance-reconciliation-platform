SHELL := /bin/bash

M1_START_DATE ?= 2026-01-01
M1_END_DATE ?= 2026-01-31

M1_RUN_DIR ?= data/generated/SYN-42-2026-01-01-2026-01-31-clean

M1_ECB_RAW ?= data/external/ecb/m1_raw_fixture.csv
M1_ECB_REFERENCE ?= data/external/ecb/m1_reference_fixture.csv

.PHONY: m1-acceptance m1-validate postgres-wait load-run help test lint validate-contract postgres-up postgres-down postgres-reset dbt-profile dbt-debug dbt-source-freshness dbt-test-sources

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