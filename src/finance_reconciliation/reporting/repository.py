"""Read the finished reconciliation marts for the Finance report.

Only two relations are touched - `mart_finance_daily` and
`mart_reconciliation_exceptions`. The same database configuration
contract the generator, ingestion and validators use is reused via
`finance_reconciliation.ingestion.database.connect`.
"""

from __future__ import annotations

import os

from psycopg import sql

from finance_reconciliation.ingestion.database import connect
from finance_reconciliation.reporting.models import (
    DAILY_SUMMARY_FIELDS,
    EXCEPTION_FIELDS,
    DailySummaryRow,
    ExceptionRow,
    FinanceReportData,
)

DAILY_RELATION = "mart_finance_daily"
EXCEPTION_RELATION = "mart_reconciliation_exceptions"


def _analytics_schema(
    analytics_schema: str | None,
) -> str:
    if analytics_schema:
        return analytics_schema

    return os.getenv(
        "DBT_SCHEMA",
        "analytics_dev",
    )


def _select(
    *,
    schema: str,
    relation: str,
    columns: tuple[str, ...],
    order_by: sql.Composable,
) -> sql.Composed:
    column_list = sql.SQL(", ").join(
        sql.Identifier(name)
        for name in columns
    )

    return sql.SQL(
        "select {columns} from {schema}.{relation} order by {order_by}"
    ).format(
        columns=column_list,
        schema=sql.Identifier(schema),
        relation=sql.Identifier(relation),
        order_by=order_by,
    )


def load_finance_report_data(
    *,
    analytics_schema: str | None = None,
) -> FinanceReportData:
    schema = _analytics_schema(
        analytics_schema
    )

    daily_query = _select(
        schema=schema,
        relation=DAILY_RELATION,
        columns=DAILY_SUMMARY_FIELDS,
        # Grain order; product_id is nullable in the mart.
        order_by=sql.SQL(
            "business_date, product_id nulls first, currency"
        ),
    )

    exception_query = _select(
        schema=schema,
        relation=EXCEPTION_RELATION,
        columns=EXCEPTION_FIELDS,
        # Finance-friendly: worst severity first, then a stable key.
        order_by=sql.SQL(
            "case severity "
            "when 'CRITICAL' then 0 "
            "when 'WARNING' then 1 "
            "when 'INFO' then 2 "
            "else 3 end, "
            "exception_code, business_date, entity_type, entity_id"
        ),
    )

    with (
        connect() as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(daily_query)
        daily_rows = tuple(
            DailySummaryRow(*row)
            for row in cursor.fetchall()
        )

        cursor.execute(exception_query)
        exception_rows = tuple(
            ExceptionRow(*row)
            for row in cursor.fetchall()
        )

    return FinanceReportData(
        daily=daily_rows,
        exceptions=exception_rows,
    )
