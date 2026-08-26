from __future__ import annotations

import os
from dataclasses import dataclass

import psycopg
from dotenv import load_dotenv

from finance_reconciliation.paths import PROJECT_ROOT


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def load_database_config() -> DatabaseConfig:
    load_dotenv(
        PROJECT_ROOT / ".env"
    )

    return DatabaseConfig(
        host=os.getenv(
            "POSTGRES_HOST",
            "localhost",
        ),
        port=int(
            os.getenv(
                "POSTGRES_PORT",
                "5432",
            )
        ),
        dbname=os.getenv(
            "POSTGRES_DB",
            "finance_reconciliation",
        ),
        user=os.getenv(
            "POSTGRES_USER",
            "finance",
        ),
        password=os.getenv(
            "POSTGRES_PASSWORD",
            "finance_local_only",
        ),
    )


def connect():
    config = load_database_config()

    return psycopg.connect(
        host=config.host,
        port=config.port,
        dbname=config.dbname,
        user=config.user,
        password=config.password,
        application_name=(
            "finance_reconciliation_loader"
        ),
    )