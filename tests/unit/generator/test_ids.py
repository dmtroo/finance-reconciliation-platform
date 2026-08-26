import pytest

from finance_reconciliation.generator.ids import IdFactory


def test_ids_are_sequential_and_zero_padded() -> None:
    ids = IdFactory()

    assert ids.next("invoice") == "INV-000001"
    assert ids.next("invoice") == "INV-000002"

    assert ids.next("customer") == "CUST-000001"

    assert ids.next("invoice") == "INV-000003"


def test_unknown_entity_is_rejected() -> None:
    ids = IdFactory()

    with pytest.raises(KeyError):
        ids.next("unknown")