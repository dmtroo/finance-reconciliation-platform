from datetime import UTC, date, datetime
from decimal import Decimal

from finance_reconciliation.generator.io import write_csv


def test_write_csv_uses_canonical_serialization(tmp_path) -> None:
    output = tmp_path / "test.csv"

    rows = [
        {
            "id": "ROW-001",
            "business_date": date(2026, 1, 2),
            "event_at": datetime(
                2026,
                1,
                2,
                10,
                30,
                tzinfo=UTC,
            ),
            "rate": Decimal("0.92000000"),
            "active": True,
            "optional": None,
        }
    ]

    count = write_csv(
        output,
        rows=rows,
        fieldnames=[
            "id",
            "business_date",
            "event_at",
            "rate",
            "active",
            "optional",
        ],
    )

    assert count == 1

    assert output.read_text(encoding="utf-8") == (
        "id,business_date,event_at,rate,active,optional\n"
        "ROW-001,2026-01-02,"
        "2026-01-02T10:30:00Z,"
        "0.92000000,true,\n"
    )