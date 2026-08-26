from __future__ import annotations

from collections import defaultdict

PREFIXES = {
    "customer": "CUST",
    "subscription": "SUB",
    "invoice": "INV",
    "payment_attempt": "ATT",
    "financial_event": "EVT",
    "settlement": "STL",
    "settlement_item": "STI",
    "bank_transaction": "BANK",
    "journal_entry": "JE",
    "journal_line": "JL",
}


class IdFactory:
    """Deterministic sequential source identifier factory."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)

    def next(self, entity: str) -> str:
        if entity not in PREFIXES:
            raise KeyError(f"Unknown entity type: {entity}")

        self._counters[entity] += 1

        return (
            f"{PREFIXES[entity]}-"
            f"{self._counters[entity]:06d}"
        )

    def current(self, entity: str) -> int:
        return self._counters.get(entity, 0)