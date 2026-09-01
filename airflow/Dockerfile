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

RUN pip install \
    --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    -e /opt/airflow/project
