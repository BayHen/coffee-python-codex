"""Unit tests for customer, employee, and loyalty validation."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.people.schemas import (
    CustomerCreate,
    EmployeeCreate,
    LoyaltyAdjustmentCreate,
)
from app.people.service import fingerprint, points_for_paid_amount


def test_customer_contact_is_normalized() -> None:
    customer = CustomerCreate(
        full_name="  Nguyễn   An ",
        phone="+84 (912) 345-678",
        email=" AN@example.com ",
    )
    assert customer.full_name == "Nguyễn An"
    assert customer.phone == "+84912345678"
    assert str(customer.email) == "an@example.com"


@pytest.mark.parametrize(
    "payload",
    [
        {"full_name": "No Contact"},
        {"full_name": "Bad Phone", "phone": "123"},
        {"full_name": "Bad Email", "email": "not-an-email"},
        {"full_name": "   ", "phone": "+84912345678"},
    ],
)
def test_invalid_customers_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CustomerCreate.model_validate(payload)


def test_employee_code_is_normalized() -> None:
    employee = EmployeeCreate(employee_code=" staff-01 ", full_name="  Mai  Lan ")
    assert employee.employee_code == "STAFF-01"
    assert employee.full_name == "Mai Lan"


def test_zero_loyalty_adjustment_is_rejected() -> None:
    with pytest.raises(ValidationError):
        LoyaltyAdjustmentCreate(points_delta=0, reason="No change")


def test_loyalty_points_round_down_by_ten_currency_units() -> None:
    assert points_for_paid_amount(Decimal("9.99")) == 0
    assert points_for_paid_amount(Decimal("10.00")) == 1
    assert points_for_paid_amount(Decimal("29.99")) == 2


def test_people_fingerprint_is_stable() -> None:
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})
