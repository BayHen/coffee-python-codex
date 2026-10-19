"""Unit tests for inventory units, movements, and low-stock calculations."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.inventory.schemas import IngredientCreate, ManualMovementCreate
from app.inventory.service import fingerprint, ingredient_view


def test_supported_units_and_low_stock_boundary() -> None:
    ingredient = SimpleNamespace(
        id=1,
        sku="MILK",
        name="Milk",
        unit="ml",
        low_stock_threshold=Decimal("500.000"),
        is_active=True,
    )
    view = ingredient_view(ingredient, Decimal("500.000"))
    assert view.is_low_stock is True
    assert view.current_stock == Decimal("500.000")


@pytest.mark.parametrize(
    "payload",
    [
        {"sku": "MILK", "name": "Milk", "unit": "liter"},
        {"sku": "bad sku", "name": "Milk", "unit": "ml"},
        {"sku": "MILK", "name": "   ", "unit": "ml"},
    ],
)
def test_invalid_ingredient_input_is_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        IngredientCreate.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "ingredient_id": 1,
            "transaction_type": "purchase",
            "quantity_delta": "-1",
            "reason": "Wrong direction",
        },
        {
            "ingredient_id": 1,
            "transaction_type": "waste",
            "quantity_delta": "1",
            "reason": "Wrong direction",
        },
        {
            "ingredient_id": 1,
            "transaction_type": "adjustment",
            "quantity_delta": "0",
            "reason": "No movement",
        },
        {
            "ingredient_id": 1,
            "transaction_type": "purchase",
            "quantity_delta": "1",
            "reason": "  ",
        },
    ],
)
def test_invalid_manual_movements_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ManualMovementCreate.model_validate(payload)


def test_inventory_fingerprint_is_stable() -> None:
    assert fingerprint({"a": 1, "b": "2"}) == fingerprint({"b": "2", "a": 1})
