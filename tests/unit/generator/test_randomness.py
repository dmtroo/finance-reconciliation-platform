from finance_reconciliation.generator.randomness import (
    DeterministicRandom,
)


def test_same_seed_produces_same_sequence() -> None:
    first = DeterministicRandom(seed=42)
    second = DeterministicRandom(seed=42)

    first_values = [
        first.randint(1, 1000)
        for _ in range(20)
    ]

    second_values = [
        second.randint(1, 1000)
        for _ in range(20)
    ]

    assert first_values == second_values


def test_weighted_choice_is_deterministic() -> None:
    weights = {
        "CARD": 0.70,
        "PAYPAL": 0.12,
        "APPLE_PAY": 0.10,
        "GOOGLE_PAY": 0.08,
    }

    first = DeterministicRandom(seed=42)
    second = DeterministicRandom(seed=42)

    assert [
        first.weighted_choice(weights)
        for _ in range(100)
    ] == [
        second.weighted_choice(weights)
        for _ in range(100)
    ]