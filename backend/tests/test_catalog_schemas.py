"""Unit tests for catalog input normalization and validation."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.catalog.schemas import (
    CategoryCreate,
    ProductCreate,
    ProductUpdate,
    ToppingUpdate,
    VariantCreate,
    VariantUpdate,
)


def test_catalog_inputs_are_normalized() -> None:
    category = CategoryCreate(name="  Cà phê   nóng ")
    product = ProductCreate(category_id=1, name="  Cà phê sữa  ")
    variant = VariantCreate(name="  Size M ", price="45000.00")

    assert category.name == "Cà phê nóng"
    assert product.name == "Cà phê sữa"
    assert variant.name == "Size M"
    assert variant.price == Decimal("45000.00")


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (CategoryCreate, {"name": "   "}),
        (ProductCreate, {"category_id": 0, "name": "Latte"}),
        (VariantCreate, {"name": "M", "price": "-0.01"}),
        (VariantCreate, {"name": "M", "price": "1.001"}),
        (VariantCreate, {"sku": "MANUAL", "name": "M", "price": "1.00"}),
        (VariantUpdate, {"sku": "MANUAL"}),
        (VariantUpdate, {"is_active": False}),
        (ToppingUpdate, {"is_active": False}),
        (ProductUpdate, {}),
        (ProductUpdate, {"is_active": None}),
    ],
)
def test_catalog_rejects_invalid_inputs(
    model: type, payload: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)
