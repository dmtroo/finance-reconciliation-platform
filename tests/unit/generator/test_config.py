from datetime import date

from finance_reconciliation.generator.config import load_config


def test_example_config_is_valid() -> None:
    config = load_config()

    assert config.seed == 42
    assert config.scenario == "clean"

    assert config.start_date == date(2026, 1, 1)
    assert config.end_date == date(2026, 1, 31)
    assert config.as_of_date == date(2026, 2, 10)


def test_run_id_is_deterministic() -> None:
    config = load_config()

    assert config.run_id == (
        "SYN-42-"
        "2026-01-01-"
        "2026-01-31-"
        "clean"
    )