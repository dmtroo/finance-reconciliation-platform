FROM apache/airflow:3.3.1-python3.13

ARG AIRFLOW_VERSION=3.3.1

# Installed at the same path the full repo is bind-mounted to at
# runtime (see docker-compose.airflow.yml: .:/opt/airflow/project).
# The -e install makes finance_reconciliation.paths.PROJECT_ROOT
# resolve to /opt/airflow/project, so relative paths (generator
# config, fixtures, data/generated, .env) match the live mount
# instead of a build-time-only copy.
COPY --chown=airflow:root \
    pyproject.toml \
    README.md \
    /opt/airflow/project/

COPY --chown=airflow:root \
    src \
    /opt/airflow/project/src

# The [dbt] extra pulls in dbt-postgres so the finance_reconciliation_pipeline
# DAG's dbt_* tasks (airflow/run_dbt.py) can build the reconciliation layers.
RUN pip install \
    --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    -e "/opt/airflow/project[dbt]"
