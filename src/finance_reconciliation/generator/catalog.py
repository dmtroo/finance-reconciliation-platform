from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from finance_reconciliation.generator.config import resolve_project_path


@dataclass(frozen=True)
class ProductDefinition:
    product_id: str
    product_name: str
    product_family: str
    billing_interval: str
    list_price_minor: int
    currency: str
    selection_weight: float


def load_catalog(path: str | Path) -> list[ProductDefinition]:
    catalog_path = resolve_project_path(path)

    raw = yaml.safe_load(
        catalog_path.read_text(encoding="utf-8")
    )

    products = [
        ProductDefinition(**product)
        for product in raw["products"]
    ]

    product_ids = [
        product.product_id
        for product in products
    ]

    if len(product_ids) != len(set(product_ids)):
        raise ValueError(
            "Product catalog contains duplicate product_id values"
        )

    total_weight = sum(
        product.selection_weight
        for product in products
    )

    if abs(total_weight - 1.0) > 1e-9:
        raise ValueError(
            f"Product selection weights must sum to 1.0; got {total_weight}"
        )

    return products