"""Unit tests for order validation, totals, workflow, and fingerprints."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.orders.schemas import OrderCreate
from app.orders.service import ALLOWED_TRANSITIONS, OrderService, order_fingerprint


def test_totals_use_decimal_and_half_up_rounding() -> None:
    discount, total = OrderService._totals(Decimal("11.45"), Decimal("10.00"))
    assert discount == Decimal("1.15")
    assert total == Decimal("10.30")


def test_order_fingerprint_is_independent_of_item_order() -> None:
    first = OrderCreate.model_validate(
        {
            "items": [
                {"variant_id": 2, "quantity": 1},
                {"variant_id": 1, "quantity": 2},
            ]
        }
    )
    second = OrderCreate.model_validate(
        {
            "items": [
                {"variant_id": 1, "quantity": 2},
                {"variant_id": 2, "quantity": 1},
            ]
        }
    )
    assert order_fingerprint(first) == order_fingerprint(second)


@pytest.mark.parametrize(
    "payload",
    [
        {"items": []},
        {
            "items": [
                {"variant_id": 1, "quantity": 1},
                {"variant_id": 1, "quantity": 2},
            ]
        },
        {"items": [{"variant_id": 1, "quantity": 0}]},
        {
            "items": [{"variant_id": 1, "quantity": 1}],
            "discount_percent": "20.01",
            "discount_reason": "Too much",
        },
        {
            "items": [{"variant_id": 1, "quantity": 1}],
            "discount_percent": "10.00",
        },
        {
            "items": [{"variant_id": 1, "quantity": 1}],
            "discount_percent": "10.00",
            "discount_reason": "   ",
        },
        {
            "items": [{"variant_id": 1, "quantity": 1}],
            "total_amount": "0.01",
        },
    ],
)
def test_invalid_order_requests_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        OrderCreate.model_validate(payload)


def test_state_machine_has_terminal_paid_and_cancelled_states() -> None:
    assert ALLOWED_TRANSITIONS["draft"] == {"placed", "cancelled"}
    assert ALLOWED_TRANSITIONS["placed"] == {"paid", "cancelled"}
    assert ALLOWED_TRANSITIONS["paid"] == set()
    assert ALLOWED_TRANSITIONS["cancelled"] == set()


def test_equivalent_decimal_discounts_have_same_fingerprint() -> None:
    base = {
        "items": [{"variant_id": 1, "quantity": 1}],
        "discount_reason": "Promotion",
    }
    first = OrderCreate.model_validate(base | {"discount_percent": "10.0"})
    second = OrderCreate.model_validate(base | {"discount_percent": "10.00"})
    assert order_fingerprint(first) == order_fingerprint(second)
