"""Unit tests for catalog input normalization and validation."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.catalog.schemas import (
    CategoryCreate,
    ProductCreate,
    ProductUpdate,
    VariantCreate,
)


def test_catalog_inputs_are_normalized() -> None:
    category = CategoryCreate(name="  Cà phê   nóng ")
    product = ProductCreate(category_id=1, name="  Cà phê sữa  ")
    variant = VariantCreate(sku=" latte.m ", name="  Size M ", price="45000.00")

    assert category.name == "Cà phê nóng"
    assert product.name == "Cà phê sữa"
    assert variant.sku == "LATTE.M"
    assert variant.name == "Size M"
    assert variant.price == Decimal("45000.00")


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (CategoryCreate, {"name": "   "}),
        (ProductCreate, {"category_id": 0, "name": "Latte"}),
        (VariantCreate, {"sku": "bad sku", "name": "M", "price": "1.00"}),
        (VariantCreate, {"sku": "OK", "name": "M", "price": "-0.01"}),
        (VariantCreate, {"sku": "OK", "name": "M", "price": "1.001"}),
        (ProductUpdate, {}),
        (ProductUpdate, {"is_active": None}),
    ],
)
def test_catalog_rejects_invalid_inputs(
    model: type, payload: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)
