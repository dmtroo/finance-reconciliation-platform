from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def parse_text(
    value: str,
) -> str | None:
    if value == "":
        return None

    return value


def parse_integer(
    value: str,
) -> int | None:
    if value == "":
        return None

    return int(value)


def parse_boolean(
    value: str,
) -> bool | None:
    if value == "":
        return None

    normalized = value.lower()

    if normalized == "true":
        return True

    if normalized == "false":
        return False

    raise ValueError(
        f"Invalid boolean value: {value!r}"
    )


def parse_date(
    value: str,
) -> date | None:
    if value == "":
        return None

    return date.fromisoformat(
        value
    )


def parse_timestamp(
    value: str,
) -> datetime | None:
    if value == "":
        return None

    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        raise ValueError(
            "Technical timestamps must be timezone-aware"
        )

    return parsed


def parse_decimal(
    value: str,
) -> Decimal | None:
    if value == "":
        return None

    return Decimal(value)


PARSERS = {
    "text": parse_text,
    "integer": parse_integer,
    "boolean": parse_boolean,
    "date": parse_date,
    "timestamp": parse_timestamp,
    "decimal": parse_decimal,
}


def parse_value(
    kind: str,
    value: str,
) -> Any:
    try:
        parser = PARSERS[kind]
    except KeyError as exc:
        raise ValueError(
            f"Unknown parser kind: {kind}"
        ) from exc

    return parser(value)