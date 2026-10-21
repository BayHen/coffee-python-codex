"""Fast unit checks for table bill and request validation rules."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.tables.schemas import CheckoutCreate, ItemCreate, TableCreate
from app.tables.service import TableService


def test_bill_counts_only_confirmed_orders_as_payable() -> None:
    session = SimpleNamespace(
        orders=[
            SimpleNamespace(status="confirmed", total_amount=Decimal("93000.00")),
            SimpleNamespace(status="draft", total_amount=Decimal("32000.00")),
            SimpleNamespace(status="cancelled", total_amount=Decimal("9000.00")),
        ]
    )

    bill = TableService.bill(session)

    assert bill.confirmed_subtotal == Decimal("93000.00")
    assert bill.draft_subtotal == Decimal("32000.00")
    assert bill.payable_total == Decimal("93000.00")


def test_table_text_is_normalized() -> None:
    table = TableCreate(table_number="  05 ", name="  Window   table ")
    assert table.table_number == "05"
    assert table.name == "Window table"


@pytest.mark.parametrize("quantity", [0, 101])
def test_item_quantity_limits(quantity: int) -> None:
    with pytest.raises(ValidationError):
        ItemCreate(variant_id=1, quantity=quantity)


def test_valid_item_payload_matches_frontend_contract() -> None:
    payload = ItemCreate(variant_id=1, topping_ids=[2, 3], quantity=2)
    assert payload.model_dump() == {
        "product_id": None,
        "variant_id": 1,
        "topping_ids": [2, 3],
        "quantity": 2,
    }


def test_item_payload_allows_product_with_backend_default_size() -> None:
    payload = ItemCreate(product_id=8, topping_ids=[], quantity=1)
    assert payload.product_id == 8
    assert payload.variant_id is None


def test_item_payload_requires_product_or_variant() -> None:
    with pytest.raises(ValidationError):
        ItemCreate(quantity=1)


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"variant_id": 0, "quantity": 1}, "variant_id"),
        ({"variant_id": 1, "quantity": 0}, "quantity"),
        ({"variant_id": 1, "quantity": 1, "unexpected": True}, "unexpected"),
    ],
)
def test_invalid_item_payload_reports_precise_field(
    payload: dict[str, object], field: str
) -> None:
    with pytest.raises(ValidationError) as error:
        ItemCreate.model_validate(payload)
    assert field in error.value.errors()[0]["loc"]


def test_cash_checkout_requires_received_amount() -> None:
    with pytest.raises(ValidationError):
        CheckoutCreate(method="cash")


def test_bank_transfer_requires_manual_verification() -> None:
    with pytest.raises(ValidationError):
        CheckoutCreate(method="bank_transfer", transfer_confirmed=False)


def test_checkout_accepts_verified_payment_methods() -> None:
    cash = CheckoutCreate(method="cash", cash_received=Decimal("125000.00"))
    transfer = CheckoutCreate(method="bank_transfer", transfer_confirmed=True)
    assert cash.cash_received == Decimal("125000.00")
    assert transfer.transfer_confirmed is True


def test_cash_change_is_zero_when_received_equals_total() -> None:
    assert TableService.calculate_change(
        Decimal("125000.00"), Decimal("125000.00")
    ) == Decimal("0.00")


def test_cash_change_is_exact_when_received_exceeds_total() -> None:
    assert TableService.calculate_change(
        Decimal("125000.00"), Decimal("200000.00")
    ) == Decimal("75000.00")


def test_cash_below_total_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        TableService.calculate_change(Decimal("125000.00"), Decimal("100000.00"))
    assert error.value.status_code == 422
