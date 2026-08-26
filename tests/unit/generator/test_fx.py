from datetime import date
from decimal import Decimal

from finance_reconciliation.generator.config import (
    load_config,
)
from finance_reconciliation.generator.fx import (
    ReferenceFxProvider,
)


def test_eur_rate_is_one() -> None:
    config = load_config()

    provider = ReferenceFxProvider.from_csv(
        config.fx_reference_path
    )

    assert provider.get_rate(
        "EUR",
        date(2026, 1, 10),
    ) == Decimal("1.00000000")


def test_weekend_uses_previous_available_rate() -> None:
    config = load_config()

    provider = ReferenceFxProvider.from_csv(
        config.fx_reference_path
    )

    friday = provider.get_rate(
        "USD",
        date(2026, 1, 9),
    )

    saturday = provider.get_rate(
        "USD",
        date(2026, 1, 10),
    )

    sunday = provider.get_rate(
        "USD",
        date(2026, 1, 11),
    )

    assert saturday == friday
    assert sunday == friday