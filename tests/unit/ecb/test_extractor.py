from datetime import date
from decimal import Decimal

from finance_reconciliation.ecb.extractor import (
    EcbMode,
    extract_ecb_rates,
    parse_api_csv,
    read_raw_csv,
)

API_SAMPLE = """KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE
EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2026-01-02,1.1700
EXR.D.GBP.EUR.SP00.A,D,GBP,EUR,SP00,A,2026-01-02,0.8600
EXR.D.PLN.EUR.SP00.A,D,PLN,EUR,SP00,A,2026-01-02,4.3000
EXR.D.SEK.EUR.SP00.A,D,SEK,EUR,SP00,A,2026-01-02,10.9000
"""


def test_api_csv_preserves_source_orientation() -> None:
    observations = parse_api_csv(
        API_SAMPLE
    )

    by_currency = {
        observation.currency: observation
        for observation
        in observations
    }

    assert (
        by_currency["USD"].units_per_eur
        == Decimal("1.1700")
    )

    assert (
        by_currency["PLN"].units_per_eur
        == Decimal("4.3000")
    )


def test_fixture_extraction_writes_source_rates(
    tmp_path,
) -> None:
    raw_path = (
        tmp_path
        / "raw.csv"
    )

    reference_path = (
        tmp_path
        / "reference.csv"
    )

    result = extract_ecb_rates(
        start_date=date(
            2026,
            1,
            1,
        ),
        end_date=date(
            2026,
            1,
            10,
        ),
        mode=EcbMode.FIXTURE,
        lookback_days=7,
        raw_output=raw_path,
        reference_output=reference_path,
    )

    assert result.row_count > 0

    observations = read_raw_csv(
        raw_path
    )

    assert observations

    assert all(
        observation.currency
        in {
            "USD",
            "GBP",
            "PLN",
            "SEK",
        }
        for observation
        in observations
    )

    assert reference_path.exists()


def test_raw_fixture_does_not_create_eur_series(
    tmp_path,
) -> None:
    raw_path = (
        tmp_path
        / "raw.csv"
    )

    reference_path = (
        tmp_path
        / "reference.csv"
    )

    extract_ecb_rates(
        start_date=date(
            2026,
            1,
            1,
        ),
        end_date=date(
            2026,
            1,
            10,
        ),
        mode=EcbMode.FIXTURE,
        raw_output=raw_path,
        reference_output=reference_path,
    )

    observations = read_raw_csv(
        raw_path
    )

    assert all(
        observation.currency != "EUR"
        for observation
        in observations
    )