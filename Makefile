SHELL := /bin/bash

M1_START_DATE ?= 2026-01-01
M1_END_DATE ?= 2026-01-31

M1_RUN_DIR ?= data/generated/SYN-42-2026-01-01-2026-01-31-clean

M1_ECB_RAW ?= data/external/ecb/m1_raw_fixture.csv
M1_ECB_REFERENCE ?= data/external/ecb/m1_reference_fixture.csv

M5_CLEAN_RUN_DIR ?= data/generated/SYN-42-2026-01-01-2026-01-31-clean
M5_ANOMALY_CONFIG ?= generator/config.with_anomalies.yml
M5_ANOMALY_RUN_DIR ?= data/generated/SYN-42-2026-01-01-2026-01-31-with_anomalies
M5_ECB_FIXTURE ?= generator/fixtures/ecb_raw_ci_rates.csv

AIRFLOW_COMPOSE := docker compose -f docker-compose.airflow.yml
AIRFLOW_UID ?= $(shell id -u)

.PHONY: final-acceptance final-quality-check final-finance-check final-airflow-check finance-report-scenarios finance-report-acceptance finance-report-validate finance-report-export airflow-workflow-acceptance airflow-reconciliation-check airflow-workflow-validate airflow-acceptance airflow-wait airflow-pipeline-check airflow-build airflow-reset airflow-down airflow-smoke airflow-logs airflow-ps airflow-init airflow-up m5-acceptance m5-validate m5-anomaly-validate m5-anomaly-pipeline m4-acceptance m4-validate dbt-build-marts m3-acceptance m3-validate dbt-build-intermediate m2-acceptance m2-validate dbt-build-staging m1-acceptance m1-validate postgres-wait load-run help test lint validate-contract postgres-up postgres-down postgres-reset dbt-profile dbt-debug dbt-source-freshness dbt-test-sources

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
	@echo "  m5-validate             Validate the deterministic clean vs with_anomalies generator scenarios"
	@echo "  m5-anomaly-validate     Validate that injected source anomalies surface as Finance exceptions"
	@echo "  m5-acceptance           Run the complete M5 anomaly acceptance workflow"
	@echo "  airflow-pipeline-check  Validate the M6 Airflow reconciliation pipeline DAG contract"
	@echo "  airflow-acceptance      Rebuild, start, and validate the M6 Airflow pipeline DAG"
	@echo "  airflow-workflow-validate     Run the M6 pipeline DAG twice and check RAW idempotency + clean reconciliation"
	@echo "  airflow-reconciliation-check  airflow-smoke + airflow-pipeline-check + airflow-workflow-validate"
	@echo "  airflow-workflow-acceptance   Business-DB clean room, then airflow-reconciliation-check"
	@echo "  finance-report-export         Export the Finance Excel report from the current marts"
	@echo "  finance-report-validate       Check the exported report matches the marts"
	@echo "  finance-report-acceptance     finance-report-export + finance-report-validate (marts must exist)"
	@echo "  finance-report-scenarios      Build clean then anomaly marts and export/validate the report for each"
	@echo "  final-acceptance              One command: repository quality + Finance + Airflow end-to-end acceptance"

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
	@# -h 127.0.0.1 + a real query force a TCP client path: during a
	@# fresh initdb the temporary server listens on the unix socket only,
	@# so a socket pg_isready reports ready before the port clients
	@# actually use is accepting connections.
	@until docker compose exec -T postgres sh -lc 'pg_isready -h 127.0.0.1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' >/dev/null 2>&1; do sleep 1; done
	@until docker compose exec -T postgres sh -lc 'psql -h 127.0.0.1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -tAc "select 1"' >/dev/null 2>&1; do sleep 1; done
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

m5-anomaly-validate:
	@test -n "$(M5_ANOMALY_RUN_DIR)" || \
		(echo "M5_ANOMALY_RUN_DIR is required"; exit 1)
	python scripts/validate_m5_anomalies.py \
		--run-dir "$(M5_ANOMALY_RUN_DIR)"

m5-validate:
	python scripts/validate_m5.py \
		--clean-run-dir "$(M5_CLEAN_RUN_DIR)" \
		--anomaly-run-dir "$(M5_ANOMALY_RUN_DIR)"

m5-anomaly-pipeline:
	finance-recon generate \
		--config "$(M5_ANOMALY_CONFIG)"
	$(MAKE) postgres-reset
	$(MAKE) postgres-wait
	finance-recon load \
		--run-dir "$(M5_ANOMALY_RUN_DIR)"
	finance-recon ecb-load \
		--input "$(M5_ECB_FIXTURE)"
	$(MAKE) dbt-build-staging
	$(MAKE) dbt-build-intermediate
	$(MAKE) dbt-build-marts
	$(MAKE) m5-anomaly-validate \
		M5_ANOMALY_RUN_DIR="$(M5_ANOMALY_RUN_DIR)"

m5-acceptance:
	$(MAKE) postgres-reset
	$(MAKE) postgres-wait
	$(MAKE) m4-acceptance
	$(MAKE) m5-anomaly-pipeline
	$(MAKE) m5-validate

airflow-init:
	AIRFLOW_UID="$(AIRFLOW_UID)" \
	$(AIRFLOW_COMPOSE) up airflow-init

airflow-up:
	AIRFLOW_UID="$(AIRFLOW_UID)" \
	$(AIRFLOW_COMPOSE) up -d \
		airflow-api-server \
		airflow-scheduler \
		airflow-dag-processor

airflow-ps:
	$(AIRFLOW_COMPOSE) ps

airflow-logs:
	$(AIRFLOW_COMPOSE) logs -f \
		airflow-api-server \
		airflow-scheduler \
		airflow-dag-processor

airflow-smoke:
	python scripts/validate_airflow_runtime.py

airflow-down:
	$(AIRFLOW_COMPOSE) stop \
		airflow-api-server \
		airflow-scheduler \
		airflow-dag-processor \
		airflow-postgres

airflow-reset:
	$(AIRFLOW_COMPOSE) down \
		-v \
		--remove-orphans

airflow-build:
	AIRFLOW_UID="$(AIRFLOW_UID)" \
	$(AIRFLOW_COMPOSE) build

airflow-pipeline-check:
	python scripts/validate_airflow_pipeline_dag.py

airflow-wait:
	@echo "Waiting for Airflow services to become healthy..."
	@for svc in airflow-api-server airflow-scheduler airflow-dag-processor; do \
		printf '  %s' "$$svc"; \
		until [ "$$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' \
			$$($(AIRFLOW_COMPOSE) ps -q $$svc 2>/dev/null) 2>/dev/null)" = "healthy" ]; do \
			printf '.'; sleep 3; \
		done; \
		printf ' healthy\n'; \
	done

# airflow-pipeline-check and airflow-smoke only check an already-running
# stack (like m1-validate etc. check an already-built DB/dbt state), so
# this brings the stack up from a clean slate before checking it.
airflow-acceptance:
	$(MAKE) airflow-reset
	$(MAKE) airflow-build
	$(MAKE) airflow-init
	$(MAKE) airflow-up
	$(MAKE) airflow-wait
	$(MAKE) airflow-smoke
	$(MAKE) airflow-pipeline-check

airflow-workflow-validate:
	python scripts/validate_airflow_workflow.py

# Runtime health + DAG structure + real repeated execution. Assumes the
# Airflow stack is already up.
airflow-reconciliation-check:
	$(MAKE) airflow-smoke
	$(MAKE) airflow-pipeline-check
	$(MAKE) airflow-workflow-validate

# Business-DB clean room, then the full reconciliation check. Airflow
# metadata is deliberately kept (the workflow validator uses its own
# run ids), so no airflow-reset here.
airflow-workflow-acceptance:
	$(MAKE) postgres-reset
	$(MAKE) postgres-wait
	$(MAKE) airflow-up
	$(MAKE) airflow-wait
	$(MAKE) airflow-reconciliation-check

finance-report-export:
	finance-recon report-export

finance-report-validate:
	python scripts/validate_finance_report.py

# Downstream Excel consumer. Precondition: the reconciliation marts are
# already built (orchestrated by m4/m5 acceptance or the Airflow DAG).
finance-report-acceptance:
	$(MAKE) finance-report-export
	$(MAKE) finance-report-validate

# One export mechanism, both mart states. Same output file is
# overwritten each time.
#   clean marts   -> export -> Exceptions = 0
#   anomaly marts -> export -> Exceptions rows = mart rows, all 16 codes
finance-report-scenarios:
	$(MAKE) postgres-reset
	$(MAKE) postgres-wait
	$(MAKE) m4-acceptance
	finance-recon report-export
	python scripts/validate_finance_report.py --scenario clean
	$(MAKE) m5-anomaly-pipeline
	finance-recon report-export
	python scripts/validate_finance_report.py --scenario with_anomalies

# --- Final project acceptance ---------------------------------------------
# One canonical end-to-end command. Phases run strictly sequentially
# because the Finance and Airflow acceptance targets each reset the
# business PostgreSQL. Each phase reuses existing targets - no validation
# logic is re-implemented here.

# Phase 1: repository health. Fast; fails before any Docker work.
final-quality-check:
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) validate-contract

# Phase 2: Finance reconciliation without orchestration - clean
# (0 exceptions, 100% reconciliation) and with_anomalies (16 injections,
# all 16 control codes). m5-acceptance owns its own DB reset.
final-finance-check:
	$(MAKE) m5-acceptance

# Phase 3: build the Airflow runtime from repository state on a clean
# metadata DB, then prove the DAG contract and a repeated real workflow.
# airflow-workflow-acceptance already resets the business DB, runs
# airflow-smoke + airflow-pipeline-check, triggers the DAG twice, and
# runs the M4 + report validators - so they are not repeated here.
final-airflow-check:
	$(MAKE) airflow-reset
	$(MAKE) airflow-build
	$(MAKE) airflow-init
	$(MAKE) airflow-workflow-acceptance

final-acceptance:
	$(MAKE) final-quality-check
	$(MAKE) final-finance-check
	$(MAKE) final-airflow-check
	@echo
	@echo "Final project acceptance passed."
	@echo
	@echo "  Repository quality:                  passed."
	@echo "  Finance clean/anomaly acceptance:    passed."
	@echo "  Airflow runtime and DAG contract:    passed."
	@echo "  Airflow repeated workflow:           passed."
	@echo "  Finance reporting export:            passed."
	@echo
	@echo "Airflow is left running (http://localhost:8081). Clean up with: make airflow-reset"