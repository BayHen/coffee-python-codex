"""Validated customer, employee, and loyalty API schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


def clean_text(value: str) -> str:
    return " ".join(value.strip().split())


def clean_phone(value: str) -> str:
    cleaned = value.strip()
    for character in " -()":
        cleaned = cleaned.replace(character, "")
    return cleaned


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomerCreate(StrictRequest):
    full_name: Annotated[str, Field(min_length=1, max_length=150)]
    phone: Annotated[str | None, Field(pattern=r"^\+?[0-9]{7,15}$")] = None
    email: EmailStr | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_text(value)

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        return None if value is None else clean_phone(value)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return None if value is None else value.strip().lower()

    @model_validator(mode="after")
    def require_contact(self) -> "CustomerCreate":
        if self.phone is None and self.email is None:
            raise ValueError("phone or email is required")
        return self


class CustomerUpdate(StrictRequest):
    full_name: Annotated[str | None, Field(min_length=1, max_length=150)] = None
    phone: Annotated[str | None, Field(pattern=r"^\+?[0-9]{7,15}$")] = None
    email: EmailStr | None = None
    is_active: bool | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return None if value is None else clean_text(value)

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        return None if value is None else clean_phone(value)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return None if value is None else value.strip().lower()

    @model_validator(mode="after")
    def require_change(self) -> "CustomerUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        for field in ("full_name", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CustomerView(BaseModel):
    id: int
    full_name: str
    phone: str | None
    email: str | None
    is_active: bool
    loyalty_points: int
    created_at: datetime


class CustomerPage(BaseModel):
    items: list[CustomerView]
    total: int
    page: int
    page_size: int
    pages: int


class CustomerOrderView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: Literal["draft", "placed", "paid", "cancelled"]
    subtotal_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    created_at: datetime


class CustomerOrderPage(BaseModel):
    items: list[CustomerOrderView]
    total: int
    page: int
    page_size: int
    pages: int


class EmployeeCreate(StrictRequest):
    employee_code: Annotated[
        str, Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9][A-Z0-9._-]*$")
    ]
    full_name: Annotated[str, Field(min_length=1, max_length=150)]
    user_id: Annotated[int | None, Field(gt=0)] = None
    is_active: bool = True

    @field_validator("employee_code", mode="before")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_text(value)


class EmployeeUpdate(StrictRequest):
    employee_code: Annotated[
        str | None,
        Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9][A-Z0-9._-]*$"),
    ] = None
    full_name: Annotated[str | None, Field(min_length=1, max_length=150)] = None
    user_id: Annotated[int | None, Field(gt=0)] = None
    is_active: bool | None = None

    @field_validator("employee_code", mode="before")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return None if value is None else value.strip().upper()

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return None if value is None else clean_text(value)

    @model_validator(mode="after")
    def require_change(self) -> "EmployeeUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        for field in ("employee_code", "full_name", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class EmployeeView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_code: str
    full_name: str
    user_id: int | None
    is_active: bool


class EmployeePage(BaseModel):
    items: list[EmployeeView]
    total: int
    page: int
    page_size: int
    pages: int


class LoyaltyAdjustmentCreate(StrictRequest):
    points_delta: int = Field(ge=-1_000_000, le=1_000_000)
    reason: Annotated[str, Field(min_length=3, max_length=255)]

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return clean_text(value)

    @model_validator(mode="after")
    def reject_zero(self) -> "LoyaltyAdjustmentCreate":
        if self.points_delta == 0:
            raise ValueError("points_delta must not be zero")
        return self


class LoyaltyRefundCreate(StrictRequest):
    reason: Annotated[str, Field(min_length=3, max_length=255)]

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return clean_text(value)


class LoyaltyTransactionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    order_id: int | None
    transaction_type: str
    points_delta: int
    reason: str
    created_at: datetime


class LoyaltyTransactionPage(BaseModel):
    items: list[LoyaltyTransactionView]
    total: int
    page: int
    page_size: int
    pages: int
