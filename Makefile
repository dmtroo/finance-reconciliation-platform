SHELL := /bin/bash

.PHONY: load-run help test lint validate-contract postgres-up postgres-down postgres-reset dbt-profile dbt-debug dbt-source-freshness dbt-test-sources

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